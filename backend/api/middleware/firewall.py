import re
from typing import Callable
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

logger = structlog.get_logger(__name__)

# Heuristic regex patterns for prompt injection, jailbreaks, and prohibited financial requests
ADVERSARIAL_PATTERNS = [
    r"(?i)ignore\s+(all\s+)?previous\s+instructions",
    r"(?i)bypass\s+(all\s+)?guardrails",
    r"(?i)system\s+prompt\s+override",
    r"(?i)act\s+as\s+an?\s+unrestricted",
    r"(?i)do\s+anything\s+now",
    r"(?i)dan\s+mode",
    r"(?i)generate\s+fake\s+(news|rumors?|press\s+release)",
    r"(?i)manipulate\s+(stock|market)\s+prices?",
    r"(?i)insider\s+trading\s+(tips|secrets|leaks)",
    r"(?i)non-public\s+earnings\s+leak",
    r"(?i)override\s+safety\s+filters?",
]


class SemanticFirewallMiddleware(BaseHTTPMiddleware):
    """Low-latency Semantic Firewall Middleware blocking adversarial prompt injections, jailbreaks, and illegal financial market manipulation requests."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check query string parameters
        from urllib.parse import unquote
        raw_query = unquote(request.url.query or "")
        param_values = " ".join(request.query_params.values())
        combined_query = f"{raw_query} {param_values}"

        for pattern in ADVERSARIAL_PATTERNS:
            if re.search(pattern, combined_query):
                logger.warning(
                    "semantic_firewall_blocked_query",
                    pattern=pattern,
                    path=request.url.path,
                    client=request.client.host if request.client else "unknown",
                )
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": "Security Violation: Adversarial prompt injection or prohibited financial inquiry detected."
                    },
                )


        # Check body for POST/PUT/PATCH requests
        if request.method in ("POST", "PUT", "PATCH"):
            try:
                body_bytes = await request.body()
                if body_bytes:
                    body_text = body_bytes.decode("utf-8", errors="ignore")
                    for pattern in ADVERSARIAL_PATTERNS:
                        if re.search(pattern, body_text):
                            logger.warning(
                                "semantic_firewall_blocked_body",
                                pattern=pattern,
                                path=request.url.path,
                                client=request.client.host if request.client else "unknown",
                            )
                            return JSONResponse(
                                status_code=403,
                                content={
                                    "detail": "Security Violation: Adversarial prompt injection or prohibited financial inquiry detected."
                                },
                            )
            except Exception as err:
                logger.warning("semantic_firewall_body_read_error", error=str(err))

        return await call_next(request)
