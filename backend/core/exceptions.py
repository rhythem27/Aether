from typing import Any, Dict, Optional
from fastapi import Request, status
from fastapi.responses import JSONResponse
import structlog

logger = structlog.get_logger(__name__)

class AetherException(Exception):
    """Base exception for all Aether platform errors."""
    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}

class DatabaseConnectionError(AetherException):
    """Raised when connection to database backend fails."""
    def __init__(self, service: str, message: str):
        super().__init__(
            message=f"Database connection error [{service}]: {message}",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details={"service": service}
        )

class MCPToolError(AetherException):
    """Raised when an MCP server or tool call fails."""
    def __init__(self, server_name: str, tool_name: str, reason: str):
        super().__init__(
            message=f"MCP tool error [{server_name}.{tool_name}]: {reason}",
            status_code=status.HTTP_502_BAD_GATEWAY,
            details={"server": server_name, "tool": tool_name, "reason": reason}
        )

class ResearchWorkflowError(AetherException):
    """Raised when agent swarm workflow fails."""
    def __init__(self, job_id: str, reason: str):
        super().__init__(
            message=f"Research workflow error for job [{job_id}]: {reason}",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={"job_id": job_id, "reason": reason}
        )

class VectorSearchError(AetherException):
    """Raised when Qdrant vector retrieval fails."""
    def __init__(self, collection: str, message: str):
        super().__init__(
            message=f"Vector search failed on [{collection}]: {message}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details={"collection": collection}
        )

class GraphRAGException(AetherException):
    """Raised when Neo4j GraphRAG operation fails."""
    def __init__(self, query: str, message: str):
        super().__init__(
            message=f"GraphRAG traversal error: {message}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details={"query": query}
        )

async def aether_exception_handler(request: Request, exc: AetherException) -> JSONResponse:
    logger.error("aether_exception", path=request.url.path, message=exc.message, details=exc.details)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.__class__.__name__,
            "message": exc.message,
            "details": exc.details
        }
    )
