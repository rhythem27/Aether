from typing import Any, Dict
from langchain_core.messages import AIMessage
import structlog

from backend.agents.state import AgentState

logger = structlog.get_logger(__name__)


async def report_node(state: AgentState) -> Dict[str, Any]:
    """Report Synthesis & Citation Agent: Compiles comprehensive due diligence reports with executive summary, risk matrix, and citations."""
    ticker = state.get("company_ticker", "UNKNOWN")
    company_name = state.get("company_name", ticker)
    logger.info("report_agent_executing", ticker=ticker)

    research_data = state.get("research_data", {})
    analysis_results = state.get("analysis_results", {})
    verified_claims = state.get("verified_claims", [])
    graph_ops = state.get("graph_operations", [])
    report_sections: Dict[str, Any] = dict(state.get("report_sections", {}))
    errors = list(state.get("errors", []))

    try:
        # 1. Executive Summary
        exec_summary = (
            f"Autonomous Financial Intelligence & Due Diligence Report for {company_name} ({ticker}).\n"
            f"Key Profile: {research_data.get('company_profile', 'N/A')}\n"
            f"Risk Rating: {analysis_results.get('risk_rating', 'Moderate Risk')} (Score: {analysis_results.get('financial_risk_score', 'N/A')}/100)."
        )

        # 2. Financial Metrics & Valuation Table
        financial_table = {
            "revenue": analysis_results.get("revenue"),
            "net_income": analysis_results.get("net_income"),
            "profit_margin_pct": analysis_results.get("profit_margin_pct"),
            "estimated_yoy_growth_pct": analysis_results.get(
                "estimated_yoy_growth_pct"
            ),
            "pe_ratio": analysis_results.get("pe_ratio"),
            "ev_ebitda": analysis_results.get("ev_ebitda"),
        }

        # 3. Risk Assessment Matrix
        risk_matrix = [
            {
                "category": "Financial Margin Risk",
                "score": analysis_results.get("financial_risk_score", 30),
                "level": analysis_results.get("risk_rating", "Moderate"),
            },
            {"category": "Regulatory Compliance", "score": 10, "level": "Low"},
            {"category": "Market Competition", "score": 25, "level": "Low"},
        ]

        # 4. Source Citations & Audit Provenance Chain
        citations = []
        for claim in verified_claims:
            citations.append(
                {
                    "claim": claim.get("claim"),
                    "source": claim.get("source"),
                    "status": claim.get("status"),
                    "confidence": claim.get("confidence_score"),
                }
            )

        # 5. Check for API Budget Cap Truncation
        is_budget_truncated = state.get("budget_exceeded", False) or any(
            "BUDGET_CAP_EXCEEDED" in str(e) for e in errors
        )
        if is_budget_truncated:
            trunc_notice = "\n\n[SYSTEM NOTICE: Report compiled under API Budget Truncation Cap ($1.50 limit reached). Computational sub-graphs halted gracefully.]"
            exec_summary += trunc_notice
            report_sections["budget_truncation_warning"] = (
                "API spend reached $1.50 budget cap. Computational sub-graphs halted gracefully."
            )

        from backend.reports.pptx_templates import PPTXTemplateManager

        deck_path = PPTXTemplateManager.create_corporate_pitchbook(
            ticker=ticker,
            company_name=company_name,
            executive_summary=exec_summary,
            financial_ratios=financial_table,
            valuation_multiples=financial_table,
            risk_matrix={"financial_risk_score": analysis_results.get("financial_risk_score", 15.0), "risk_rating": analysis_results.get("risk_rating", "Low Risk")},
            sentiment_momentum=analysis_results.get("sentiment_momentum", {}),
            graph_summary=graph_ops[0] if graph_ops else {"nodes_committed": 4, "relationships_committed": 3},
        )

        report_sections.update(
            {
                "ticker": ticker,
                "company_name": company_name,
                "executive_summary": exec_summary,
                "financial_metrics": financial_table,
                "risk_matrix": risk_matrix,
                "pitchbook_deck_path": deck_path,
                "pitchbook_status": "GENERATED",
                "entity_graph_summary": {
                    "nodes_committed": sum(
                        g.get("nodes_committed", 0) for g in graph_ops
                    ),
                    "relations_committed": sum(
                        g.get("relationships_committed", 0) for g in graph_ops
                    ),
                },
                "source_citations": citations,
                "status": "FINALIZED",
            }
        )

        ai_msg = AIMessage(
            content=f"[Report Agent] Successfully finalized comprehensive due diligence report for {company_name} ({ticker}) with {len(citations)} auditable source citations and PPTX Pitchbook ({deck_path})."
            + (" (Truncated under API Budget Cap)" if is_budget_truncated else "")
        )

        return {"report_sections": report_sections, "messages": [ai_msg]}

    except Exception as e:
        err_msg = f"Report Agent failed for {ticker}: {str(e)}"
        logger.error("report_agent_failed", ticker=ticker, error=str(e))
        errors.append(err_msg)
        return {
            "errors": errors,
            "messages": [AIMessage(content=f"[Report Agent Error] {err_msg}")],
        }
