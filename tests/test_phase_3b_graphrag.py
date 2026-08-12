import pytest
from pydantic import BaseModel
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.api.routers.graph import get_neo4j_db_driver
from backend.db.neo4j import get_neo4j_driver, bulk_write_nodes_and_relationships
from backend.rag.graphrag import (
    CommunityDetector,
    rrf_score_fusion,
    traverse_2hop_graph,
    FinancialGraphRAG,
)

client = TestClient(app)


class MockPassage(BaseModel):
    chunk_id: str
    text: str
    score: float = 0.0


@pytest.mark.asyncio
async def test_community_detector_louvain():
    driver = get_neo4j_driver("memory")
    nodes = [
        {"id": "comp_1", "name": "Alpha Corp", "label": "Company"},
        {"id": "comp_2", "name": "Beta Inc", "label": "Company"},
    ]
    await bulk_write_nodes_and_relationships(nodes, [], driver=driver)

    summaries = await CommunityDetector.run_louvain_communities(driver)
    assert len(summaries) > 0
    assert summaries[0].level == 1
    assert "comp_1" in summaries[0].entity_ids


def test_rrf_score_fusion():
    vector_results = [
        MockPassage(chunk_id="doc_1", text="Vector match 1", score=0.9),
        MockPassage(chunk_id="doc_2", text="Vector match 2", score=0.8),
    ]
    graph_results = [
        MockPassage(chunk_id="doc_2", text="Vector match 2", score=1.0),
        MockPassage(chunk_id="doc_3", text="Graph match 3", score=1.0),
    ]

    fused = rrf_score_fusion(vector_results, graph_results, k=60.0)
    assert len(fused) == 3
    # doc_2 appears in both vector and graph results, so its RRF rank should be highest
    assert fused[0].chunk_id == "doc_2"
    assert fused[0].score > fused[1].score


@pytest.mark.asyncio
async def test_traverse_2hop_graph_and_financial_query():
    driver = get_neo4j_driver("memory")
    nodes = [
        {"id": "comp_aapl", "name": "Apple Inc.", "label": "Company"},
        {"id": "comp_beats", "name": "Beats Electronics", "label": "Company"},
    ]
    rels = [
        {"source_id": "comp_aapl", "target_id": "comp_beats", "rel_type": "ACQUIRED"}
    ]
    await bulk_write_nodes_and_relationships(nodes, rels, driver=driver)

    graph_data = await traverse_2hop_graph(driver, entity_name="Apple Inc.")
    assert len(graph_data["nodes"]) == 2
    assert len(graph_data["links"]) == 1
    assert graph_data["links"][0]["type"] == "ACQUIRED"

    financial_rag = FinancialGraphRAG(neo4j_driver=driver)
    passages = await financial_rag.query_hybrid_rrf("Apple Inc.", top_k=2)
    assert len(passages) > 0


def test_graph_explore_rest_endpoint():
    # Override Neo4j driver with in-memory driver for testing
    mem_driver = get_neo4j_driver("memory")
    nodes = [
        {"id": "c1", "name": "Company A", "label": "Company"},
        {"id": "c2", "name": "Company B", "label": "Company"},
    ]
    rels = [{"source_id": "c1", "target_id": "c2", "rel_type": "COMPETES_WITH"}]

    # Write into memory driver
    import asyncio

    asyncio.run(bulk_write_nodes_and_relationships(nodes, rels, driver=mem_driver))

    app.dependency_overrides[get_neo4j_db_driver] = lambda: mem_driver
    try:
        response = client.post(
            "/api/v1/graph/explore", json={"entity_name": "Company A", "limit": 10}
        )
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "links" in data
        assert len(data["nodes"]) == 2
        assert len(data["links"]) == 1
        assert data["links"][0]["type"] == "COMPETES_WITH"
    finally:
        app.dependency_overrides.clear()
