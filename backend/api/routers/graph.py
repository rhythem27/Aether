from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from neo4j import AsyncDriver
import structlog

from backend.db.neo4j import get_neo4j_driver
from backend.rag.graphrag import traverse_2hop_graph

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/graph", tags=["graph"])


class GraphExploreRequest(BaseModel):
    entity_name: Optional[str] = None
    max_depth: int = 2
    limit: int = 50


class GraphExploreResponse(BaseModel):
    nodes: List[Dict[str, Any]]
    links: List[Dict[str, Any]]


async def get_neo4j_db_driver() -> AsyncDriver:
    return get_neo4j_driver()


@router.post("/explore", response_model=GraphExploreResponse)
async def explore_graph(
    request: GraphExploreRequest, driver: AsyncDriver = Depends(get_neo4j_db_driver)
):
    """Retrieve 2-hop neighborhood graph nodes and links formatted for D3/Cytoscape visualization."""
    logger.info("exploring_graph", entity_name=request.entity_name, limit=request.limit)

    try:
        graph_data = await traverse_2hop_graph(
            driver=driver, entity_name=request.entity_name, limit=request.limit
        )
        return GraphExploreResponse(
            nodes=graph_data.get("nodes", []), links=graph_data.get("links", [])
        )
    except Exception as e:
        logger.error(
            "graph_exploration_failed", entity_name=request.entity_name, error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Graph exploration failed: {str(e)}",
        )
