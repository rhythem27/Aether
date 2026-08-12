import os
import re
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import structlog

logger = structlog.get_logger(__name__)


class DocumentType(str, Enum):
    PDF = "pdf"
    HTML = "html"
    TXT = "txt"
    DOCX = "docx"
    UNKNOWN = "unknown"


class ChunkMetadata(BaseModel):
    source_file: str
    page_number: int = 1
    section_heading: Optional[str] = None
    company_ticker: Optional[str] = None
    company_name: Optional[str] = None
    fiscal_year: Optional[int] = None
    document_type: str = "general"
    has_tables: bool = False
    tables_json: List[Dict[str, Any]] = Field(default_factory=list)


class DocumentChunk(BaseModel):
    chunk_id: str
    text: str
    token_count: int
    metadata: ChunkMetadata


class DocumentElement(BaseModel):
    element_type: str  # "title", "text", "table", "header"
    text: str
    page_number: int = 1
    section_heading: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ParsedDocument(BaseModel):
    filename: str
    doc_type: DocumentType
    elements: List[DocumentElement]
    raw_text: str


class DocumentParser:
    """Multi-Format Document Parsing Engine supporting PDF, HTML, TXT, and DOCX."""

    @staticmethod
    def detect_format(file_path: str) -> DocumentType:
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".pdf":
            return DocumentType.PDF
        elif ext in [".html", ".htm"]:
            return DocumentType.HTML
        elif ext == ".docx":
            return DocumentType.DOCX
        elif ext in [".txt", ".log", ".csv", ".md"]:
            return DocumentType.TXT
        return DocumentType.UNKNOWN

    def parse(
        self,
        file_path: str,
        content: Optional[bytes] = None,
        company_ticker: Optional[str] = None,
        fiscal_year: Optional[int] = None,
        use_unstructured: bool = False,
    ) -> ParsedDocument:
        doc_type = self.detect_format(file_path)
        logger.info("parsing_document", file_path=file_path, doc_type=doc_type.value)

        text_content = ""
        elements: List[DocumentElement] = []

        if content:
            raw_str = content.decode("utf-8", errors="ignore")
        elif os.path.exists(file_path):
            with open(file_path, "rb") as f:
                raw_str = f.read().decode("utf-8", errors="ignore")
        else:
            raw_str = ""

        # Attempt unstructured parsing only if explicitly requested or if file is PDF
        parsed_via_unstructured = False
        if use_unstructured or doc_type == DocumentType.PDF:
            try:
                from unstructured.partition.auto import partition

                if os.path.exists(file_path):
                    raw_elements = partition(filename=file_path)
                    if raw_elements:
                        current_section = None
                        for idx, elem in enumerate(raw_elements):
                            elem_type = getattr(elem, "category", "text").lower()
                            elem_text = str(elem).strip()
                            page_num = (
                                getattr(
                                    getattr(elem, "metadata", None), "page_number", 1
                                )
                                or 1
                            )

                            if elem_type in ["title", "header", "heading"]:
                                current_section = elem_text

                            table_data = []
                            if elem_type == "table":
                                html_table = getattr(
                                    getattr(elem, "metadata", None), "text_as_html", ""
                                )
                                table_data = [
                                    {"raw_html": html_table, "text": elem_text}
                                ]

                            elements.append(
                                DocumentElement(
                                    element_type=elem_type,
                                    text=elem_text,
                                    page_number=page_num,
                                    section_heading=current_section,
                                    metadata=(
                                        {"table_data": table_data} if table_data else {}
                                    ),
                                )
                            )
                        text_content = "\n\n".join(e.text for e in elements)
                        parsed_via_unstructured = True
            except Exception as err:
                logger.warning(
                    "unstructured_partition_fallback",
                    file_path=file_path,
                    error=str(err),
                )

        if not parsed_via_unstructured:
            # High-speed fallback parser logic
            text_content = raw_str
            elements = self._fallback_parse(raw_str, doc_type)

        return ParsedDocument(
            filename=os.path.basename(file_path),
            doc_type=doc_type,
            elements=elements,
            raw_text=text_content,
        )

    def _fallback_parse(
        self, text: str, doc_type: DocumentType
    ) -> List[DocumentElement]:
        elements = []
        lines = text.splitlines()
        current_section = None

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            # Detect title / heading lines
            if stripped.startswith("#") or (len(stripped) < 80 and stripped.isupper()):
                current_section = stripped.lstrip("#").strip()
                elements.append(
                    DocumentElement(
                        element_type="title",
                        text=stripped,
                        page_number=1,
                        section_heading=current_section,
                    )
                )
            # Detect table structure (e.g. pipe-delimited or tab-separated matrix)
            elif "|" in stripped or "\t" in stripped:
                cols = [c.strip() for c in re.split(r"[|\t]", stripped) if c.strip()]
                elements.append(
                    DocumentElement(
                        element_type="table",
                        text=stripped,
                        page_number=1,
                        section_heading=current_section,
                        metadata={"table_matrix": cols},
                    )
                )
            else:
                elements.append(
                    DocumentElement(
                        element_type="text",
                        text=stripped,
                        page_number=1,
                        section_heading=current_section,
                    )
                )

        return elements


class TokenAwareChunker:
    """Dynamic token-aware chunker respecting section boundaries, max token limits, and table structures."""

    def __init__(self, max_tokens: int = 512, overlap: int = 50):
        self.max_tokens = max_tokens
        self.overlap = overlap

    @staticmethod
    def count_tokens(text: str) -> int:
        """Estimate token count (approx. 4 chars per token fallback or tiktoken if installed)."""
        try:
            import tiktoken

            enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text))
        except Exception:
            return max(1, len(text.split()) * 4 // 3)

    def chunk_document(
        self,
        document: ParsedDocument,
        company_ticker: Optional[str] = None,
        company_name: Optional[str] = None,
        fiscal_year: Optional[int] = None,
        document_type: str = "financial_report",
    ) -> List[DocumentChunk]:
        chunks: List[DocumentChunk] = []
        chunk_idx = 0

        current_text_buf: List[str] = []
        current_token_count = 0
        current_section: Optional[str] = None
        current_page = 1
        tables_in_chunk: List[Dict[str, Any]] = []

        for element in document.elements:
            elem_tokens = self.count_tokens(element.text)

            # If element is a table, retain its structured payload
            if element.element_type == "table":
                tables_in_chunk.append(
                    {"text": element.text, "metadata": element.metadata}
                )

            # Check if adding this element exceeds max token window
            if current_token_count + elem_tokens > self.max_tokens and current_text_buf:
                chunk_text = "\n\n".join(current_text_buf)
                chunk_idx += 1

                chunks.append(
                    DocumentChunk(
                        chunk_id=f"{document.filename}_chunk_{chunk_idx}",
                        text=chunk_text,
                        token_count=current_token_count,
                        metadata=ChunkMetadata(
                            source_file=document.filename,
                            page_number=current_page,
                            section_heading=current_section,
                            company_ticker=company_ticker,
                            company_name=company_name,
                            fiscal_year=fiscal_year,
                            document_type=document_type,
                            has_tables=len(tables_in_chunk) > 0,
                            tables_json=tables_in_chunk,
                        ),
                    )
                )

                # Reset buffer
                current_text_buf = []
                current_token_count = 0
                tables_in_chunk = []

            current_text_buf.append(element.text)
            current_token_count += elem_tokens
            current_page = element.page_number
            if element.section_heading:
                current_section = element.section_heading

        # Flush remaining buffer
        if current_text_buf:
            chunk_text = "\n\n".join(current_text_buf)
            chunk_idx += 1
            chunks.append(
                DocumentChunk(
                    chunk_id=f"{document.filename}_chunk_{chunk_idx}",
                    text=chunk_text,
                    token_count=current_token_count,
                    metadata=ChunkMetadata(
                        source_file=document.filename,
                        page_number=current_page,
                        section_heading=current_section,
                        company_ticker=company_ticker,
                        company_name=company_name,
                        fiscal_year=fiscal_year,
                        document_type=document_type,
                        has_tables=len(tables_in_chunk) > 0,
                        tables_json=tables_in_chunk,
                    ),
                )
            )

        logger.info(
            "chunking_complete", filename=document.filename, num_chunks=len(chunks)
        )
        return chunks
