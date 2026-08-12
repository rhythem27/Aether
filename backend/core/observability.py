import functools
from typing import Callable
import structlog

from backend.core.config import settings

logger = structlog.get_logger(__name__)

# Try importing Langfuse decorators
try:
    from langfuse.decorators import observe, langfuse_context

    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False
    observe = None
    langfuse_context = None


def observe_agent(agent_name: str, as_type: str = "agent"):
    """Decorator for instrumenting agent node functions with Langfuse tracing and metadata scoring."""

    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            state = (
                args[0]
                if args and isinstance(args[0], dict)
                else kwargs.get("state", {})
            )
            company = state.get("company_ticker", "UNKNOWN")

            if LANGFUSE_AVAILABLE and settings.LANGFUSE_PUBLIC_KEY and observe:
                try:
                    langfuse_context.update_current_trace(
                        name=f"aether_agent_{agent_name}",
                        metadata={"company_ticker": company, "agent_name": agent_name},
                        tags=["financial_intelligence", "multi_agent_swarm"],
                    )
                except Exception as e:
                    logger.debug("langfuse_trace_update_skipped", error=str(e))

            result = await func(*args, **kwargs)

            if LANGFUSE_AVAILABLE and settings.LANGFUSE_PUBLIC_KEY and langfuse_context:
                try:
                    langfuse_context.score_current_observation(
                        name=f"{agent_name}_execution_status",
                        value=1.0 if not state.get("errors") else 0.0,
                    )
                except Exception as e:
                    logger.debug("langfuse_score_update_skipped", error=str(e))

            return result

        return wrapper

    return decorator
