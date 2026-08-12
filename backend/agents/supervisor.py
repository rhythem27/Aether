from typing import Any, Dict, Optional
from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph, END
import structlog

from backend.agents.state import AgentState
from backend.agents.research import research_node
from backend.agents.analysis import analysis_node
from backend.agents.verify import verify_node
from backend.agents.graph_builder import graph_node
from backend.agents.report import report_node

logger = structlog.get_logger(__name__)


async def supervisor_node(state: AgentState) -> Dict[str, Any]:
    """Supervisor Agent: Decomposes tasks, validates inputs, and plans next steps."""
    ticker = state.get("company_ticker", "UNKNOWN")
    logger.info("supervisor_node_executing", ticker=ticker)

    ai_msg = AIMessage(content=f"[Supervisor Agent] Planning execution for {ticker}.")
    return {"messages": [ai_msg]}


def supervisor_router(state: AgentState) -> str:
    """Routing edge logic for Supervisor Plan-Execute workflow."""
    errors = state.get("errors", [])
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


def create_supervisor_workflow(checkpointer: Optional[Any] = None):
    """Build and compile the multi-agent LangGraph workflow with optional checkpointer persistence."""
    workflow = StateGraph(AgentState)

    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("research_agent", research_node)
    workflow.add_node("analysis_agent", analysis_node)
    workflow.add_node("verify_agent", verify_node)
    workflow.add_node("graph_agent", graph_node)
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
            "report_agent": "report_agent",
            "human_escalation": "human_escalation",
            END: END,
        },
    )

    # Return to supervisor after each agent step
    workflow.add_edge("research_agent", "supervisor")
    workflow.add_edge("analysis_agent", "supervisor")
    workflow.add_edge("verify_agent", "supervisor")
    workflow.add_edge("graph_agent", "supervisor")
    workflow.add_edge("report_agent", "supervisor")
    workflow.add_edge("human_escalation", END)

    return workflow.compile(checkpointer=checkpointer)
