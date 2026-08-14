import os
import re
import json
import base64
from enum import Enum
from typing import Any, Dict, List, Optional, Union
import httpx
import structlog
from pydantic import BaseModel, Field

from backend.core.config import settings
from backend.rag.chunking import DocumentType, DocumentElement, ParsedDocument

logger = structlog.get_logger(__name__)


SUPPORTED_FORMATS = {
    ".pdf": DocumentType.PDF,
    ".html": DocumentType.HTML,
    ".htm": DocumentType.HTML,
    ".txt": DocumentType.TXT,
    ".docx": DocumentType.DOCX,
    ".xlsx": DocumentType.TXT,
    ".pptx": DocumentType.TXT,
    ".epub": DocumentType.TXT,
    ".md": DocumentType.TXT,
    ".csv": DocumentType.TXT,
    ".log": DocumentType.TXT,
    ".json": DocumentType.TXT,
    ".xml": DocumentType.TXT,
    ".rst": DocumentType.TXT,
}


class AnyDocParser:
    """
    Multi-format document parsing engine supporting Firecrawl AnyDoc & PDF-Inspector API
    with offline fallback parsing stack (BeautifulSoup, pdfplumber, unstructured).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_url: Optional[str] = None,
    ):
        self.api_key = api_key or settings.FIRECRAWL_API_KEY
        self.api_url = (api_url or settings.FIRECRAWL_API_URL).rstrip("/")

    @staticmethod
    def detect_format(file_path: str) -> DocumentType:
        ext = os.path.splitext(file_path)[1].lower()
        return SUPPORTED_FORMATS.get(ext, DocumentType.UNKNOWN)

    def parse(
        self,
        file_path: str,
        content: Optional[bytes] = None,
        company_ticker: Optional[str] = None,
        fiscal_year: Optional[int] = None,
        doc_category: str = "general",
        force_local: bool = False,
    ) -> ParsedDocument:
        """Synchronous parse entrypoint."""
        doc_type = self.detect_format(file_path)
        filename = os.path.basename(file_path)
        logger.info("anydoc_parse_start", filename=filename, doc_type=doc_type.value, force_local=force_local)

        if not content and os.path.exists(file_path):
            with open(file_path, "rb") as f:
                content = f.read()

        # Try Firecrawl API if configured and not explicitly forced local
        if self.api_key and not force_local and content:
            try:
                parsed = self._parse_with_firecrawl_sync(
                    filename=filename,
                    content=content,
                    doc_type=doc_type,
                    company_ticker=company_ticker,
                    fiscal_year=fiscal_year,
                )
                if parsed:
                    return parsed
            except Exception as exc:
                logger.warning(
                    "firecrawl_parse_failed_falling_back",
                    filename=filename,
                    error=str(exc),
                )

        # Fallback to local offline parsing stack
        return self._parse_local(
            filename=filename,
            file_path=file_path,
            content=content,
            doc_type=doc_type,
            company_ticker=company_ticker,
            fiscal_year=fiscal_year,
            doc_category=doc_category,
        )

    async def parse_async(
        self,
        file_path: str,
        content: Optional[bytes] = None,
        company_ticker: Optional[str] = None,
        fiscal_year: Optional[int] = None,
        doc_category: str = "general",
        force_local: bool = False,
    ) -> ParsedDocument:
        """Asynchronous parse entrypoint."""
        doc_type = self.detect_format(file_path)
        filename = os.path.basename(file_path)

        if not content and os.path.exists(file_path):
            with open(file_path, "rb") as f:
                content = f.read()

        if self.api_key and not force_local and content:
            try:
                parsed = await self._parse_with_firecrawl_async(
                    filename=filename,
                    content=content,
                    doc_type=doc_type,
                    company_ticker=company_ticker,
                    fiscal_year=fiscal_year,
                )
                if parsed:
                    return parsed
            except Exception as exc:
                logger.warning(
                    "firecrawl_async_parse_failed_falling_back",
                    filename=filename,
                    error=str(exc),
                )

        return self._parse_local(
            filename=filename,
            file_path=file_path,
            content=content,
            doc_type=doc_type,
            company_ticker=company_ticker,
            fiscal_year=fiscal_year,
            doc_category=doc_category,
        )

    def _parse_with_firecrawl_sync(
        self,
        filename: str,
        content: bytes,
        doc_type: DocumentType,
        company_ticker: Optional[str],
        fiscal_year: Optional[int],
    ) -> Optional[ParsedDocument]:
        endpoint = f"{self.api_url}/parse"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        encoded_content = base64.b64encode(content).decode("utf-8")
        payload = {
            "file": encoded_content,
            "filename": filename,
            "formats": ["markdown"],
        }

        with httpx.Client(timeout=30.0) as client:
            resp = client.post(endpoint, json=payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                markdown = data.get("markdown") or data.get("data", {}).get("markdown", "")
                if markdown:
                    elements = self._markdown_to_elements(markdown)
                    return ParsedDocument(
                        filename=filename,
                        doc_type=doc_type,
                        elements=elements,
                        raw_text=markdown,
                    )
        return None

    async def _parse_with_firecrawl_async(
        self,
        filename: str,
        content: bytes,
        doc_type: DocumentType,
        company_ticker: Optional[str],
        fiscal_year: Optional[int],
    ) -> Optional[ParsedDocument]:
        endpoint = f"{self.api_url}/parse"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        encoded_content = base64.b64encode(content).decode("utf-8")
        payload = {
            "file": encoded_content,
            "filename": filename,
            "formats": ["markdown"],
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(endpoint, json=payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                markdown = data.get("markdown") or data.get("data", {}).get("markdown", "")
                if markdown:
                    elements = self._markdown_to_elements(markdown)
                    return ParsedDocument(
                        filename=filename,
                        doc_type=doc_type,
                        elements=elements,
                        raw_text=markdown,
                    )
        return None

    def _parse_local(
        self,
        filename: str,
        file_path: str,
        content: Optional[bytes],
        doc_type: DocumentType,
        company_ticker: Optional[str],
        fiscal_year: Optional[int],
        doc_category: str,
    ) -> ParsedDocument:
        elements: List[DocumentElement] = []
        raw_text = ""

        if doc_type == DocumentType.HTML:
            elements, raw_text = self._parse_local_html(content, file_path)
        elif doc_type == DocumentType.PDF:
            elements, raw_text = self._parse_local_pdf(content, file_path)
        else:
            elements, raw_text = self._parse_local_text(content, file_path)

        return ParsedDocument(
            filename=filename,
            doc_type=doc_type,
            elements=elements,
            raw_text=raw_text,
        )

    def _parse_local_html(
        self, content: Optional[bytes], file_path: str
    ) -> tuple[List[DocumentElement], str]:
        elements: List[DocumentElement] = []
        html_str = ""

        if content:
            html_str = content.decode("utf-8", errors="ignore")
        elif os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                html_str = f.read()

        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html_str, "html.parser")

            # Remove script and style elements
            for element in soup(["script", "style"]):
                element.decompose()

            current_heading = None
            page_num = 1

            for tag in soup.find_all(["h1", "h2", "h3", "h4", "p", "table", "div"]):
                name = tag.name.lower()
                text = tag.get_text(separator=" ", strip=True)

                if not text:
                    continue

                if name in ["h1", "h2", "h3", "h4"]:
                    current_heading = text
                    elements.append(
                        DocumentElement(
                            element_type="title",
                            text=f"### {text}",
                            page_number=page_num,
                            section_heading=current_heading,
                        )
                    )
                elif name == "table":
                    rows_data = []
                    markdown_rows = []
                    for tr in tag.find_all("tr"):
                        cols = [
                            td.get_text(strip=True)
                            for td in tr.find_all(["td", "th"])
                        ]
                        if cols:
                            rows_data.append(cols)
                            markdown_rows.append("| " + " | ".join(cols) + " |")

                    if markdown_rows:
                        table_md = "\n".join(markdown_rows)
                        elements.append(
                            DocumentElement(
                                element_type="table",
                                text=table_md,
                                page_number=page_num,
                                section_heading=current_heading,
                                metadata={"table_matrix": rows_data},
                            )
                        )
                else:
                    # Paragraph / div text element
                    elements.append(
                        DocumentElement(
                            element_type="text",
                            text=text,
                            page_number=page_num,
                            section_heading=current_heading,
                        )
                    )

            raw_text = "\n\n".join(e.text for e in elements)
            return elements, raw_text

        except Exception as err:
            logger.warning("bs4_html_parse_failed_falling_back", error=str(err))

        # Basic regex fallback for HTML
        clean_text = re.sub(r"<[^>]+>", " ", html_str)
        clean_text = re.sub(r"\s+", " ", clean_text).strip()
        lines = [line.strip() for line in clean_text.splitlines() if line.strip()]
        elements = [
            DocumentElement(element_type="text", text=line, page_number=1)
            for line in lines
        ]
        return elements, clean_text

    def _parse_local_pdf(
        self, content: Optional[bytes], file_path: str
    ) -> tuple[List[DocumentElement], str]:
        elements: List[DocumentElement] = []
        raw_text_parts = []

        # 1. Try pdfplumber if available
        try:
            import pdfplumber
            import io

            pdf_file = io.BytesIO(content) if content else file_path
            with pdfplumber.open(pdf_file) as pdf:
                for idx, page in enumerate(pdf.pages, start=1):
                    page_text = page.extract_text() or ""
                    tables = page.extract_tables() or []

                    if page_text:
                        raw_text_parts.append(page_text)
                        lines = page_text.splitlines()
                        current_heading = None
                        for line in lines:
                            line_str = line.strip()
                            if not line_str:
                                continue
                            if len(line_str) < 80 and (line_str.isupper() or line_str.startswith("#")):
                                current_heading = line_str
                                elements.append(
                                    DocumentElement(
                                        element_type="title",
                                        text=line_str,
                                        page_number=idx,
                                        section_heading=current_heading,
                                    )
                                )
                            else:
                                elements.append(
                                    DocumentElement(
                                        element_type="text",
                                        text=line_str,
                                        page_number=idx,
                                        section_heading=current_heading,
                                    )
                                )

                    for tbl in tables:
                        md_rows = [
                            "| " + " | ".join(str(c or "") for c in row) + " |"
                            for row in tbl
                            if any(row)
                        ]
                        if md_rows:
                            elements.append(
                                DocumentElement(
                                    element_type="table",
                                    text="\n".join(md_rows),
                                    page_number=idx,
                                    metadata={"table_matrix": tbl},
                                )
                            )

            raw_text = "\n\n".join(raw_text_parts)
            if elements:
                return elements, raw_text
        except Exception as err:
            logger.warning("pdfplumber_parse_failed", error=str(err))

        # 2. Try unstructured auto partition if pdfplumber fails or is missing
        try:
            from unstructured.partition.auto import partition

            if os.path.exists(file_path):
                raw_elements = partition(filename=file_path)
                current_heading = None
                for elem in raw_elements:
                    cat = getattr(elem, "category", "text").lower()
                    elem_text = str(elem).strip()
                    page_num = getattr(getattr(elem, "metadata", None), "page_number", 1) or 1

                    if cat in ["title", "header", "heading"]:
                        current_heading = elem_text
                    
                    elements.append(
                        DocumentElement(
                            element_type=cat,
                            text=elem_text,
                            page_number=page_num,
                            section_heading=current_heading,
                        )
                    )
                raw_text = "\n\n".join(e.text for e in elements)
                if elements:
                    return elements, raw_text
        except Exception as err:
            logger.warning("unstructured_parse_failed", error=str(err))

        # 3. Try pypdf or PyPDF2 fallback
        try:
            import io
            import pypdf

            pdf_file = io.BytesIO(content) if content else file_path
            reader = pypdf.PdfReader(pdf_file)
            for idx, page in enumerate(reader.pages, start=1):
                page_text = page.extract_text() or ""
                if page_text:
                    raw_text_parts.append(page_text)
                    for line in page_text.splitlines():
                        line_str = line.strip()
                        if line_str:
                            elements.append(
                                DocumentElement(
                                    element_type="text",
                                    text=line_str,
                                    page_number=idx,
                                )
                            )
            raw_text = "\n\n".join(raw_text_parts)
            if elements:
                return elements, raw_text
        except Exception as err:
            logger.warning("pypdf_parse_failed", error=str(err))

        # 3. Last fallback text decoding
        text = content.decode("utf-8", errors="ignore") if content else ""
        elements = [
            DocumentElement(element_type="text", text=line.strip(), page_number=1)
            for line in text.splitlines()
            if line.strip()
        ]
        return elements, text

    def _parse_local_text(
        self, content: Optional[bytes], file_path: str
    ) -> tuple[List[DocumentElement], str]:
        elements: List[DocumentElement] = []
        if content:
            raw_text = content.decode("utf-8", errors="ignore")
        elif os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                raw_text = f.read()
        else:
            raw_text = ""

        current_heading = None
        for line in raw_text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#") or (len(stripped) < 80 and stripped.isupper()):
                current_heading = stripped.lstrip("#").strip()
                elements.append(
                    DocumentElement(
                        element_type="title",
                        text=stripped,
                        page_number=1,
                        section_heading=current_heading,
                    )
                )
            elif "|" in stripped or "\t" in stripped:
                cols = [c.strip() for c in re.split(r"[|\t]", stripped) if c.strip()]
                elements.append(
                    DocumentElement(
                        element_type="table",
                        text=stripped,
                        page_number=1,
                        section_heading=current_heading,
                        metadata={"table_matrix": cols},
                    )
                )
            else:
                elements.append(
                    DocumentElement(
                        element_type="text",
                        text=stripped,
                        page_number=1,
                        section_heading=current_heading,
                    )
                )

        return elements, raw_text

    def _markdown_to_elements(self, markdown: str) -> List[DocumentElement]:
        elements: List[DocumentElement] = []
        current_heading = None
        page_num = 1

        for block in markdown.split("\n\n"):
            stripped = block.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                current_heading = stripped.lstrip("#").strip()
                elements.append(
                    DocumentElement(
                        element_type="title",
                        text=stripped,
                        page_number=page_num,
                        section_heading=current_heading,
                    )
                )
            elif "|" in stripped:
                elements.append(
                    DocumentElement(
                        element_type="table",
                        text=stripped,
                        page_number=page_num,
                        section_heading=current_heading,
                    )
                )
            else:
                elements.append(
                    DocumentElement(
                        element_type="text",
                        text=stripped,
                        page_number=page_num,
                        section_heading=current_heading,
                    )
                )
        return elements
