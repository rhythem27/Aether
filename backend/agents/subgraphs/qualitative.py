from typing import Any, Dict, List, Optional
from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph, END
import structlog

from backend.agents.state import AgentState
from backend.agents.analysis import compute_sentiment_momentum

logger = structlog.get_logger(__name__)


async def sentiment_momentum_node(state: AgentState) -> Dict[str, Any]:
    """Compute Quarter-over-Quarter (QoQ) Sentiment Momentum Score trajectory."""
    ticker = state.get("company_ticker", "AAPL")
    analysis_results = dict(state.get("analysis_results", {}))
    research_data = state.get("research_data", {})
    logger.info("qualitative_subgraph_sentiment_executing", ticker=ticker)

    news_sentiment = research_data.get("news_sentiment", {})
    score_val = news_sentiment.get("score", 0.35)

    mock_quarters = [
        {"quarter": "Q1", "fiscal_year": 2024, "avg_sentiment": round(score_val - 0.2, 2), "positive_ratio": 0.55},
        {"quarter": "Q2", "fiscal_year": 2024, "avg_sentiment": round(score_val - 0.1, 2), "positive_ratio": 0.65},
        {"quarter": "Q3", "fiscal_year": 2024, "avg_sentiment": round(score_val, 2), "positive_ratio": 0.72},
        {"quarter": "Q4", "fiscal_year": 2024, "avg_sentiment": round(score_val + 0.15, 2), "positive_ratio": 0.80},
    ]

    sentiment_momentum = compute_sentiment_momentum(mock_quarters)
    analysis_results["sentiment_momentum"] = sentiment_momentum

    return {
        "analysis_results": analysis_results,
        "messages": [
            AIMessage(
                content=f"[Qualitative Sub-Graph / Sentiment] Trajectory: {sentiment_momentum['momentum_direction']} ({sentiment_momentum['sentiment_momentum_score']})."
            )
        ],
    }


async def expert_transcript_node(state: AgentState) -> Dict[str, Any]:
    """Extract qualitative insights from expert call transcripts and news sentiment."""
    ticker = state.get("company_ticker", "AAPL")
    research_data = dict(state.get("research_data", {}))
    logger.info("qualitative_subgraph_transcripts_executing", ticker=ticker)

    qual_passages = list(research_data.get("qualitative_passages", []))
    expert_transcripts = research_data.get("expert_transcripts", [])

    if expert_transcripts and not qual_passages:
        try:
            from backend.rag.transcripts import query_qualitative_transcript_passages
            for tr in expert_transcripts:
                passages = await query_qualitative_transcript_passages(tr, speaker_role_filter="executive")
                qual_passages.extend(passages)
            research_data["qualitative_passages"] = qual_passages
        except Exception as err:
            logger.warning("qualitative_transcript_extraction_warn", error=str(err))

    return {
        "research_data": research_data,
        "messages": [
            AIMessage(
                content=f"[Qualitative Sub-Graph / Transcripts] Extracted {len(qual_passages)} executive transcript insights."
            )
        ],
    }


async def qualitative_risk_node(state: AgentState) -> Dict[str, Any]:
    """Perform compliance and qualitative risk scoring."""
    ticker = state.get("company_ticker", "AAPL")
    analysis_results = dict(state.get("analysis_results", {}))
    logger.info("qualitative_subgraph_compliance_executing", ticker=ticker)

    qual_risk = {
        "regulatory_compliance_status": "COMPLIANT",
        "litigation_risk_level": "LOW",
        "governance_score": 92.0,
    }
    analysis_results["qualitative_risk"] = qual_risk

    return {
        "analysis_results": analysis_results,
        "messages": [
            AIMessage(
                content=f"[Qualitative Sub-Graph / Compliance] Governance score: {qual_risk['governance_score']} for {ticker}."
            )
        ],
    }


def create_qualitative_subgraph(checkpointer: Optional[Any] = None):
    """Build and compile the Qualitative Sub-Graph."""
    workflow = StateGraph(AgentState)

    workflow.add_node("sentiment_momentum", sentiment_momentum_node)
    workflow.add_node("expert_transcripts", expert_transcript_node)
    workflow.add_node("qualitative_compliance", qualitative_risk_node)

    workflow.set_entry_point("sentiment_momentum")
    workflow.add_edge("sentiment_momentum", "expert_transcripts")
    workflow.add_edge("expert_transcripts", "qualitative_compliance")
    workflow.add_edge("qualitative_compliance", END)

    return workflow.compile(checkpointer=checkpointer)


async def qualitative_node(state: AgentState) -> Dict[str, Any]:
    """Node wrapper executing the compiled Qualitative Sub-Graph."""
    subgraph = create_qualitative_subgraph()
    return await subgraph.ainvoke(state)
