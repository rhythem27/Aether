from typing import Optional
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    HnswConfigDiff,
    PayloadSchemaType,
)
from backend.core.config import settings
from backend.core.logging import logger

FINANCIAL_COLLECTION_NAME = "financial_intelligence"
_qdrant_client: Optional[AsyncQdrantClient] = None


def get_qdrant_client(url: Optional[str] = None) -> AsyncQdrantClient:
    global _qdrant_client
    if url is not None:
        return AsyncQdrantClient(url=url)
    if _qdrant_client is None:
        _qdrant_client = AsyncQdrantClient(url=settings.QDRANT_URL)
    return _qdrant_client


async def init_qdrant_collection(
    client: Optional[AsyncQdrantClient] = None,
    collection_name: str = FINANCIAL_COLLECTION_NAME,
):
    """Ensure the Qdrant financial_intelligence collection exists with HNSW and payload indexes."""
    q_client = client or get_qdrant_client()
    try:
        collections_resp = await q_client.get_collections()
        existing_names = [c.name for c in collections_resp.collections]

        if collection_name not in existing_names:
            logger.info("creating_qdrant_collection", collection=collection_name)
            await q_client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
                hnsw_config=HnswConfigDiff(m=16, ef_construct=200, on_disk=True),
                optimizers_config={"indexing_threshold": 10000},  # type: ignore[arg-type]
            )

            # Create payload indexes for fast filtered searches
            payload_fields = [
                ("text", PayloadSchemaType.TEXT),
                ("company_ticker", PayloadSchemaType.KEYWORD),
                ("document_type", PayloadSchemaType.KEYWORD),
                ("fiscal_year", PayloadSchemaType.INTEGER),
            ]
            for field_name, field_schema in payload_fields:
                try:
                    await q_client.create_payload_index(
                        collection_name=collection_name,
                        field_name=field_name,
                        field_schema=field_schema,
                    )
                except Exception as idx_err:
                    logger.warning(
                        "payload_index_creation_warn",
                        field=field_name,
                        error=str(idx_err),
                    )
        else:
            logger.info("qdrant_collection_exists", collection=collection_name)
    except Exception as e:
        logger.error(
            "qdrant_init_collection_failed", collection=collection_name, error=str(e)
        )
        raise


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
