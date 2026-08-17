import re
from typing import Any, Dict, List, Optional
from langchain_core.messages import AIMessage
import structlog

from backend.agents.state import AgentState
from backend.rag.taxonomy import get_financial_taxonomy

logger = structlog.get_logger(__name__)


def expand_query(query: str, driver: Optional[Any] = None) -> Dict[str, Any]:
    """Dynamically rewrite query string by expanding financial acronyms and terminology into full synonym clauses."""
    if not query or not query.strip():
        return {
            "original_query": query,
            "expanded_query": query,
            "synonyms": [],
        }

    taxonomy = get_financial_taxonomy()
    words = re.findall(r"\b[\w&'-]+\b", query.lower())
    found_synonyms: List[str] = []
    expanded_parts: List[str] = []

    for word in words:
        syns = taxonomy.get_synonyms(word, driver=driver)
        if syns:
            found_synonyms.extend(syns)
            expanded_parts.append(f"({word} OR {' OR '.join(syns)})")
        else:
            expanded_parts.append(word)

    expanded_query_str = " ".join(expanded_parts)

    logger.info(
        "query_expanded",
        original=query,
        expanded=expanded_query_str,
        synonyms=found_synonyms,
    )

    return {
        "original_query": query,
        "expanded_query": expanded_query_str,
        "synonyms": list(set(found_synonyms)),
    }


async def query_expansion_node(state: AgentState) -> Dict[str, Any]:
    """QueryExpansionAgent: Traverses taxonomy graph nodes before retrieval to rewrite vector/BM25 search payloads for maximum recall."""
    ticker = state.get("company_ticker", "UNKNOWN")
    logger.info("query_expansion_agent_executing", ticker=ticker)

    errors = list(state.get("errors", []))
    driver = state.get("neo4j_driver")

    try:
        user_query = f"{ticker} quarterly capex and revenue report"
        res = expand_query(user_query, driver=driver)

        ai_msg = AIMessage(
            content=f"[Query Expansion Agent] Expanded query for {ticker}: '{res['expanded_query']}'. Injected {len(res['synonyms'])} taxonomy terms."
        )

        return {
            "query_expansion": res,
            "messages": [ai_msg],
        }

    except Exception as e:
        err_msg = f"Query Expansion Agent failed for {ticker}: {str(e)}"
        logger.error("query_expansion_agent_failed", ticker=ticker, error=str(e))
        errors.append(err_msg)
        return {
            "errors": errors,
            "messages": [AIMessage(content=f"[Query Expansion Agent Error] {err_msg}")],
        }
