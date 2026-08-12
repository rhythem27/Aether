import os
import json
import asyncio
from typing import Any, Callable, Dict, List, Optional
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
import structlog


logger = structlog.get_logger(__name__)


def retry_mcp_call(fn: Callable) -> Callable:
    """Decorator applying exponential backoff retries to MCP tool calls via Tenacity."""
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4.0),
        retry=retry_if_exception_type((TimeoutError, ConnectionError, Exception)),
        reraise=True,
    )(fn)


class MCPClientManager:
    """Central MCP Client Connection Manager for discovering, configuring, and invoking FastMCP tools."""

    def __init__(self, config_path: str = "mcp_config.json"):
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(
                    "mcp_config_load_failed", path=self.config_path, error=str(e)
                )

        # Default fallback server registry
        return {
            "mcpServers": {
                "sec_edgar": {
                    "command": "python",
                    "args": ["-m", "backend.mcp.servers.sec_edgar"],
                },
                "crunchbase": {
                    "command": "python",
                    "args": ["-m", "backend.mcp.servers.crunchbase"],
                },
                "newsapi": {
                    "command": "python",
                    "args": ["-m", "backend.mcp.servers.newsapi"],
                },
                "neo4j_graph": {
                    "command": "python",
                    "args": ["-m", "backend.mcp.servers.neo4j"],
                },
            }
        }

    def get_server_config(self, server_name: str) -> Optional[Dict[str, Any]]:
        return self.config.get("mcpServers", {}).get(server_name)

    async def execute_tool_with_retry(
        self, tool_func: Callable, *args: Any, **kwargs: Any
    ) -> Any:
        """Execute an MCP tool function wrapped with Tenacity retry logic."""

        @retry_mcp_call
        async def _call():
            if asyncio.iscoroutinefunction(tool_func):
                return await tool_func(*args, **kwargs)
            return tool_func(*args, **kwargs)

        return await _call()

    def get_tools_for_servers(
        self, server_names: Optional[List[str]] = None
    ) -> Dict[str, Callable]:
        """Aggregate available tools across specified FastMCP servers."""
        tools: Dict[str, Callable] = {}
        targets = server_names or list(self.config.get("mcpServers", {}).keys())

        if "sec_edgar" in targets:
            from backend.mcp.servers.sec_edgar import search_filings, extract_financials

            tools["search_filings"] = search_filings
            tools["extract_financials"] = extract_financials

        if "crunchbase" in targets:
            from backend.mcp.servers.crunchbase import (
                get_funding_rounds,
                get_investors,
                get_acquisition_history,
            )

            tools["get_funding_rounds"] = get_funding_rounds
            tools["get_investors"] = get_investors
            tools["get_acquisition_history"] = get_acquisition_history

        if "newsapi" in targets:
            from backend.mcp.servers.newsapi import (
                get_recent_news,
                analyze_news_sentiment,
            )

            tools["get_recent_news"] = get_recent_news
            tools["analyze_news_sentiment"] = analyze_news_sentiment

        if "neo4j_graph" in targets:
            from backend.mcp.servers.neo4j import (
                query_entity_subgraph,
                find_paths_between,
                execute_cypher,
            )

            tools["query_entity_subgraph"] = query_entity_subgraph
            tools["find_paths_between"] = find_paths_between
            tools["execute_cypher"] = execute_cypher

        return tools


# Global singleton client manager
mcp_client = MCPClientManager()
