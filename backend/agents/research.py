from typing import Any, Dict
from langchain_core.messages import AIMessage
import structlog

from backend.agents.state import AgentState
from backend.mcp.client import mcp_client
from backend.mcp.servers.sec_edgar import get_company_profile
from backend.rag.retriever import HybridRetriever

logger = structlog.get_logger(__name__)


async def research_node(state: AgentState) -> Dict[str, Any]:
    """Research Data Gathering Agent: Dynamically invokes MCP tools (SEC, Crunchbase, NewsAPI) with retry handling."""
    ticker = state.get("company_ticker", "AAPL")
    company_name = state.get("company_name", ticker)
    logger.info("research_agent_executing", ticker=ticker)

    research_data = dict(state.get("research_data", {}))
    errors = list(state.get("errors", []))

    try:
        # Load MCP tools for research agent
        mcp_tools = mcp_client.get_tools_for_servers(
            ["sec_edgar", "crunchbase", "newsapi"]
        )

        # 1. SEC EDGAR disclosures
        search_filings_fn = mcp_tools["search_filings"]
        extract_financials_fn = mcp_tools["extract_financials"]

        profile_str = await get_company_profile(ticker)
        filings = await mcp_client.execute_tool_with_retry(
            search_filings_fn, ticker=ticker, form_type="10-K", limit=3
        )

        financial_extracts = {}
        if filings and isinstance(filings, list) and len(filings) > 0:
            filing_url = filings[0].get(
                "file_url", filings[0].get("sample_filing_url", "")
            )
            if filing_url:
                financial_extracts = await mcp_client.execute_tool_with_retry(
                    extract_financials_fn, filing_url=filing_url
                )

        # 2. Crunchbase Private Market & M&A Data
        funding_fn = mcp_tools["get_funding_rounds"]
        funding_rounds = await mcp_client.execute_tool_with_retry(
            funding_fn, company_id=ticker.lower()
        )

        # 3. NewsAPI Sentiment & Market News
        news_fn = mcp_tools["get_recent_news"]
        sentiment_fn = mcp_tools["analyze_news_sentiment"]

        recent_news = await mcp_client.execute_tool_with_retry(
            news_fn, query=company_name, limit=3
        )
        news_sentiment = await mcp_client.execute_tool_with_retry(
            sentiment_fn, articles=recent_news
        )

        # 4. Hybrid Vector + GraphRAG RRF passages
        passages = []
        try:
            from backend.rag.graphrag import FinancialGraphRAG
            graph_rag = FinancialGraphRAG()
            fused_results = await graph_rag.query_hybrid_rrf(
                query=f"{ticker} financial revenue growth risk factors",
                top_k=5,
            )
            passages = [p.model_dump() for p in fused_results if hasattr(p, "model_dump")]
        except Exception as rag_err:
            logger.warning("research_graphrag_retrieval_warn", error=str(rag_err))
            try:
                retriever = HybridRetriever()
                retrieved = await retriever.search(
                    query=f"{ticker} financial revenue growth risk factors",
                    top_k=3,
                    company_ticker=ticker,
                )
                passages = [p.model_dump() for p in retrieved]
            except Exception as fallback_err:
                logger.warning("research_rag_fallback_warn", error=str(fallback_err))

        research_data.update(
            {
                "ticker": ticker,
                "company_name": company_name,
                "company_profile": profile_str,
                "sec_filings": filings,
                "financial_extracts": financial_extracts,
                "funding_rounds": funding_rounds,
                "recent_news": recent_news,
                "news_sentiment": news_sentiment,
                "retrieved_passages": passages,
            }
        )

        ai_msg = AIMessage(
            content=f"[Research Agent] Dynamically gathered MCP data for {ticker}. SEC filings: {len(filings)}, News: {len(recent_news)}, Sentiment: {news_sentiment.get('sentiment')}."
        )

        return {"research_data": research_data, "messages": [ai_msg]}

    except Exception as e:
        err_msg = f"Research Agent failed for {ticker}: {str(e)}"
        logger.error("research_agent_failed", ticker=ticker, error=str(e))
        errors.append(err_msg)
        return {
            "errors": errors,
            "messages": [AIMessage(content=f"[Research Agent Error] {err_msg}")],
        }
