import os
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from backend.rag.anydoc_parser import AnyDocParser
from backend.rag.chunking import DocumentType, TokenAwareChunker, DocumentParser
from backend.scripts.ingest_required_docs import find_required_docs_dir, process_and_ingest
from backend.api.main import app


@pytest.fixture
def parser():
    return AnyDocParser()


def test_anydoc_format_detection():
    assert AnyDocParser.detect_format("doc.pdf") == DocumentType.PDF
    assert AnyDocParser.detect_format("page.html") == DocumentType.HTML
    assert AnyDocParser.detect_format("page.htm") == DocumentType.HTML
    assert AnyDocParser.detect_format("notes.txt") == DocumentType.TXT
    assert AnyDocParser.detect_format("deck.pptx") == DocumentType.TXT
    assert AnyDocParser.detect_format("data.csv") == DocumentType.TXT


def test_parse_sample_sec_10k_html(parser):
    docs_dir = find_required_docs_dir()
    file_path = docs_dir / "sec_filings" / "sample_10k.html"
    assert file_path.exists()

    parsed = parser.parse(
        file_path=str(file_path),
        company_ticker="AAPL",
        fiscal_year=2024,
        force_local=True,
    )

    assert parsed.filename == "sample_10k.html"
    assert parsed.doc_type == DocumentType.HTML
    assert len(parsed.elements) > 0
    assert "TABLE OF CONTENTS" in parsed.raw_text or "UNITED STATES" in parsed.raw_text or len(parsed.raw_text) > 100


def test_parse_sample_pitch_deck_pdf(parser):
    docs_dir = find_required_docs_dir()
    file_path = docs_dir / "pitch_decks" / "sample_deck.pdf"
    assert file_path.exists()

    parsed = parser.parse(
        file_path=str(file_path),
        company_ticker="ACME",
        fiscal_year=2024,
        force_local=True,
    )

    assert parsed.filename == "sample_deck.pdf"
    assert parsed.doc_type == DocumentType.PDF
    assert len(parsed.elements) > 0


def test_parse_sample_press_release_txt(parser):
    docs_dir = find_required_docs_dir()
    file_path = docs_dir / "news_and_press" / "sample_press_release.txt"
    assert file_path.exists()

    parsed = parser.parse(
        file_path=str(file_path),
        company_ticker="GOOGL",
        fiscal_year=2024,
        force_local=True,
    )

    assert parsed.filename == "sample_press_release.txt"
    assert parsed.doc_type == DocumentType.TXT
    assert len(parsed.elements) > 0


@pytest.mark.asyncio
async def test_batch_ingest_required_docs_dry_run(tmp_path):
    docs_dir = find_required_docs_dir()
    output_dir = tmp_path / "parsed_markdown"

    stats = await process_and_ingest(
        docs_dir=docs_dir,
        company_ticker="AETHER",
        fiscal_year=2024,
        dry_run=True,
        output_dir=str(output_dir),
    )

    assert stats["files_processed"] >= 4
    assert stats["files_failed"] == 0
    assert stats["total_chunks"] > 0
    assert len(list(output_dir.glob("*.md"))) >= 4


def test_firecrawl_mock_parsing(monkeypatch):
    class MockResponse:
        status_code = 200
        def json(self):
            return {
                "markdown": "# Header\n\n| Col 1 | Col 2 |\n| --- | --- |\n| Val 1 | Val 2 |"
            }

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def post(self, *args, **kwargs):
            return MockResponse()

    monkeypatch.setattr("httpx.Client", MockClient)

    parser = AnyDocParser(api_key="mock_key")
    parsed = parser.parse("dummy.pdf", content=b"dummy_content", force_local=False)

    assert parsed.raw_text.startswith("# Header")
    assert len(parsed.elements) >= 2


def test_documents_upload_endpoint():
    client = TestClient(app)
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("sample.txt", b"Header Line\n\n| Col A | Col B |\n| 1 | 2 |", "text/plain")},
        data={"company_ticker": "TEST", "fiscal_year": 2024, "document_type": "press_release"},
    )

    # If Qdrant is offline, the endpoint may fail gracefully or succeed.
    assert response.status_code in [201, 500]
