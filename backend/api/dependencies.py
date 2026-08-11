from qdrant_client import AsyncQdrantClient
from backend.db.qdrant import get_qdrant_client

async def get_qdrant_db_client() -> AsyncQdrantClient:
    return get_qdrant_client()
