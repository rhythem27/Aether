import pytest
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from backend.agents.state import AgentState
from backend.agents.verify import verify_node
from backend.agents.graph_builder import graph_node
from backend.agents.report import report_node
from backend.agents.supervisor import create_supervisor_workflow


@pytest.mark.asyncio
async def test_verify_node_audit():
    state: AgentState = {
        "messages": [],
        "company_ticker": "NVDA",
        "company_name": "NVIDIA Corp",
        "fiscal_year": 2025,
        "research_data": {
            "financial_extracts": {"revenue": 60_000_000_000},
            "retrieved_passages": [{"text": "NVIDIA GPU sales doubled."}],
        },
        "analysis_results": {
            "revenue": 60_000_000_000,
            "profit_margin_pct": 45.0,
            "financial_risk_score": 15.0,
            "risk_rating": "Low Risk",
        },
        "verified_claims": [],
        "graph_operations": [],
        "report_sections": {},
        "human_approval": True,
        "errors": [],
        "token_usage": {},
    }

    res = await verify_node(state)
    assert "verified_claims" in res
    claims = res["verified_claims"]
    assert len(claims) >= 2
    assert any(c["status"] == "VERIFIED" for c in claims)


@pytest.mark.asyncio
async def test_graph_node_operations():
    state: AgentState = {
        "messages": [],
        "company_ticker": "AAPL",
        "company_name": "Apple Inc.",
        "fiscal_year": 2025,
        "research_data": {
            "company_profile": "Apple Inc. acquired Beats Electronics.",
            "retrieved_passages": [],
        },
        "analysis_results": {},
        "verified_claims": [],
        "graph_operations": [],
        "report_sections": {},
        "human_approval": True,
        "errors": [],
        "token_usage": {},
    }

    res = await graph_node(state)
    assert "graph_operations" in res
    ops = res["graph_operations"]
    assert len(ops) > 0
    assert ops[0]["operation"] == "BULK_UPSERT"


@pytest.mark.asyncio
async def test_report_node_synthesis():
    state: AgentState = {
        "messages": [],
        "company_ticker": "AAPL",
        "company_name": "Apple Inc.",
        "fiscal_year": 2025,
        "research_data": {"company_profile": "Leading Tech Company"},
        "analysis_results": {
            "profit_margin_pct": 25.0,
            "risk_rating": "Low Risk",
            "financial_risk_score": 15.0,
        },
        "verified_claims": [
            {
                "claim": "Revenue verified",
                "source": "10-K",
                "status": "VERIFIED",
                "confidence_score": 0.98,
            }
        ],
        "graph_operations": [{"nodes_committed": 2, "relationships_committed": 1}],
        "report_sections": {},
        "human_approval": True,
        "errors": [],
        "token_usage": {},
    }

    res = await report_node(state)
    assert "report_sections" in res
    rep = res["report_sections"]
    assert "executive_summary" in rep
    assert "risk_matrix" in rep
    assert rep["status"] == "FINALIZED"


@pytest.mark.asyncio
async def test_full_6_agent_swarm_workflow_with_checkpointer():
    memory = MemorySaver()
    app = create_supervisor_workflow(checkpointer=memory)

    config = {"configurable": {"thread_id": "test_thread_1"}}
    initial_state: AgentState = {
        "messages": [HumanMessage(content="Perform full due diligence on NVDA")],
        "company_ticker": "NVDA",
        "company_name": "NVIDIA Corporation",
        "fiscal_year": 2025,
        "research_data": {},
        "analysis_results": {},
        "verified_claims": [],
        "graph_operations": [],
        "report_sections": {},
        "human_approval": True,
        "errors": [],
        "token_usage": {},
    }

    final_state = await app.ainvoke(initial_state, config=config)

    # Verify state output across all 6 agents
    assert len(final_state["research_data"]) > 0
    assert len(final_state["analysis_results"]) > 0
    assert len(final_state["verified_claims"]) > 0
    assert len(final_state["graph_operations"]) > 0
    assert final_state["report_sections"]["status"] == "FINALIZED"

    # Verify checkpointer persistence
    checkpointed_state = await app.aget_state(config)
    assert checkpointed_state.values["company_ticker"] == "NVDA"
    assert checkpointed_state.values["report_sections"]["status"] == "FINALIZED"
