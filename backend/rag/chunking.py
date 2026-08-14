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
    """Multi-Format Document Parsing Engine supporting PDF, HTML, TXT, DOCX, and AnyDoc formats."""

    def __init__(self, api_key: Optional[str] = None, api_url: Optional[str] = None):
        from backend.rag.anydoc_parser import AnyDocParser
        self.anydoc_parser = AnyDocParser(api_key=api_key, api_url=api_url)

    @staticmethod
    def detect_format(file_path: str) -> DocumentType:
        from backend.rag.anydoc_parser import AnyDocParser
        return AnyDocParser.detect_format(file_path)

    def parse(
        self,
        file_path: str,
        content: Optional[bytes] = None,
        company_ticker: Optional[str] = None,
        fiscal_year: Optional[int] = None,
        use_unstructured: bool = False,
    ) -> ParsedDocument:
        return self.anydoc_parser.parse(
            file_path=file_path,
            content=content,
            company_ticker=company_ticker,
            fiscal_year=fiscal_year,
            force_local=use_unstructured,
        )


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
