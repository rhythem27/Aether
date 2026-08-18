from typing import Any, Dict
from langchain_core.messages import AIMessage
import structlog

from backend.agents.state import AgentState

logger = structlog.get_logger(__name__)

# Standard Cost Rates ($ per token)
INPUT_TOKEN_RATE = 0.0000025   # $2.50 per 1,000,000 input tokens
OUTPUT_TOKEN_RATE = 0.0000100  # $10.00 per 1,000,000 output tokens
MAX_BUDGET_CAP = 1.50          # $1.50 API budget cap per research job


def calculate_token_cost(token_usage: Dict[str, int]) -> float:
    """Compute total API spend in USD from token usage dictionary."""
    input_tokens = token_usage.get("prompt_tokens", token_usage.get("input_tokens", 0))
    output_tokens = token_usage.get("completion_tokens", token_usage.get("output_tokens", 0))

    if not input_tokens and not output_tokens:
        total_toks = token_usage.get("total_tokens", 0)
        input_tokens = int(total_toks * 0.7)
        output_tokens = int(total_toks * 0.3)

    cost = (input_tokens * INPUT_TOKEN_RATE) + (output_tokens * OUTPUT_TOKEN_RATE)
    return round(cost, 6)


async def cost_management_node(state: AgentState) -> Dict[str, Any]:
    """Cost Management Agent: Monitors real-time Langfuse token spend and enforces $1.50 budget circuit breakers."""
    ticker = state.get("company_ticker", "UNKNOWN")
    logger.info("cost_management_agent_executing", ticker=ticker)

    token_usage = dict(state.get("token_usage", {}))
    errors = list(state.get("errors", []))
    budget_exceeded = state.get("budget_exceeded", False)

    # Estimate tokens if state has accumulated messages
    messages = state.get("messages", [])
    if not token_usage and messages:
        msg_text_len = sum(len(getattr(m, "content", "")) for m in messages)
        est_tokens = max(100, msg_text_len // 4)
        token_usage = {
            "prompt_tokens": int(est_tokens * 0.7),
            "completion_tokens": int(est_tokens * 0.3),
            "total_tokens": est_tokens,
        }

    current_cost = calculate_token_cost(token_usage)
    forced_cost = state.get("force_simulated_cost", 0.0)
    effective_cost = max(current_cost, forced_cost)

    logger.info(
        "cost_management_budget_check",
        ticker=ticker,
        current_cost=effective_cost,
        max_budget=MAX_BUDGET_CAP,
    )

    if effective_cost >= MAX_BUDGET_CAP:
        budget_exceeded = True
        err_msg = f"BUDGET_CAP_EXCEEDED: API spend reached ${effective_cost:.2f} (exceeds ${MAX_BUDGET_CAP:.2f} cap). Halting further sub-graph expansions."
        logger.error("budget_circuit_breaker_triggered", ticker=ticker, cost=effective_cost)

        if err_msg not in errors:
            errors.append(err_msg)

        ai_msg = AIMessage(
            content=f"[Cost Management Agent Warning] Budget limit exceeded (${effective_cost:.2f} / ${MAX_BUDGET_CAP:.2f}). Halting further sub-graph expansions."
        )

        return {
            "budget_exceeded": True,
            "errors": errors,
            "token_usage": token_usage,
            "messages": [ai_msg],
        }

    ai_msg = AIMessage(
        content=f"[Cost Management Agent] API Spend: ${effective_cost:.4f} / ${MAX_BUDGET_CAP:.2f} (Within Budget)."
    )

    return {
        "budget_exceeded": budget_exceeded,
        "token_usage": token_usage,
        "messages": [ai_msg],
    }
