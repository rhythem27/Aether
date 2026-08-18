from typing import Any, Dict, Optional
from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph, END
import structlog

from backend.agents.state import AgentState
from backend.agents.research import research_node
from backend.agents.analysis import analysis_node
from backend.agents.verify import verify_node
from backend.agents.graph_builder import graph_node
from backend.agents.macro_trends import macro_trends_node
from backend.agents.report import report_node
from backend.agents.subgraphs import (
    create_ingestion_subgraph,
    ingestion_node,
    create_quantitative_subgraph,
    quantitative_node,
    create_qualitative_subgraph,
    qualitative_node,
)

logger = structlog.get_logger(__name__)


async def supervisor_node(state: AgentState) -> Dict[str, Any]:
    """Master Orchestrator Agent: Decomposes tasks, validates inputs, and plans nested sub-graph execution."""
    ticker = state.get("company_ticker", "UNKNOWN")
    logger.info("master_orchestrator_node_executing", ticker=ticker)

    ai_msg = AIMessage(content=f"[Master Orchestrator] Planning nested sub-graph execution for {ticker}.")
    return {"messages": [ai_msg]}


def supervisor_router(state: AgentState) -> str:
    """Routing edge logic for Master Orchestrator Plan-Execute workflow."""
    errors = state.get("errors", [])
    if any("CIRCUIT_BREAKER_TRIGGERED" in str(err) for err in errors):
        logger.error("supervisor_circuit_breaker_escalating_to_human")
        return "human_escalation"

    if errors and len(errors) > 2:
        logger.warning("supervisor_escalating_to_human", num_errors=len(errors))
        return "human_escalation"

    if not state.get("research_data"):
        return "research_agent"
    if not state.get("analysis_results"):
        return "analysis_agent"
    if not state.get("verified_claims"):
        return "verify_agent"
    if not state.get("graph_operations"):
        return "graph_agent"
    if not state.get("macro_trends_data"):
        return "macro_trends_agent"
    if not state.get("report_sections"):
        return "report_agent"

    return END


async def human_escalation_node(state: AgentState) -> Dict[str, Any]:
    """Human-in-the-loop escalation node for unresolved agent errors."""
    logger.error("human_escalation_node_triggered", errors=state.get("errors"))
    return {
        "human_approval": False,
        "messages": [
            AIMessage(
                content="[Escalation] Workflow suspended due to repeated errors. Human approval required."
            )
        ],
    }


async def master_orchestrator_ingestion_node(state: AgentState) -> Dict[str, Any]:
    """Master Orchestrator delegate node for Data Ingestion Sub-Graph."""
    logger.info("master_orchestrator_delegating_ingestion")
    return await ingestion_node(state)


async def master_orchestrator_quantitative_node(state: AgentState) -> Dict[str, Any]:
    """Master Orchestrator delegate node for Quantitative Sub-Graph."""
    logger.info("master_orchestrator_delegating_quantitative")
    return await quantitative_node(state)


async def master_orchestrator_qualitative_node(state: AgentState) -> Dict[str, Any]:
    """Master Orchestrator delegate node for Qualitative Sub-Graph."""
    logger.info("master_orchestrator_delegating_qualitative")
    return await qualitative_node(state)


def create_supervisor_workflow(checkpointer: Optional[Any] = None):
    """Build and compile the Master Orchestrator multi-agent LangGraph workflow with nested sub-graphs."""
    workflow = StateGraph(AgentState)

    ingestion_subgraph = create_ingestion_subgraph()
    quantitative_subgraph = create_quantitative_subgraph()
    qualitative_subgraph = create_qualitative_subgraph()

    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("ingestion_subgraph", ingestion_subgraph)
    workflow.add_node("quantitative_subgraph", quantitative_subgraph)
    workflow.add_node("qualitative_subgraph", qualitative_subgraph)

    workflow.add_node("research_agent", research_node)
    workflow.add_node("analysis_agent", analysis_node)
    workflow.add_node("verify_agent", verify_node)
    workflow.add_node("graph_agent", graph_node)
    workflow.add_node("macro_trends_agent", macro_trends_node)
    workflow.add_node("report_agent", report_node)
    workflow.add_node("human_escalation", human_escalation_node)

    workflow.set_entry_point("supervisor")

    workflow.add_conditional_edges(
        "supervisor",
        supervisor_router,
        {
            "research_agent": "research_agent",
            "analysis_agent": "analysis_agent",
            "verify_agent": "verify_agent",
            "graph_agent": "graph_agent",
            "macro_trends_agent": "macro_trends_agent",
            "report_agent": "report_agent",
            "human_escalation": "human_escalation",
            END: END,
        },
    )

    workflow.add_edge("research_agent", "supervisor")
    workflow.add_edge("analysis_agent", "supervisor")
    workflow.add_edge("verify_agent", "supervisor")
    workflow.add_edge("graph_agent", "supervisor")
    workflow.add_edge("macro_trends_agent", "supervisor")
    workflow.add_edge("report_agent", "supervisor")
    workflow.add_edge("human_escalation", END)

    return workflow.compile(checkpointer=checkpointer)


create_master_orchestrator_workflow = create_supervisor_workflow


