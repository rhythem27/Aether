from typing import Optional
from qdrant_client import AsyncQdrantClient
from backend.core.config import settings
from backend.core.logging import logger

_qdrant_client: Optional[AsyncQdrantClient] = None

def get_qdrant_client() -> AsyncQdrantClient:
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = AsyncQdrantClient(url=settings.QDRANT_URL)
    return _qdrant_client

async def close_qdrant_client():
    global _qdrant_client
    if _qdrant_client is not None:
        await _qdrant_client.close()
        _qdrant_client = None

async def check_qdrant_health() -> bool:
    try:
        client = get_qdrant_client()
        response = await client.get_collections()
        return response is not None
    except Exception as e:
        logger.error("qdrant_health_check_failed", error=str(e))
        return False
