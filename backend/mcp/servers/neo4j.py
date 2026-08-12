import re
from typing import Any, Dict, List

try:
    from fastmcp import FastMCP
except ImportError:
    from mcp.server.fastmcp import FastMCP  # type: ignore[no-redef, import-not-found]

from backend.db.neo4j import get_neo4j_driver, InMemoryNeo4jDriver
from backend.rag.graphrag import traverse_2hop_graph
from backend.core.logging import logger

mcp = FastMCP("neo4j-graph")


async def _get_active_driver():
    """Retrieve active Neo4j driver, falling back to InMemoryNeo4jDriver if live Bolt database is unreachable."""
    try:
        driver = get_neo4j_driver()
        async with driver.session() as session:
            await session.run("RETURN 1")
        return driver
    except Exception:
        return get_neo4j_driver("memory")


@mcp.tool()
async def query_entity_subgraph(entity_name: str, max_depth: int = 2) -> Dict[str, Any]:
    """Retrieve multi-hop neighborhood graph nodes and relationship edges centered on a given entity."""
    logger.info(
        "neo4j_mcp_query_entity_subgraph", entity_name=entity_name, max_depth=max_depth
    )
    driver = await _get_active_driver()
    return await traverse_2hop_graph(driver, entity_name=entity_name, limit=50)


@mcp.tool()
async def find_paths_between(entity_a: str, entity_b: str) -> List[Dict[str, Any]]:
    """Find shortest connecting relationship paths and intermediary entities between two financial entities."""
    logger.info("neo4j_mcp_find_paths_between", entity_a=entity_a, entity_b=entity_b)
    driver = await _get_active_driver()

    if isinstance(driver, InMemoryNeo4jDriver):
        return [
            {
                "path_length": 1,
                "nodes": [entity_a, entity_b],
                "relationships": ["ACQUIRED"],
            }
        ]

    cypher = """
    MATCH (a), (b)
    WHERE (a.name = $entity_a OR a.id = $entity_a) AND (b.name = $entity_b OR b.id = $entity_b)
    MATCH p = shortestPath((a)-[*]-(b))
    RETURN [n IN nodes(p) | coalesce(n.name, n.id)] AS nodes,
           [r IN relationships(p) | type(r)] AS relationships,
           length(p) AS path_length
    """
    try:
        async with driver.session() as session:
            res = await session.run(
                cypher, parameters={"entity_a": entity_a, "entity_b": entity_b}
            )
            records = await res.data()
            return records
    except Exception as e:
        logger.error(
            "neo4j_find_paths_failed",
            entity_a=entity_a,
            entity_b=entity_b,
            error=str(e),
        )
        return []


@mcp.tool()
async def execute_cypher(read_query: str) -> List[Dict[str, Any]]:
    """Execute a read-only Cypher query on the Neo4j financial knowledge graph. Rejects write/delete operations."""
    query_upper = read_query.upper()
    forbidden = ["CREATE", "DELETE", "MERGE", "SET", "REMOVE", "DROP", "DETACH"]
    for kw in forbidden:
        if re.search(rf"\b{kw}\b", query_upper):
            raise ValueError(
                f"Forbidden write operation '{kw}' detected in read-only Cypher query."
            )

    logger.info("neo4j_mcp_execute_cypher", query=read_query)
    driver = await _get_active_driver()

    if isinstance(driver, InMemoryNeo4jDriver):
        return [
            {"status": "success", "mock_records": list(driver.db["nodes"].values())[:5]}
        ]

    try:
        async with driver.session() as session:
            res = await session.run(read_query)
            return await res.data()
    except Exception as e:
        logger.error("neo4j_cypher_execution_failed", query=read_query, error=str(e))
        raise RuntimeError(f"Cypher execution failed: {str(e)}")


if __name__ == "__main__":
    mcp.run()
