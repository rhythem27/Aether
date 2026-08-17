import pytest
from qdrant_client import AsyncQdrantClient

from backend.rag.taxonomy import FinancialTaxonomyEngine, get_financial_taxonomy
from backend.agents.query_expansion import expand_query, query_expansion_node
from backend.db.qdrant import init_qdrant_collection
from backend.rag.chunking import DocumentChunk, ChunkMetadata
from backend.rag.retriever import HybridRetriever


def test_financial_taxonomy_engine():
    engine = get_financial_taxonomy()

    capex_syns = engine.get_synonyms("capex")
    assert "capital expenditures" in capex_syns

    ebitda_syns = engine.get_synonyms("ebitda")
    assert any("earnings before interest" in s for s in ebitda_syns)

    exp_terms = engine.expand_term("revenue")
    assert "top line" in exp_terms or "gross sales" in exp_terms


def test_query_expansion_agent():
    res = expand_query("AAPL quarterly capex report")
    assert "capital expenditures" in res["expanded_query"]
    assert len(res["synonyms"]) > 0


@pytest.mark.asyncio
async def test_query_expansion_node():
    state = {
        "company_ticker": "AAPL",
        "errors": [],
    }

    res = await query_expansion_node(state)
    assert "query_expansion" in res
    assert "expanded_query" in res["query_expansion"]


@pytest.mark.asyncio
async def test_retriever_dual_path_synonym_expansion():
    q_client = AsyncQdrantClient(":memory:")
    await init_qdrant_collection(client=q_client, collection_name="test_taxonomy_expansion")
    retriever = HybridRetriever(qdrant_client=q_client)

    chunks = [
        DocumentChunk(
            chunk_id="chunk_capex_doc",
            text="Apple Inc. reported $10.5B in capital expenditures during Q4.",
            token_count=12,
            metadata=ChunkMetadata(
                source_file="apple_q4.pdf",
                company_ticker="AAPL",
            ),
        ),
    ]
    await retriever.upsert_chunks(chunks, collection_name="test_taxonomy_expansion")

    # Acronym query "capex" expanded with synonyms ["capital expenditures"]
    results = await retriever.search(
        query="capex",
        expanded_query="capex capital expenditures capital spending",
        synonyms=["capital expenditures"],
        top_k=1,
        collection_name="test_taxonomy_expansion",
    )

    assert len(results) == 1
    assert results[0].chunk_id == "chunk_capex_doc"
    assert results[0].score > 0.0
