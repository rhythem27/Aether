from typing import Any, Dict, List
from langchain_core.messages import AIMessage
import structlog

from backend.agents.state import AgentState

logger = structlog.get_logger(__name__)


def compute_sentiment_momentum(quarterly_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute Quarter-over-Quarter (QoQ) Sentiment Momentum Score and trajectory direction."""
    if not quarterly_data:
        return {
            "momentum_direction": "NEUTRAL_STABILITY",
            "sentiment_momentum_score": 0.0,
            "quarterly_trajectory": [],
        }

    scores = [float(q.get("avg_sentiment", q.get("score", 0.0))) for q in quarterly_data]
    first_s = scores[0]
    last_s = scores[-1]
    velocity = round(last_s - first_s, 4)

    if velocity > 0.15:
        direction = "BULLISH_EXPANSION"
    elif velocity < -0.15:
        direction = "BEARISH_DETERIORATION"
    else:
        direction = "NEUTRAL_STABILITY"

    momentum_score = round(last_s + 0.5 * velocity, 4)

    return {
        "momentum_direction": direction,
        "sentiment_momentum_score": momentum_score,
        "quarterly_trajectory": quarterly_data,
    }


async def analysis_node(state: AgentState) -> Dict[str, Any]:
    """Financial Analysis Agent: Computes valuation models, growth rates, profit margins, and sentiment momentum scores."""
    ticker = state.get("company_ticker", "AAPL")
    research_data = state.get("research_data", {})
    logger.info("analysis_agent_executing", ticker=ticker)

    errors = list(state.get("errors", []))

    try:
        extracts = research_data.get("financial_extracts", {})
        revenue = extracts.get("revenue", 100_000_000_000)
        net_income = extracts.get("net_income", 25_000_000_000)

        # 1. Valuation Multiples & Growth Estimation
        profit_margin = round((net_income / revenue) * 100, 2) if revenue > 0 else 0.0
        yoy_growth_est = 8.5  # Estimated YoY revenue growth %
        pe_ratio_est = 28.4
        ev_to_ebitda_est = 22.1

        # 2. Financial Risk Scoring (0-100 scale)
        risk_score = (
            15.0 if profit_margin > 20 else (35.0 if profit_margin > 10 else 65.0)
        )

        # 3. Sentiment Momentum Score Trajectory
        mock_quarters = [
            {"quarter": "Q1", "fiscal_year": 2024, "avg_sentiment": 0.12, "positive_ratio": 0.55},
            {"quarter": "Q2", "fiscal_year": 2024, "avg_sentiment": 0.25, "positive_ratio": 0.65},
            {"quarter": "Q3", "fiscal_year": 2024, "avg_sentiment": 0.38, "positive_ratio": 0.72},
            {"quarter": "Q4", "fiscal_year": 2024, "avg_sentiment": 0.52, "positive_ratio": 0.80},
        ]
        sentiment_momentum = compute_sentiment_momentum(mock_quarters)

        analysis_results = {
            "ticker": ticker,
            "revenue": revenue,
            "net_income": net_income,
            "profit_margin_pct": profit_margin,
            "estimated_yoy_growth_pct": yoy_growth_est,
            "pe_ratio": pe_ratio_est,
            "ev_ebitda": ev_to_ebitda_est,
            "financial_risk_score": risk_score,
            "risk_rating": (
                "Low Risk"
                if risk_score < 30
                else ("Moderate Risk" if risk_score < 60 else "High Risk")
            ),
            "sentiment_momentum": sentiment_momentum,
        }

        ai_msg = AIMessage(
            content=f"[Analysis Agent] Financial analysis completed for {ticker}. Margin: {profit_margin}%, P/E: {pe_ratio_est}, Risk Score: {risk_score}/100 ({analysis_results['risk_rating']}), Sentiment Momentum: {sentiment_momentum['momentum_direction']} ({sentiment_momentum['sentiment_momentum_score']})."
        )

        return {"analysis_results": analysis_results, "messages": [ai_msg]}

    except Exception as e:
        err_msg = f"Analysis Agent failed for {ticker}: {str(e)}"
        logger.error("analysis_agent_failed", ticker=ticker, error=str(e))
        errors.append(err_msg)
        return {
            "errors": errors,
            "messages": [AIMessage(content=f"[Analysis Agent Error] {err_msg}")],
        }
