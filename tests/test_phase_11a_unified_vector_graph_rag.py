import pytest
from qdrant_client import AsyncQdrantClient

from backend.db.neo4j import get_neo4j_driver, bulk_write_nodes_and_relationships
from backend.db.qdrant import init_qdrant_collection
from backend.rag.chunking import DocumentChunk, ChunkMetadata, TokenAwareChunker, ParsedDocument, DocumentElement, DocumentType
from backend.rag.graphrag import (
    FinancialGraphRAG,
    SinglePassLLMReranker,
    expand_subgraph_entity_ids,
    EntityExtractor,
)
from backend.rag.retriever import HybridRetriever, QueryResultPassage
from backend.agents.research import research_node


@pytest.mark.asyncio
async def test_universal_entity_key_mapping():
    driver = get_neo4j_driver("memory")

    nodes = [
        {"id": "company_apple_inc", "name": "Apple Inc.", "label": "Company"},
        {"id": "executive_tim_cook", "name": "Tim Cook", "label": "Executive"},
    ]
    relationships = [
        {
            "source_id": "executive_tim_cook",
            "target_id": "company_apple_inc",
            "rel_type": "EXECUTIVE_OF",
        }
    ]
    await bulk_write_nodes_and_relationships(nodes, relationships, driver=driver)

    chunker = TokenAwareChunker(max_tokens=256)
    doc = ParsedDocument(
        filename="apple_report.txt",
        doc_type=DocumentType.TXT,
        elements=[
            DocumentElement(
                element_type="text",
                text="Tim Cook is CEO of Apple Inc. Apple Inc. reported record revenue.",
            )
        ],
        raw_text="Tim Cook is CEO of Apple Inc. Apple Inc. reported record revenue.",
    )

    chunks = chunker.chunk_document(doc, company_ticker="AAPL")
    assert len(chunks) > 0
    chunk_eids = chunks[0].metadata.entity_ids
    assert "company_aapl" in chunk_eids or "company_apple_inc" in chunk_eids


@pytest.mark.asyncio
async def test_subgraph_expansion_and_qdrant_payload_filtering():
    driver = get_neo4j_driver("memory")

    # Construct 2-hop graph: Apple Inc -> Tim Cook -> Board Member
    nodes = [
        {"id": "company_apple_inc", "name": "Apple Inc.", "label": "Company"},
        {"id": "executive_tim_cook", "name": "Tim Cook", "label": "Executive"},
        {"id": "person_board_member", "name": "Board Member", "label": "Person"},
    ]
    relationships = [
        {
            "source_id": "company_apple_inc",
            "target_id": "executive_tim_cook",
            "rel_type": "HAS_EXECUTIVE",
        },
        {
            "source_id": "executive_tim_cook",
            "target_id": "person_board_member",
            "rel_type": "MEETS_WITH",
        },
    ]
    await bulk_write_nodes_and_relationships(nodes, relationships, driver=driver)

    # Expand 2-hops from seed "company_apple_inc"
    expanded_eids = await expand_subgraph_entity_ids(
        driver=driver, seed_entity_ids=["company_apple_inc"], max_hops=2
    )

    assert "company_apple_inc" in expanded_eids
    assert "executive_tim_cook" in expanded_eids
    assert "person_board_member" in expanded_eids

    # Setup in-memory Qdrant
    q_client = AsyncQdrantClient(":memory:")
    await init_qdrant_collection(client=q_client, collection_name="test_phase_11a")
    retriever = HybridRetriever(qdrant_client=q_client)

    chunks = [
        DocumentChunk(
            chunk_id="chunk_apple_1",
            text="Apple Inc. revenue reached record levels.",
            token_count=10,
            metadata=ChunkMetadata(
                source_file="apple.txt",
                company_ticker="AAPL",
                entity_ids=["company_apple_inc"],
            ),
        ),
        DocumentChunk(
            chunk_id="chunk_other_1",
            text="Unrelated tech company disclosure.",
            token_count=10,
            metadata=ChunkMetadata(
                source_file="other.txt",
                company_ticker="OTHER",
                entity_ids=["company_other_corp"],
            ),
        ),
    ]

    await retriever.upsert_chunks(chunks, collection_name="test_phase_11a")

    # Perform search filtered strictly by 2-hop expanded entity IDs
    results = await retriever.search(
        query="revenue",
        top_k=5,
        entity_ids=expanded_eids,
        collection_name="test_phase_11a",
    )

    assert len(results) == 1
    assert results[0].chunk_id == "chunk_apple_1"
    assert "company_apple_inc" in results[0].entity_ids


@pytest.mark.asyncio
async def test_single_pass_llm_reranker():
    reranker = SinglePassLLMReranker()

    vector_passages = [
        QueryResultPassage(
            chunk_id="c1",
            text="Apple Inc. announced revenue growth.",
            score=0.7,
            source_file="apple.pdf",
            page_number=1,
            document_type="10-K",
            entity_ids=["company_apple_inc"],
        ),
        QueryResultPassage(
            chunk_id="c2",
            text="General market analysis text.",
            score=0.8,
            source_file="market.pdf",
            page_number=1,
            document_type="report",
            entity_ids=["market_general"],
        ),
    ]

    graph_context = {
        "nodes": [
            {"id": "company_apple_inc", "name": "Apple Inc."},
        ],
        "links": [
            {"source": "company_apple_inc", "target": "executive_tim_cook", "type": "HAS_CEO"},
        ],
    }

    reranked = await reranker.rerank(
        query="Apple revenue",
        vector_passages=vector_passages,
        graph_context=graph_context,
        top_k=2,
    )

    assert len(reranked) == 2
    # c1 should get an alignment boost from matching graph context entity "company_apple_inc"
    assert reranked[0].chunk_id == "c1"


@pytest.mark.asyncio
async def test_unified_vector_graph_rag_query():
    driver = get_neo4j_driver("memory")
    q_client = AsyncQdrantClient(":memory:")
    await init_qdrant_collection(client=q_client, collection_name="test_unified")

    graph_rag = FinancialGraphRAG(neo4j_driver=driver, qdrant_client=q_client)

    sample_text = "Tesla Inc. acquired SolarCity and reported high battery production revenue."
    await graph_rag.index_document_graph(sample_text)

    # Index vector chunks into Qdrant
    retriever = HybridRetriever(qdrant_client=q_client)
    await retriever.upsert_chunks(
        [
            DocumentChunk(
                chunk_id="chunk_tsla",
                text=sample_text,
                token_count=12,
                metadata=ChunkMetadata(
                    source_file="tsla.txt",
                    company_ticker="TSLA",
                    entity_ids=["company_tesla_inc"],
                ),
            )
        ],
        collection_name="test_unified",
    )

    results = await graph_rag.query_unified_vector_graph_rag(
        query="Tesla revenue",
        seed_entities=["company_tesla_inc"],
        top_k=3,
        use_single_pass_reranker=True,
        collection_name="test_unified",
    )

    assert len(results) > 0


@pytest.mark.asyncio
async def test_research_agent_integration():
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
