from typing import Any, Dict, List
from langchain_core.messages import AIMessage
import structlog

from backend.agents.state import AgentState
from backend.db.neo4j import get_neo4j_driver
from backend.rag.graphrag import (
    run_louvain_communities,
    run_pagerank_centrality,
    run_node2vec_embeddings,
    run_degree_assortativity,
)

logger = structlog.get_logger(__name__)


async def macro_trends_node(state: AgentState) -> Dict[str, Any]:
    """MacroTrendsAgent Background Worker: Executes asynchronous batch graph analytics (Louvain, PageRank, Node2Vec, Degree Assortativity) and triggers consolidation alerts."""
    ticker = state.get("company_ticker", "SYSTEMIC_MACRO")
    logger.info("macro_trends_agent_executing", ticker=ticker)

    errors = list(state.get("errors", []))
    driver = state.get("neo4j_driver")
    if not driver:
        try:
            driver = get_neo4j_driver()
        except Exception:
            driver = get_neo4j_driver("memory")

    try:
        # 1. Louvain Community Detection
        louvain_summaries = await run_louvain_communities(driver)
        communities_data = [
            {
                "community_id": c.community_id,
                "summary": c.summary_text,
                "entities": c.entity_ids,
            }
            for c in louvain_summaries
        ]

        # 2. PageRank Centrality Scores
        pagerank_scores = await run_pagerank_centrality(driver)

        # 3. Node2Vec Topological Embeddings
        node2vec_embeds = await run_node2vec_embeddings(driver, dimensions=32)

        # 4. Degree Assortativity & Consolidation Analysis
        assortativity_metrics = await run_degree_assortativity(driver)

        # Build macro trends payload
        macro_payload: Dict[str, Any] = {
            "communities": communities_data,
            "top_central_entities": sorted(
                pagerank_scores.items(), key=lambda x: x[1], reverse=True
            )[:10],
            "topological_embedding_count": len(node2vec_embeds),
            "network_assortativity": assortativity_metrics.get("assortativity_score", 0.0),
            "edge_density": assortativity_metrics.get("edge_density", 0.0),
            "market_consolidation_alert": assortativity_metrics.get("is_consolidation_alert", False),
            "total_nodes": assortativity_metrics.get("total_nodes", 0),
            "total_edges": assortativity_metrics.get("total_edges", 0),
        }

        # Formulate agent response message
        if assortativity_metrics.get("is_consolidation_alert"):
            alert_text = f"🚨 MARKET CONSOLIDATION ALERT: Density spike detected ({macro_payload['edge_density']}) with assortativity coefficient {macro_payload['network_assortativity']}."
        else:
            alert_text = f"Graph Analytics Complete: {len(communities_data)} Louvain communities detected across {macro_payload['total_nodes']} nodes."

        logger.info(
            "macro_trends_analysis_completed",
            ticker=ticker,
            alert=macro_payload["market_consolidation_alert"],
        )

        ai_msg = AIMessage(
            content=f"[MacroTrends Agent] {alert_text} Calculated PageRank for {len(pagerank_scores)} entities and generated 32-dim Node2Vec embeddings."
        )

        return {"macro_trends_data": macro_payload, "messages": [ai_msg]}

    except Exception as e:
        err_msg = f"MacroTrends Agent execution failed for {ticker}: {str(e)}"
        logger.error("macro_trends_agent_failed", ticker=ticker, error=str(e))
        errors.append(err_msg)
        return {
            "errors": errors,
            "messages": [AIMessage(content=f"[MacroTrends Agent Error] {err_msg}")],
        }
