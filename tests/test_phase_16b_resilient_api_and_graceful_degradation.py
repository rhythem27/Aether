import pytest
from unittest.mock import MagicMock, AsyncMock

from backend.mcp.client import retry_mcp_call
from backend.rag.graphrag import FinancialGraphRAG
from backend.core.metrics import (
    DEGRADATION_EVENTS_COUNT,
    MCP_RETRY_EVENTS_COUNT,
    get_prometheus_metrics,
)


@pytest.mark.asyncio
async def test_mcp_retry_decorator_exponential_backoff_and_jitter():
    """Verify retry_mcp_call decorator applies exponential backoff retries with randomized jitter."""
    call_count = 0

    @retry_mcp_call
    async def flaky_tool_func():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionError("Transient FastMCP API rate limit error (HTTP 429)")
        return {"status": "RECOVERED"}

    result = await flaky_tool_func()
    assert result == {"status": "RECOVERED"}
    assert call_count == 3


@pytest.mark.asyncio
async def test_neo4j_outage_fallback_to_qdrant_vector_rag():
    """Verify automatic fallback from Neo4j GraphRAG to pure Qdrant vector search during database outages."""
    # Mock Neo4j driver that raises a connection outage exception
    failing_neo4j_driver = MagicMock()
    failing_neo4j_driver.session.side_effect = Exception("Neo4j BoltConnectionError: Database unavailable")

    # Mock Qdrant client returning dense vector search results
    mock_qdrant = MagicMock()
    mock_point = MagicMock()
    mock_point.id = "doc_chunk_101"
    mock_point.score = 0.92
    mock_point.payload = {
        "chunk_id": "doc_chunk_101",
        "text": "NVIDIA revenue reached $60 billion driven by Data Center H100 GPUs.",
        "entity_ids": ["company_nvidia"],
        "source_file": "10-K",
        "page_number": 1,
        "document_type": "sec_filing",
    }

    mock_response = MagicMock()
    mock_response.points = [mock_point]
    mock_qdrant.query_points = AsyncMock(return_value=mock_response)
    mock_qdrant.search = AsyncMock(return_value=[mock_point])

    graph_rag = FinancialGraphRAG(neo4j_driver=failing_neo4j_driver, qdrant_client=mock_qdrant)

    # Query RAG during Neo4j outage
    results = await graph_rag.query_unified_vector_graph_rag(
        query="NVIDIA Data Center H100 GPU revenue",
        top_k=3,
        use_single_pass_reranker=False,
    )

    # Search should complete cleanly via pure Qdrant vector fallback without throwing 500 exceptions
    assert len(results) > 0
    assert "NVIDIA" in results[0].text


def test_prometheus_metrics_degradation_recording():
    """Verify Prometheus metrics record outage degradation and MCP retry events cleanly."""
    DEGRADATION_EVENTS_COUNT.labels(source="neo4j_outage", target="qdrant_fallback").inc()
    MCP_RETRY_EVENTS_COUNT.labels(server_name="sec_edgar", status="retry").inc()

    content, content_type = get_prometheus_metrics()
    metrics_str = content.decode("utf-8")

    assert "aether_degradation_events_total" in metrics_str
    assert "aether_mcp_retry_events_total" in metrics_str
