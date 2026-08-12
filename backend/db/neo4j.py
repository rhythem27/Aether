from typing import Any, Dict, List, Optional
from neo4j import AsyncGraphDatabase, AsyncDriver
from backend.core.config import settings
from backend.core.logging import logger

_neo4j_driver: Optional[AsyncDriver] = None


class InMemorySession:
    """Mock Neo4j session for offline unit testing."""

    def __init__(self, db_store: Dict[str, Any]):
        self.db = db_store

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def run(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> Any:
        params = parameters or {}
        # Support basic schema queries and UNWIND inserts
        if "MERGE" in query or "CREATE" in query:
            if "nodes" in params:
                for node in params["nodes"]:
                    node_id = node.get("id")
                    label = node.get("label", "Entity")
                    self.db["nodes"][node_id] = {
                        "label": label,
                        "properties": node.get("properties", {}),
                    }
            if "relationships" in params:
                for rel in params["relationships"]:
                    self.db["relationships"].append(rel)

        class Record:
            def __getitem__(self, key):
                if key == "result":
                    return 1
                return None

        class Result:
            async def single(self):
                return Record()

            async def data(self):
                return []

        return Result()


class InMemoryNeo4jDriver:
    """In-memory Neo4j driver mock for testing environments without active Neo4j container."""

    def __init__(self):
        self.db = {"nodes": {}, "relationships": []}

    def session(self):
        return InMemorySession(self.db)

    async def close(self):
        pass


def get_neo4j_driver(uri: Optional[str] = None) -> AsyncDriver:
    global _neo4j_driver
    if uri is not None and uri == "memory":
        return InMemoryNeo4jDriver()  # type: ignore[return-value]
    if _neo4j_driver is None:
        _neo4j_driver = AsyncGraphDatabase.driver(
            settings.NEO4J_URI, auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )
    return _neo4j_driver


async def init_neo4j_schema(driver: Optional[AsyncDriver] = None):
    """Initialize Neo4j Cypher unique constraints and vector indexes for financial entities."""
    d = driver or get_neo4j_driver()
    if isinstance(d, InMemoryNeo4jDriver):
        logger.info("in_memory_neo4j_schema_initialized")
        return

    constraints = [
        "CREATE CONSTRAINT company_id_unique IF NOT EXISTS FOR (c:Company) REQUIRE c.id IS UNIQUE",
        "CREATE CONSTRAINT company_name_unique IF NOT EXISTS FOR (c:Company) REQUIRE c.name IS UNIQUE",
        "CREATE CONSTRAINT person_id_unique IF NOT EXISTS FOR (p:Person) REQUIRE p.id IS UNIQUE",
        "CREATE CONSTRAINT investor_id_unique IF NOT EXISTS FOR (i:Investor) REQUIRE i.id IS UNIQUE",
        "CREATE CONSTRAINT sector_name_unique IF NOT EXISTS FOR (s:Sector) REQUIRE s.name IS UNIQUE",
        "CREATE CONSTRAINT filing_id_unique IF NOT EXISTS FOR (f:Filing) REQUIRE f.id IS UNIQUE",
        "CREATE CONSTRAINT lawsuit_id_unique IF NOT EXISTS FOR (l:Lawsuit) REQUIRE l.id IS UNIQUE",
    ]

    indexes = [
        "CREATE INDEX company_name_idx IF NOT EXISTS FOR (c:Company) ON (c.name)",
        "CREATE INDEX filing_ticker_idx IF NOT EXISTS FOR (f:Filing) ON (f.ticker)",
    ]

    try:
        async with d.session() as session:
            for constraint in constraints:
                try:
                    await session.run(constraint)
                except Exception as c_err:
                    logger.warning(
                        "cypher_constraint_creation_warn",
                        query=constraint,
                        error=str(c_err),
                    )

            for index in indexes:
                try:
                    await session.run(index)
                except Exception as i_err:
                    logger.warning(
                        "cypher_index_creation_warn", query=index, error=str(i_err)
                    )

        logger.info("neo4j_schema_initialized_successfully")
    except Exception as e:
        logger.error("neo4j_schema_init_failed", error=str(e))
        raise


async def bulk_write_nodes_and_relationships(
    nodes: List[Dict[str, Any]],
    relationships: List[Dict[str, Any]],
    driver: Optional[AsyncDriver] = None,
) -> int:
    """Async transactional Cypher bulk batch writer using UNWIND parameterization."""
    if not nodes and not relationships:
        return 0

    d = driver or get_neo4j_driver()

    # Process nodes grouped by label to maintain clean Cypher syntax
    nodes_by_label: Dict[str, List[Dict[str, Any]]] = {}
    for node in nodes:
        label = node.get("label", "Company")
        nodes_by_label.setdefault(label, []).append(node)

    written_count = 0

    async with d.session() as session:
        # Upsert nodes in batch per label
        for label, label_nodes in nodes_by_label.items():
            cypher_nodes_query = f"""
            UNWIND $nodes AS node
            MERGE (n:`{label}` {{id: node.id}})
            SET n += node.properties, n.name = node.name
            """
            try:
                await session.run(cypher_nodes_query, parameters={"nodes": label_nodes})
                written_count += len(label_nodes)
            except Exception as e:
                logger.error("neo4j_bulk_nodes_write_failed", label=label, error=str(e))
                raise

        # Upsert relationships in batch
        if relationships:
            rel_by_type: Dict[str, List[Dict[str, Any]]] = {}
            for rel in relationships:
                rel_type = rel.get("rel_type", "RELATED_TO")
                rel_by_type.setdefault(rel_type, []).append(rel)

            for rel_type, type_rels in rel_by_type.items():
                cypher_rel_query = f"""
                UNWIND $relationships AS rel
                MATCH (source {{id: rel.source_id}})
                MATCH (target {{id: rel.target_id}})
                MERGE (source)-[r:`{rel_type}`]->(target)
                SET r += rel.properties
                """
                try:
                    await session.run(
                        cypher_rel_query, parameters={"relationships": type_rels}
                    )
                    written_count += len(type_rels)
                except Exception as e:
                    logger.error(
                        "neo4j_bulk_rel_write_failed", rel_type=rel_type, error=str(e)
                    )
                    raise

    logger.info("neo4j_bulk_write_complete", total_elements=written_count)
    return written_count


async def close_neo4j_driver():
    global _neo4j_driver
    if _neo4j_driver is not None:
        await _neo4j_driver.close()
        _neo4j_driver = None


async def check_neo4j_health() -> bool:
    try:
        driver = get_neo4j_driver()
        async with driver.session() as session:
            result = await session.run("RETURN 1 AS result")
            record = await result.single()
            return record is not None and record["result"] == 1
    except Exception as e:
        logger.error("neo4j_health_check_failed", error=str(e))
        return False
