import pytest
from unittest.mock import MagicMock

from backend.mcp.client import MCPClientManager, mcp_client, retry_mcp_call
from backend.agents.state import AgentState
from backend.agents.research import research_node

def test_mcp_client_config_loading():
    client = MCPClientManager("mcp_config.json")
    config = client.config
    assert "mcpServers" in config
    assert "sec_edgar" in config["mcpServers"]
    assert "crunchbase" in config["mcpServers"]
    assert "newsapi" in config["mcpServers"]
    assert "neo4j_graph" in config["mcpServers"]

def test_mcp_client_tool_aggregation():
    tools = mcp_client.get_tools_for_servers(["sec_edgar", "crunchbase", "newsapi", "neo4j_graph"])
    assert "search_filings" in tools
    assert "get_funding_rounds" in tools
    assert "get_recent_news" in tools
    assert "query_entity_subgraph" in tools

@pytest.mark.asyncio
async def test_execute_tool_with_retry_success():
    async def sample_tool(val: int):
        return val * 2

    res = await mcp_client.execute_tool_with_retry(sample_tool, 21)
    assert res == 42

@pytest.mark.asyncio
async def test_execute_tool_with_retry_flaky_recovery():
    attempts = 0

    async def flaky_tool():
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            raise TimeoutError("Transient MCP server connection timeout")
        return "SUCCESS"

    res = await mcp_client.execute_tool_with_retry(flaky_tool)
    assert res == "SUCCESS"
    assert attempts == 2

@pytest.mark.asyncio
async def test_research_agent_mcp_integration():
    state: AgentState = {
        "messages": [],
        "company_ticker": "NVDA",
        "company_name": "NVIDIA Corporation",
        "fiscal_year": 2025,
        "research_data": {},
        "analysis_results": {},
        "verified_claims": [],
        "graph_operations": [],
        "report_sections": {},
        "human_approval": True,
        "errors": [],
        "token_usage": {}
    }

    res = await research_node(state)
    assert "research_data" in res
    data = res["research_data"]
    assert data["ticker"] == "NVDA"
    assert "sec_filings" in data
    assert "funding_rounds" in data
    assert "recent_news" in data
    assert "news_sentiment" in data
