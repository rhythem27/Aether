from typing import Any, Dict
from langchain_core.messages import AIMessage
import structlog

from backend.agents.state import AgentState
from backend.mcp.servers.sec_edgar import search_filings, extract_financials, get_company_profile
from backend.rag.retriever import HybridRetriever

logger = structlog.get_logger(__name__)

async def research_node(state: AgentState) -> Dict[str, Any]:
    """Research Data Gathering Agent: Aggregates SEC disclosures, company profiles, and RAG search passages."""
    ticker = state.get("company_ticker", "AAPL")
    logger.info("research_agent_executing", ticker=ticker)

    research_data = dict(state.get("research_data", {}))
    errors = list(state.get("errors", []))

    try:
        # 1. Gather SEC EDGAR Filings & Company Profile
        profile_str = await get_company_profile(ticker)
        filings = await search_filings(ticker, form_type="10-K", limit=3)
        
        financial_extracts = {}
        if filings and isinstance(filings, list) and len(filings) > 0:
            filing_url = filings[0].get("linkToFilingDetails", "")
            if filing_url:
                financial_extracts = await extract_financials(filing_url)

        # 2. Query Hybrid Retriever for RAG passages if available
        passages = []
        try:
            retriever = HybridRetriever()
            retrieved = await retriever.search(
                query=f"{ticker} financial revenue growth risk factors",
                top_k=3,
                company_ticker=ticker
            )
            passages = [p.model_dump() for p in retrieved]
        except Exception as rag_err:
            logger.warning("research_rag_retrieval_warn", error=str(rag_err))

        research_data.update({
            "ticker": ticker,
            "company_profile": profile_str,
            "sec_filings": filings,
            "financial_extracts": financial_extracts,
            "retrieved_passages": passages
        })

        ai_msg = AIMessage(
            content=f"[Research Agent] Completed data gathering for {ticker}. Retrieved {len(filings)} SEC filings and {len(passages)} RAG passages."
        )

        return {
            "research_data": research_data,
            "messages": [ai_msg]
        }

    except Exception as e:
        err_msg = f"Research Agent failed for {ticker}: {str(e)}"
        logger.error("research_agent_failed", ticker=ticker, error=str(e))
        errors.append(err_msg)
        return {
            "errors": errors,
            "messages": [AIMessage(content=f"[Research Agent Error] {err_msg}")]
        }
