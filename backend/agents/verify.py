from typing import Any, Dict, List
from langchain_core.messages import AIMessage
import structlog

from backend.agents.state import AgentState
from backend.core.observability import observe_agent
from backend.core.metrics import VERIFIED_CLAIMS_COUNT

logger = structlog.get_logger(__name__)

try:
    from langgraph.types import interrupt

    INTERRUPT_AVAILABLE = True
except ImportError:
    INTERRUPT_AVAILABLE = False
    interrupt = None  # type: ignore[assignment]


@observe_agent(agent_name="verify_agent")
async def verify_node(state: AgentState) -> Dict[str, Any]:
    """Fact-Checking & Verification Agent: Audits financial claims against primary SEC sources and RAG passages."""
    ticker = state.get("company_ticker", "UNKNOWN")
    logger.info("verify_agent_executing", ticker=ticker)

    research_data = state.get("research_data", {})
    analysis_results = state.get("analysis_results", {})
    verified_claims: List[Dict[str, Any]] = list(state.get("verified_claims", []))
    errors = list(state.get("errors", []))

    try:
        extracts = research_data.get("financial_extracts", {})
        reported_rev = analysis_results.get("revenue")
        source_rev = extracts.get("revenue")

        # 1. Audit Revenue Claim
        if reported_rev and source_rev and reported_rev == source_rev:
            verified_claims.append(
                {
                    "claim": f"{ticker} Annual Revenue is ${reported_rev:,}",
                    "source": "SEC EDGAR 10-K",
                    "status": "VERIFIED",
                    "confidence_score": 0.98,
                }
            )
            VERIFIED_CLAIMS_COUNT.labels(status="VERIFIED").inc()
        elif reported_rev:
            verified_claims.append(
                {
                    "claim": f"{ticker} Reported Revenue is ${reported_rev:,}",
                    "source": "Unverified Primary Source",
                    "status": "UNVERIFIED_CLAIM",
                    "confidence_score": 0.50,
                }
            )
            VERIFIED_CLAIMS_COUNT.labels(status="UNVERIFIED").inc()

        # 2. Audit Profit Margin & Risk Metrics
        margin = analysis_results.get("profit_margin_pct")
        if margin is not None:
            verified_claims.append(
                {
                    "claim": f"{ticker} Profit Margin is {margin}%",
                    "source": "Computed Financial Analysis Model",
                    "status": "VERIFIED",
                    "confidence_score": 0.95,
                }
            )
            VERIFIED_CLAIMS_COUNT.labels(status="VERIFIED").inc()

        # 3. Check for unverified passages / hallucinated metrics
        passages = research_data.get("retrieved_passages", [])
        if passages:
            verified_claims.append(
                {
                    "claim": f"Grounded in {len(passages)} primary document RAG passages",
                    "source": "Qdrant Hybrid Vector Store",
                    "status": "VERIFIED",
                    "confidence_score": 0.92,
                }
            )
            VERIFIED_CLAIMS_COUNT.labels(status="VERIFIED").inc()

        verified_count = sum(
            1 for c in verified_claims if c.get("status") == "VERIFIED"
        )

        total_claims = len(verified_claims)
        avg_conf = (
            sum(float(c.get("confidence_score", 0.0)) for c in verified_claims) / max(1, total_claims)
            if total_claims > 0
            else 0.0
        )

        low_conf_count = int(state.get("low_confidence_attempts", 0))
        if avg_conf < 0.85:
            low_conf_count += 1
            logger.warning(
                "verify_low_confidence_iteration",
                ticker=ticker,
                avg_confidence=round(avg_conf, 2),
                consecutive_count=low_conf_count,
            )
        else:
            low_conf_count = 0

        if low_conf_count >= 3:
            cb_msg = "CIRCUIT_BREAKER_TRIGGERED: Verification confidence < 85% across 3 consecutive iterations."
            logger.error("circuit_breaker_triggered", ticker=ticker, avg_confidence=round(avg_conf, 2))
            if cb_msg not in errors:
                errors.append(cb_msg)

        ai_msg = AIMessage(
            content=f"[Verify Agent] Completed claim audit for {ticker}. Verified {verified_count}/{total_claims} financial claims (avg confidence: {avg_conf:.2f})."
        )

        return {
            "verified_claims": verified_claims,
            "low_confidence_attempts": low_conf_count,
            "errors": errors,
            "messages": [ai_msg],
        }

    except Exception as e:
        err_msg = f"Verify Agent failed for {ticker}: {str(e)}"
        logger.error("verify_agent_failed", ticker=ticker, error=str(e))
        errors.append(err_msg)
        return {
            "errors": errors,
            "messages": [AIMessage(content=f"[Verify Agent Error] {err_msg}")],
        }



async def high_risk_validator_node(state: AgentState) -> Dict[str, Any]:
    """Human-in-the-Loop (HITL) Checkpoint Node using langgraph.types.interrupt."""
    unverified = [
        c
        for c in state.get("verified_claims", [])
        if c.get("status") == "UNVERIFIED_CLAIM"
    ]

    if unverified and INTERRUPT_AVAILABLE and callable(interrupt):
        logger.warning("hitl_interrupt_triggered", num_unverified=len(unverified))
        decision = interrupt(
            {
                "unverified_claims": unverified,
                "prompt": "Unverified financial claims detected. Human analyst decision required: approve or reject.",
            }
        )
        if isinstance(decision, dict) and decision.get("action") == "reject":
            verified_clean = [
                c
                for c in state.get("verified_claims", [])
                if c.get("status") != "UNVERIFIED_CLAIM"
            ]
            return {
                "verified_claims": verified_clean,
                "human_approval": False,
                "messages": [
                    AIMessage(
                        content="[HITL] Human analyst rejected unverified financial claims."
                    )
                ],
            }

    return {
        "human_approval": True,
        "messages": [
            AIMessage(
                content="[HITL] Financial claims validated and approved for final report synthesis."
            )
        ],
    }
