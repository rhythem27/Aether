import pytest
import io
from qdrant_client import AsyncQdrantClient
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.api.dependencies import get_qdrant_db_client
from backend.db.qdrant import init_qdrant_collection
from backend.rag.chunking import DocumentChunk, ChunkMetadata
from backend.rag.retriever import HybridRetriever

client = TestClient(app)

@pytest.fixture(autouse=True)
def mock_qdrant_dependency():
    test_q_client = AsyncQdrantClient(":memory:")
    app.dependency_overrides[get_qdrant_db_client] = lambda: test_q_client
    yield test_q_client
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_qdrant_collection_initialization(mock_qdrant_dependency):
    q_client = mock_qdrant_dependency
    await init_qdrant_collection(client=q_client, collection_name="test_financial")
    
    collections_resp = await q_client.get_collections()
    names = [c.name for c in collections_resp.collections]
    assert "test_financial" in names

@pytest.mark.asyncio
async def test_hybrid_retriever_upsert_and_search(mock_qdrant_dependency):
    q_client = mock_qdrant_dependency
    await init_qdrant_collection(client=q_client, collection_name="test_hybrid")
    
    retriever = HybridRetriever(qdrant_client=q_client)
    
    chunks = [
        DocumentChunk(
            chunk_id="chunk_aapl_1",
            text="Apple Inc. reported fiscal Q3 2025 revenue of $85.8 billion with strong iPhone sales.",
            token_count=15,
            metadata=ChunkMetadata(
                source_file="aapl_10q.txt",
                page_number=1,
                section_heading="Financial Performance",
                company_ticker="AAPL",
                company_name="Apple Inc.",
                fiscal_year=2025,
                document_type="10-Q"
            )
        ),
        DocumentChunk(
            chunk_id="chunk_tsla_1",
            text="Tesla Motors automotive gross margin was 18.5% in Q2 2025.",
            token_count=12,
            metadata=ChunkMetadata(
                source_file="tsla_10q.txt",
                page_number=2,
                section_heading="Margins",
                company_ticker="TSLA",
                company_name="Tesla Motors",
                fiscal_year=2025,
                document_type="10-Q"
            )
        )
    ]
    
    count = await retriever.upsert_chunks(chunks, collection_name="test_hybrid")
    assert count == 2
    
    # Unfiltered Search
    passages = await retriever.search(
        query="iPhone sales revenue",
        top_k=2,
        collection_name="test_hybrid"
    )
    assert len(passages) > 0
    assert passages[0].company_ticker == "AAPL"
    
    # Filtered Search by company_ticker
    filtered_passages = await retriever.search(
        query="margin",
        top_k=2,
        company_ticker="TSLA",
        collection_name="test_hybrid"
    )
    assert len(filtered_passages) == 1
    assert filtered_passages[0].company_ticker == "TSLA"

def test_rest_document_upload_and_query():
    file_content = b"""# Quarterly Report
Company Ticker: NVDA
NVIDIA announced record AI GPU revenue driven by Hopper and Blackwell architecture.
Net income reached $14.8 billion.
"""
    files = {
        "file": ("nvda_report.txt", io.BytesIO(file_content), "text/plain")
    }
    data = {
        "company_ticker": "NVDA",
        "company_name": "NVIDIA Corp",
        "fiscal_year": "2025",
        "document_type": "10-Q"
    }
    
    # Test Upload Endpoint
    upload_resp = client.post("/api/v1/documents/upload", files=files, data=data)
    assert upload_resp.status_code == 201
    upload_data = upload_resp.json()
    assert upload_data["filename"] == "nvda_report.txt"
    assert upload_data["company_ticker"] == "NVDA"
    assert upload_data["total_chunks"] > 0
    
    # Test Query Endpoint
    query_payload = {
        "query": "GPU revenue Blackwell",
        "top_k": 3,
        "company_ticker": "NVDA"
    }
    query_resp = client.post("/api/v1/documents/query", json=query_payload)
    assert query_resp.status_code == 200
    query_data = query_resp.json()
    assert query_data["query"] == "GPU revenue Blackwell"
    assert "total_results" in query_data
    assert query_data["total_results"] > 0
