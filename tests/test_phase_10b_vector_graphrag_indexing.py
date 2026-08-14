import pytest
from backend.rag.graphrag import (
    EntityExtractor,
    EntityResolver,
    EntityType,
    RelationType,
    FinancialGraphRAG,
    rrf_score_fusion,
    GraphPassage,
)
from backend.rag.retriever import QueryResultPassage
from backend.scripts.ingest_required_docs import find_required_docs_dir, process_and_ingest
from backend.agents.research import research_node


def test_entity_extractor_financial_metrics_and_risks():
    extractor = EntityExtractor()
    sample_text = """
    Apple Inc. reported revenue of $90 billion in FY24.
    Apple Inc. competes with Microsoft Corporation.
    There is a risk of litigation and cybersecurity threats in 10-K filings.
    """
    extracted = extractor.extract_from_text(sample_text)

    labels = [n.label for n in extracted.nodes]
    rel_types = [r.rel_type for r in extracted.relationships]

    assert EntityType.COMPANY in labels
    assert EntityType.METRIC in labels or EntityType.RISK_FACTOR in labels or EntityType.FILING in labels
    assert RelationType.COMPETES_WITH in rel_types or RelationType.REPORTED_METRIC in rel_types


def test_rrf_score_fusion():
    v_passages = [
        QueryResultPassage(
            chunk_id="chunk_1",
            text="Revenue grew 15%",
            score=0.95,
            source_file="doc1.pdf",
            page_number=1,
            document_type="financial_statement",
        ),
        QueryResultPassage(
            chunk_id="chunk_2",
            text="Risk of supply chain disruption",
            score=0.88,
            source_file="doc1.pdf",
            page_number=2,
            document_type="financial_statement",
        ),
    ]

    g_passages = [
        GraphPassage(chunk_id="rel_apple_msft", text="Apple COMPETES_WITH Microsoft", score=1.0),
        GraphPassage(chunk_id="chunk_1", text="Revenue grew 15%", score=1.0),
    ]

    fused = rrf_score_fusion(v_passages, g_passages, k=60.0)
    assert len(fused) == 3
    # chunk_1 appeared in both lists, so it should have higher RRF score and rank first
    assert getattr(fused[0], "chunk_id") == "chunk_1"


@pytest.mark.asyncio
async def test_financial_graphrag_indexing():
    graph_rag = FinancialGraphRAG()
    text = "Tesla Inc. reported revenue of $25 billion and acquired SolarCity."
    extracted = await graph_rag.index_document_graph(text, source_id="test.pdf")

    assert len(extracted.nodes) > 0
    assert len(extracted.relationships) > 0

    fused = await graph_rag.query_hybrid_rrf("Tesla Inc.", top_k=3)
    assert isinstance(fused, list)


@pytest.mark.asyncio
async def test_ingest_required_docs_with_graphrag(tmp_path):
    docs_dir = find_required_docs_dir()
    out_dir = tmp_path / "md_out"

    stats = await process_and_ingest(
        docs_dir=docs_dir,
        company_ticker="AAPL",
        fiscal_year=2024,
        dry_run=True,
        output_dir=str(out_dir),
    )

    assert stats["files_processed"] >= 4
    assert stats["graph_nodes"] > 0
    assert stats["graph_relationships"] >= 0


@pytest.mark.asyncio
async def test_research_agent_knowledge_binding():
    state = {
        "company_ticker": "AAPL",
        "company_name": "Apple Inc.",
        "research_data": {},
        "errors": [],
    }

    result = await research_node(state)
    assert "research_data" in result
    r_data = result["research_data"]
    assert "retrieved_passages" in r_data
