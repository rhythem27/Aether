import asyncio
import structlog

from backend.db.postgres import engine, Base
from backend.db.qdrant import init_qdrant_collection

logger = structlog.get_logger(__name__)


async def init_databases():
    """Initialize PostgreSQL database tables and Qdrant vector collections."""
    logger.info("initializing_databases")

    # 1. Create PostgreSQL tables
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("postgres_tables_initialized_successfully")
    except Exception as e:
        logger.warning("postgres_init_warning", error=str(e))

    # 2. Create Qdrant vector collections
    try:
        await init_qdrant_collection()
        logger.info("qdrant_collections_initialized_successfully")
    except Exception as e:
        logger.warning("qdrant_init_warning", error=str(e))

    logger.info("database_initialization_complete")


if __name__ == "__main__":
    asyncio.run(init_databases())

