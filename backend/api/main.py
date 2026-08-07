from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.core.config import settings
from backend.core.logging import setup_logging, logger
from backend.core.exceptions import AetherException, aether_exception_handler
from backend.api.routers.health import router as health_router
from backend.db.qdrant import close_qdrant_client
from backend.db.neo4j import close_neo4j_driver
from backend.db.redis import close_redis_client

setup_logging()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("starting_aether_platform", version=settings.VERSION, environment=settings.ENVIRONMENT)
    yield
    logger.info("shutting_down_aether_platform")
    await close_qdrant_client()
    await close_neo4j_driver()
    await close_redis_client()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(AetherException, aether_exception_handler)

app.include_router(health_router)
app.include_router(health_router, prefix=settings.API_V1_STR)

@app.get("/")
async def root():
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs_url": "/docs",
        "health_url": "/health"
    }
