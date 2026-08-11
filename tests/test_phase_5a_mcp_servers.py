import pytest

from backend.mcp.servers.crunchbase import get_funding_rounds, get_investors, get_acquisition_history
from backend.mcp.servers.newsapi import get_recent_news, analyze_news_sentiment
from backend.mcp.servers.neo4j import query_entity_subgraph, find_paths_between, execute_cypher

@pytest.mark.asyncio
async def test_crunchbase_mcp_tools():
    rounds = await get_funding_rounds("apple-inc")
    assert isinstance(rounds, list)
    assert len(rounds) > 0
    assert "round_name" in rounds[0]

    investors = await get_investors("apple-inc")
    assert isinstance(investors, list)
    assert len(investors) > 0
    assert "investor_name" in investors[0]

    acquisitions = await get_acquisition_history("apple-inc")
    assert isinstance(acquisitions, list)
    assert len(acquisitions) > 0
    assert "acquiree_name" in acquisitions[0]

@pytest.mark.asyncio
async def test_newsapi_mcp_tools():
    articles = await get_recent_news("NVIDIA", limit=2)
    assert isinstance(articles, list)
    assert len(articles) <= 2
    assert "title" in articles[0]

    sentiment_res = await analyze_news_sentiment(articles)
    assert "aggregate_score" in sentiment_res
    assert "sentiment" in sentiment_res
    assert sentiment_res["sentiment"] in ["BULLISH", "BEARISH", "NEUTRAL"]

@pytest.mark.asyncio
async def test_neo4j_mcp_tools():
    subgraph = await query_entity_subgraph("Apple Inc.")
    assert "nodes" in subgraph
    assert "links" in subgraph

    paths = await find_paths_between("Apple Inc.", "Beats Electronics")
    assert isinstance(paths, list)

    cypher_res = await execute_cypher("MATCH (n) RETURN n LIMIT 5")
    assert isinstance(cypher_res, list)

    # Test safety checks on write queries
    with pytest.raises(ValueError, match="Forbidden write operation"):
        await execute_cypher("MATCH (n) DELETE n")
