import pytest
from backend.db.neo4j import (
    get_neo4j_driver,
    init_neo4j_schema,
    bulk_write_nodes_and_relationships,
)
from backend.rag.graphrag import (
    EntityResolver,
    FinancialGraphRAG,
    EntityType,
    RelationType,
    EntityNode,
    RelationshipTriple,
    ExtractedGraphData,
)


@pytest.mark.asyncio
async def test_neo4j_schema_and_in_memory_driver():
    driver = get_neo4j_driver("memory")
    await init_neo4j_schema(driver)

    nodes = [
        {
            "id": "company_apple_inc",
            "name": "Apple Inc.",
            "label": "Company",
            "properties": {"ticker": "AAPL"},
        },
        {
            "id": "company_beats",
            "name": "Beats Electronics",
            "label": "Company",
            "properties": {},
        },
    ]
    relationships = [
        {
            "source_id": "company_apple_inc",
            "target_id": "company_beats",
            "rel_type": "ACQUIRED",
            "properties": {"year": 2014},
        }
    ]

    written = await bulk_write_nodes_and_relationships(
        nodes, relationships, driver=driver
    )
    assert written == 3
    assert len(driver.db["nodes"]) == 2
    assert len(driver.db["relationships"]) == 1


def test_entity_resolver_canonicalization_and_deduplication():
    # Test Ticker Canonicalization
    assert EntityResolver.canonicalize_name("AAPL") == "Apple Inc."
    assert EntityResolver.canonicalize_name("MSFT") == "Microsoft Corporation"
    assert EntityResolver.canonicalize_name("Apple Inc.") == "Apple Inc."

    raw_data = ExtractedGraphData(
        nodes=[
            EntityNode(id="c1", name="Apple Inc.", label=EntityType.COMPANY),
            EntityNode(
                id="c2",
                name="AAPL",
                label=EntityType.COMPANY,
                properties={"sector": "Tech"},
            ),
            EntityNode(id="c3", name="Tesla Inc.", label=EntityType.COMPANY),
        ],
        relationships=[
            RelationshipTriple(
                source_id="company_apple",
                target_id="company_tesla",
                rel_type=RelationType.COMPETES_WITH,
            ),
            RelationshipTriple(
                source_id="company_apple",
                target_id="company_tesla",
                rel_type=RelationType.COMPETES_WITH,
            ),  # Duplicate
        ],
    )

    resolved = EntityResolver.resolve_and_deduplicate(raw_data)
    # AAPL and Apple Inc. resolve to the same canonical ID
    assert len(resolved.nodes) == 2
    assert len(resolved.relationships) == 1

    aapl_node = next(n for n in resolved.nodes if "apple" in n.id)
    assert aapl_node.properties.get("sector") == "Tech"


@pytest.mark.asyncio
async def test_financial_graphrag_extraction_and_indexing():
    driver = get_neo4j_driver("memory")
    graphrag = FinancialGraphRAG(neo4j_driver=driver)

    sample_text = """
    Sequoia Capital invested in OpenAI during the early funding rounds.
    Microsoft Corporation acquired GitHub for $7.5 billion in stock.
    Apple Inc. competes with Samsung Electronics in the smartphone market.
    """

    extracted = await graphrag.index_document_graph(sample_text)
    assert len(extracted.nodes) > 0
    assert len(extracted.relationships) > 0

    rel_types = [r.rel_type for r in extracted.relationships]
    assert (
        RelationType.INVESTED_IN in rel_types
        or RelationType.ACQUIRED in rel_types
        or RelationType.COMPETES_WITH in rel_types
    )
    assert len(driver.db["nodes"]) > 0
