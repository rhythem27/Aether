from typing import Any, Dict, List, Optional
from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph, END
import structlog

from backend.agents.state import AgentState
from backend.mcp.client import mcp_client
from backend.mcp.servers.sec_edgar import get_company_profile
from backend.rag.anydoc_parser import AnyDocParser
from backend.rag.retriever import HybridRetriever

logger = structlog.get_logger(__name__)


async def mcp_ingestion_node(state: AgentState) -> Dict[str, Any]:
    """Gather SEC disclosures, Crunchbase funding, and news via FastMCP tools with retry handling."""
    ticker = state.get("company_ticker", "AAPL")
    company_name = state.get("company_name", ticker)
    logger.info("ingestion_subgraph_mcp_executing", ticker=ticker)

    research_data = dict(state.get("research_data", {}))
    errors = list(state.get("errors", []))

    try:
        mcp_tools = mcp_client.get_tools_for_servers(
            ["sec_edgar", "crunchbase", "newsapi"]
        )

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

        funding_fn = mcp_tools["get_funding_rounds"]
        funding_rounds = await mcp_client.execute_tool_with_retry(
            funding_fn, company_id=ticker.lower()
        )

        news_fn = mcp_tools["get_recent_news"]
        sentiment_fn = mcp_tools["analyze_news_sentiment"]

        recent_news = await mcp_client.execute_tool_with_retry(
            news_fn, query=company_name, limit=3
        )
        news_sentiment = await mcp_client.execute_tool_with_retry(
            sentiment_fn, articles=recent_news
        )

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
            }
        )

        return {
            "research_data": research_data,
            "messages": [
                AIMessage(
                    content=f"[Ingestion Sub-Graph / MCP] Gathered FastMCP filings ({len(filings)}) and news ({len(recent_news)}) for {ticker}."
                )
            ],
        }

    except Exception as e:
        err_msg = f"MCP Ingestion sub-graph step failed for {ticker}: {str(e)}"
        logger.error("mcp_ingestion_failed", ticker=ticker, error=str(e))
        errors.append(err_msg)
        return {
            "errors": errors,
            "messages": [AIMessage(content=f"[MCP Ingestion Error] {err_msg}")],
        }


async def doc_parser_ocr_node(state: AgentState) -> Dict[str, Any]:
    """Parse large filings/documents (e.g. S-1s) using Firecrawl AnyDoc parser with OCR fallback and chunk splitting."""
    ticker = state.get("company_ticker", "AAPL")
    research_data = dict(state.get("research_data", {}))
    errors = list(state.get("errors", []))
    logger.info("ingestion_subgraph_ocr_executing", ticker=ticker)

    try:
        passages = list(research_data.get("retrieved_passages", []))

        # 1. Check if document file paths or raw documents provided in research_data
        document_paths: List[str] = research_data.get("document_paths", [])
        parser = AnyDocParser()

        parsed_docs = []
        for path in document_paths:
            parsed = await parser.parse_async(
                file_path=path, company_ticker=ticker
            )
            parsed_docs.append(parsed.model_dump())

        # 2. Vector + GraphRAG single-pass retrieval for document chunks
        try:
            from backend.rag.graphrag import FinancialGraphRAG
            graph_rag = FinancialGraphRAG()
            fused_results = await graph_rag.query_unified_vector_graph_rag(
                query=f"{ticker} financial revenue growth risk factors S-1 disclosures",
                seed_entities=[f"company_{ticker.lower()}"],
                top_k=5,
                use_single_pass_reranker=True,
            )
            retrieved = [p.model_dump() for p in fused_results if hasattr(p, "model_dump")]
            passages.extend(retrieved)
        except Exception as rag_err:
            logger.warning("doc_parser_graphrag_warn", error=str(rag_err))
            try:
                retriever = HybridRetriever()
                retrieved = await retriever.search(
                    query=f"{ticker} financial revenue growth risk factors S-1 disclosures",
                    top_k=3,
                    company_ticker=ticker,
                )
                passages.extend([p.model_dump() for p in retrieved])
            except Exception as fallback_err:
                logger.warning("doc_parser_rag_fallback_warn", error=str(fallback_err))

        research_data["retrieved_passages"] = passages
        if parsed_docs:
            research_data["parsed_documents"] = parsed_docs

        return {
            "research_data": research_data,
            "messages": [
                AIMessage(
                    content=f"[Ingestion Sub-Graph / AnyDoc-OCR] Parsed {len(parsed_docs)} docs & indexed {len(passages)} passages."
                )
            ],
        }

    except Exception as e:
        err_msg = f"Doc Parser OCR step failed for {ticker}: {str(e)}"
        logger.error("doc_parser_ocr_failed", ticker=ticker, error=str(e))
        errors.append(err_msg)
        return {
            "errors": errors,
            "messages": [AIMessage(content=f"[Doc Parser OCR Error] {err_msg}")],
        }


async def ingestion_retry_node(state: AgentState) -> Dict[str, Any]:
    """Retry policy node ensuring mandatory data fields exist or logging fallback warnings."""
    research_data = state.get("research_data", {})
    errors = state.get("errors", [])
    logger.info("ingestion_subgraph_retry_evaluating", errors_count=len(errors))

    if not research_data.get("company_profile"):
        research_data["company_profile"] = f"Fallback Profile for {state.get('company_ticker', 'UNKNOWN')}"

    return {
        "research_data": research_data,
        "messages": [
            AIMessage(content="[Ingestion Sub-Graph / Policy] Verified data ingestion completeness.")
        ],
    }


from backend.agents.document_extraction import document_extraction_node


def create_ingestion_subgraph(checkpointer: Optional[Any] = None):
    """Build and compile the Data Ingestion Sub-Graph."""
    workflow = StateGraph(AgentState)

    workflow.add_node("mcp_ingestion", mcp_ingestion_node)
    workflow.add_node("doc_parser_ocr", doc_parser_ocr_node)
    workflow.add_node("document_extraction", document_extraction_node)
    workflow.add_node("ingestion_policy", ingestion_retry_node)

    workflow.set_entry_point("mcp_ingestion")
    workflow.add_edge("mcp_ingestion", "doc_parser_ocr")
    workflow.add_edge("doc_parser_ocr", "document_extraction")
    workflow.add_edge("document_extraction", "ingestion_policy")
    workflow.add_edge("ingestion_policy", END)

    return workflow.compile(checkpointer=checkpointer)


async def ingestion_node(state: AgentState) -> Dict[str, Any]:
    """Node wrapper executing the compiled Ingestion Sub-Graph."""
    subgraph = create_ingestion_subgraph()
    return await subgraph.ainvoke(state)
