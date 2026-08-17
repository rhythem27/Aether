import pytest
from qdrant_client import AsyncQdrantClient

from backend.db.neo4j import get_neo4j_driver, bulk_write_nodes_and_relationships
from backend.db.qdrant import init_qdrant_collection
from backend.rag.chunking import DocumentChunk, ChunkMetadata
from backend.rag.graphrag import (
    run_louvain_communities,
    run_pagerank_centrality,
    run_node2vec_embeddings,
    run_degree_assortativity,
)
from backend.rag.retriever import HybridRetriever
from backend.agents.macro_trends import macro_trends_node
from backend.agents.supervisor import create_supervisor_workflow


@pytest.mark.asyncio
async def test_gds_louvain_communities():
    driver = get_neo4j_driver("memory")

    nodes = [
        {"id": "company_apple_inc", "name": "Apple Inc.", "label": "Company"},
        {"id": "executive_tim_cook", "name": "Tim Cook", "label": "Executive"},
        {"id": "company_beats", "name": "Beats Electronics", "label": "Company"},
    ]
    relationships = [
        {"source_id": "executive_tim_cook", "target_id": "company_apple_inc", "rel_type": "EXECUTIVE_OF"},
        {"source_id": "company_apple_inc", "target_id": "company_beats", "rel_type": "ACQUIRED"},
    ]
    await bulk_write_nodes_and_relationships(nodes, relationships, driver=driver)

    communities = await run_louvain_communities(driver)
    assert len(communities) > 0
    assert "company_apple_inc" in communities[0].entity_ids


@pytest.mark.asyncio
async def test_gds_pagerank_centrality():
    driver = get_neo4j_driver("memory")

    nodes = [
        {"id": "company_apple_inc", "name": "Apple Inc.", "label": "Company"},
        {"id": "executive_tim_cook", "name": "Tim Cook", "label": "Executive"},
        {"id": "company_beats", "name": "Beats Electronics", "label": "Company"},
    ]
    relationships = [
        {"source_id": "executive_tim_cook", "target_id": "company_apple_inc", "rel_type": "EXECUTIVE_OF"},
        {"source_id": "company_beats", "target_id": "company_apple_inc", "rel_type": "ACQUIRED_BY"},
    ]
    await bulk_write_nodes_and_relationships(nodes, relationships, driver=driver)

    pr_scores = await run_pagerank_centrality(driver)
    assert len(pr_scores) == 3
    # Apple Inc. has degree 2 so it should have higher PageRank score than single-degree nodes
    assert pr_scores["company_apple_inc"] >= pr_scores["executive_tim_cook"]


@pytest.mark.asyncio
async def test_gds_node2vec_embeddings():
    driver = get_neo4j_driver("memory")

    nodes = [
        {"id": "company_nvidia", "name": "NVIDIA", "label": "Company"},
        {"id": "company_arm", "name": "Arm", "label": "Company"},
    ]
    relationships = [
        {"source_id": "company_nvidia", "target_id": "company_arm", "rel_type": "PARTNERED_WITH"},
    ]
    await bulk_write_nodes_and_relationships(nodes, relationships, driver=driver)

    embeds = await run_node2vec_embeddings(driver, dimensions=32)
    assert "company_nvidia" in embeds
    assert len(embeds["company_nvidia"]) == 32


@pytest.mark.asyncio
async def test_gds_degree_assortativity_and_consolidation():
    driver = get_neo4j_driver("memory")

    nodes = [
        {"id": "c1", "name": "Company 1", "label": "Company"},
        {"id": "c2", "name": "Company 2", "label": "Company"},
        {"id": "c3", "name": "Company 3", "label": "Company"},
    ]
    relationships = [
        {"source_id": "c1", "target_id": "c2", "rel_type": "ACQUIRED"},
        {"source_id": "c2", "target_id": "c3", "rel_type": "ACQUIRED"},
        {"source_id": "c3", "target_id": "c1", "rel_type": "MERGED_WITH"},
    ]
    await bulk_write_nodes_and_relationships(nodes, relationships, driver=driver)

    metrics = await run_degree_assortativity(driver)
    assert "assortativity_score" in metrics
    assert "edge_density" in metrics
    assert "is_consolidation_alert" in metrics
    assert metrics["total_nodes"] == 3


@pytest.mark.asyncio
async def test_pagerank_centrality_weighted_retrieval():
    q_client = AsyncQdrantClient(":memory:")
    await init_qdrant_collection(client=q_client, collection_name="test_pagerank_rerank")
    retriever = HybridRetriever(qdrant_client=q_client)

    chunks = [
        DocumentChunk(
            chunk_id="chunk_apple",
            text="Apple Inc. reported quarterly revenue of $90B.",
            token_count=10,
            metadata=ChunkMetadata(
                source_file="apple.pdf",
                entity_ids=["company_apple_inc"],
            ),
        ),
        DocumentChunk(
            chunk_id="chunk_small_supplier",
            text="Small component supplier reported quarterly revenue of $5M.",
            token_count=10,
            metadata=ChunkMetadata(
                source_file="supplier.pdf",
                entity_ids=["company_small_supplier"],
            ),
        ),
    ]
    await retriever.upsert_chunks(chunks, collection_name="test_pagerank_rerank")

    pr_weights = {
        "company_apple_inc": 0.95,
        "company_small_supplier": 0.10,
    }

    results = await retriever.search(
        query="quarterly revenue",
        top_k=2,
        pagerank_weights=pr_weights,
        collection_name="test_pagerank_rerank",
    )

    assert len(results) == 2
    # Apple Inc. chunk has higher PageRank score and should be ranked first
    assert results[0].chunk_id == "chunk_apple"
    assert results[0].pagerank_score == 0.95


@pytest.mark.asyncio
async def test_macro_trends_agent_worker():
    driver = get_neo4j_driver("memory")

    nodes = [
        {"id": "company_apple_inc", "name": "Apple Inc.", "label": "Company"},
        {"id": "executive_tim_cook", "name": "Tim Cook", "label": "Executive"},
    ]
    relationships = [
        {"source_id": "executive_tim_cook", "target_id": "company_apple_inc", "rel_type": "EXECUTIVE_OF"},
    ]
    await bulk_write_nodes_and_relationships(nodes, relationships, driver=driver)

    state = {
        "company_ticker": "AAPL",
        "company_name": "Apple Inc.",
        "neo4j_driver": driver,
        "errors": [],
    }

    res = await macro_trends_node(state)
    assert "macro_trends_data" in res
    m_data = res["macro_trends_data"]
    assert "communities" in m_data
    assert "top_central_entities" in m_data
    assert "market_consolidation_alert" in m_data


def test_supervisor_workflow_compilation():
    app = create_supervisor_workflow()
    assert app is not None
