from typing import Optional
from neo4j import AsyncGraphDatabase, AsyncDriver
from backend.core.config import settings
from backend.core.logging import logger

_neo4j_driver: Optional[AsyncDriver] = None

def get_neo4j_driver() -> AsyncDriver:
    global _neo4j_driver
    if _neo4j_driver is None:
        _neo4j_driver = AsyncGraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )
    return _neo4j_driver

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
