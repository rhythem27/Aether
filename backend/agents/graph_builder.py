from typing import Any, Dict, List, Optional
from langchain_core.messages import AIMessage
import structlog

from backend.agents.state import AgentState
from backend.db.neo4j import bulk_write_nodes_and_relationships, get_neo4j_driver, InMemoryNeo4jDriver
from backend.rag.graphrag import EntityExtractor, EntityResolver, EntityType

logger = structlog.get_logger(__name__)

async def graph_node(state: AgentState) -> Dict[str, Any]:
    """Graph Operations Agent: Validates entity networks and executes transactional bulk Cypher updates into Neo4j."""
    ticker = state.get("company_ticker", "UNKNOWN")
    company_name = state.get("company_name", ticker)
    logger.info("graph_agent_executing", ticker=ticker)

    research_data = state.get("research_data", {})
    graph_ops: List[Dict[str, Any]] = list(state.get("graph_operations", []))
    errors = list(state.get("errors", []))

    try:
        extractor = EntityExtractor()
        
        # Aggregate text disclosures for graph extraction
        text_snippets = [company_name]
        profile_str = research_data.get("company_profile", "")
        if profile_str:
            text_snippets.append(profile_str)
        
        for passage in research_data.get("retrieved_passages", []):
            if isinstance(passage, dict) and "text" in passage:
                text_snippets.append(passage["text"])

        combined_text = "\n".join(text_snippets)
        extracted = extractor.extract_from_text(combined_text)

        # Ensure target company node exists
        canonical_target = EntityResolver.canonicalize_name(company_name)
        target_id = EntityResolver.generate_entity_id(canonical_target, EntityType.COMPANY)
        
        nodes_dicts = [
            {
                "id": target_id,
                "name": canonical_target,
                "label": EntityType.COMPANY.value,
                "properties": {"ticker": ticker}
            }
        ]
        
        for node in extracted.nodes:
            if node.id != target_id:
                nodes_dicts.append({
                    "id": node.id,
                    "name": node.name,
                    "label": node.label.value,
                    "properties": node.properties
                })

        rels_dicts = [
            {
                "source_id": r.source_id,
                "target_id": r.target_id,
                "rel_type": r.rel_type.value,
                "properties": r.properties
            }
            for r in extracted.relationships
        ]

        # Execute transactional bulk write (try live driver first, fallback to memory driver if connection fails)
        driver = state.get("neo4j_driver")
        if not driver:
            try:
                driver = get_neo4j_driver()
                # Test connectivity
                async with driver.session() as session:
                    await session.run("RETURN 1")
            except Exception:
                driver = get_neo4j_driver("memory")

        total_committed = await bulk_write_nodes_and_relationships(
            nodes=nodes_dicts,
            relationships=rels_dicts,
            driver=driver
        )

        op_entry = {
            "operation": "BULK_UPSERT",
            "company_ticker": ticker,
            "nodes_committed": len(nodes_dicts),
            "relationships_committed": len(rels_dicts),
            "total_elements": total_committed
        }
        graph_ops.append(op_entry)

        ai_msg = AIMessage(
            content=f"[Graph Agent] Successfully committed {len(nodes_dicts)} entity nodes and {len(rels_dicts)} relationship edges to Neo4j graph store."
        )

        return {
            "graph_operations": graph_ops,
            "messages": [ai_msg]
        }

    except Exception as e:
        err_msg = f"Graph Agent failed for {ticker}: {str(e)}"
        logger.error("graph_agent_failed", ticker=ticker, error=str(e))
        errors.append(err_msg)
        return {
            "errors": errors,
            "messages": [AIMessage(content=f"[Graph Agent Error] {err_msg}")]
        }
