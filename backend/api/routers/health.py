from fastapi import APIRouter, status
from pydantic import BaseModel
from backend.core.config import settings
from backend.db.qdrant import check_qdrant_health
from backend.db.neo4j import check_neo4j_health
from backend.db.postgres import check_postgres_health
from backend.db.redis import check_redis_health

router = APIRouter(tags=["health"])


class ServiceHealthStatus(BaseModel):
    status: str
    version: str
    services: dict


@router.get(
    "/health", response_model=ServiceHealthStatus, status_code=status.HTTP_200_OK
)
async def get_health_status():
    qdrant_ok = await check_qdrant_health()
    neo4j_ok = await check_neo4j_health()
    postgres_ok = await check_postgres_health()
    redis_ok = await check_redis_health()

    services_status = {
        "qdrant": "healthy" if qdrant_ok else "unhealthy",
        "neo4j": "healthy" if neo4j_ok else "unhealthy",
        "postgres": "healthy" if postgres_ok else "unhealthy",
        "redis": "healthy" if redis_ok else "unhealthy",
    }

    all_healthy = all(status == "healthy" for status in services_status.values())

    return ServiceHealthStatus(
        status="healthy" if all_healthy else "degraded",
        version=settings.VERSION,
        services=services_status,
    )


@router.get("/ready", status_code=status.HTTP_200_OK)
async def readiness_probe():
    return {"status": "ready"}
