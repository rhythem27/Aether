import pytest
import os
import tempfile
from backend.rag.chunking import DocumentParser, TokenAwareChunker, DocumentType
from backend.rag.embeddings import EmbeddingService

@pytest.fixture
def parser():
    return DocumentParser()

@pytest.fixture
def chunker():
    return TokenAwareChunker(max_tokens=100, overlap=10)

@pytest.fixture
def embedding_service():
    return EmbeddingService()

def test_detect_format(parser):
    assert parser.detect_format("doc.pdf") == DocumentType.PDF
    assert parser.detect_format("page.html") == DocumentType.HTML
    assert parser.detect_format("report.docx") == DocumentType.DOCX
    assert parser.detect_format("notes.txt") == DocumentType.TXT
    assert parser.detect_format("unknown.xyz") == DocumentType.UNKNOWN

def test_parse_text_file(parser):
    sample_text = """# Section 1: Financial Highlights
Company revenue grew 25% year-over-year.

# Section 2: Balance Sheet
Revenue | Expenses | Net Profit
$100M   | $70M     | $30M
"""
    with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as f:
        f.write(sample_text)
        temp_path = f.name

    try:
        doc = parser.parse(temp_path)
        assert doc.doc_type == DocumentType.TXT
        assert len(doc.elements) > 0
        has_table = any(e.element_type == "table" for e in doc.elements)
        assert has_table
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

def test_chunking_and_table_metadata(parser, chunker):
    sample_text = """# Income Statement
Total Revenue | Cost of Revenue | Gross Profit
$500,000      | $300,000        | $200,000

The company operated at a 40% gross margin in Q3. Operating expenses were kept low through efficient operations.
"""
    doc = parser.parse("sample_income_statement.txt", content=sample_text.encode("utf-8"))
    chunks = chunker.chunk_document(
        doc,
        company_ticker="AAPL",
        company_name="Apple Inc.",
        fiscal_year=2025,
        document_type="10-Q"
    )

    assert len(chunks) > 0
    first_chunk = chunks[0]
    assert first_chunk.metadata.company_ticker == "AAPL"
    assert first_chunk.metadata.company_name == "Apple Inc."
    assert first_chunk.metadata.fiscal_year == 2025
    assert first_chunk.metadata.document_type == "10-Q"
    assert first_chunk.metadata.has_tables is True
    assert len(first_chunk.metadata.tables_json) > 0

@pytest.mark.asyncio
async def test_embedding_service_vectors(embedding_service):
    texts = [
        "Apple Inc. reported fiscal Q3 revenue of $85.8 billion.",
        "Tesla Motors delivered 443,956 vehicles in Q2."
    ]
    vectors = await embedding_service.embed_documents(texts)
    assert len(vectors) == 2
    assert len(vectors[0]) == 1024
    assert len(vectors[1]) == 1024

    query_vec = await embedding_service.embed_query("What was Apple's quarterly revenue?")
    assert len(query_vec) == 1024
