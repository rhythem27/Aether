import pytest
from langchain_core.messages import HumanMessage

from backend.agents.state import AgentState
from backend.agents.supervisor import supervisor_router, create_supervisor_workflow
from backend.agents.research import research_node
from backend.agents.analysis import analysis_node


def test_agent_state_initialization():
    state: AgentState = {
        "messages": [HumanMessage(content="Analyze AAPL")],
        "company_ticker": "AAPL",
        "company_name": "Apple Inc.",
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
    assert state["company_ticker"] == "AAPL"
    assert len(state["messages"]) == 1


def test_supervisor_router_branching():
    state: AgentState = {
        "messages": [],
        "company_ticker": "NVDA",
        "company_name": "NVIDIA",
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

    # 1. First step should route to research_agent
    assert supervisor_router(state) == "research_agent"

    # 2. Add research_data -> should route to analysis_agent
    state["research_data"] = {"ticker": "NVDA"}
    assert supervisor_router(state) == "analysis_agent"

    # 3. Add analysis_results -> should route to verify_agent
    state["analysis_results"] = {"risk_score": 20}
    assert supervisor_router(state) == "verify_agent"

    # 4. Error escalation: >2 errors -> human_escalation
    state["errors"] = ["Error 1", "Error 2", "Error 3"]
    assert supervisor_router(state) == "human_escalation"


@pytest.mark.asyncio
async def test_research_node():
    state: AgentState = {
        "messages": [],
        "company_ticker": "AAPL",
        "company_name": "Apple Inc.",
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
    res = await research_node(state)
    assert "research_data" in res
    assert res["research_data"]["ticker"] == "AAPL"
    assert len(res["messages"]) == 1


@pytest.mark.asyncio
async def test_analysis_node():
    state: AgentState = {
        "messages": [],
        "company_ticker": "TSLA",
        "company_name": "Tesla Motors",
        "fiscal_year": 2025,
        "research_data": {
            "financial_extracts": {
                "revenue": 90_000_000_000,
                "net_income": 12_000_000_000,
            }
        },
        "analysis_results": {},
        "verified_claims": [],
        "graph_operations": [],
        "report_sections": {},
        "human_approval": True,
        "errors": [],
        "token_usage": {},
    }
    res = await analysis_node(state)
    assert "analysis_results" in res
    results = res["analysis_results"]
    assert results["profit_margin_pct"] > 0
    assert "financial_risk_score" in results


@pytest.mark.asyncio
async def test_full_supervisor_workflow_execution():
    app = create_supervisor_workflow()
    initial_state: AgentState = {
        "messages": [HumanMessage(content="Perform due diligence on AAPL")],
        "company_ticker": "AAPL",
        "company_name": "Apple Inc.",
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

    final_state = await app.ainvoke(initial_state)
    assert len(final_state["research_data"]) > 0
    assert len(final_state["analysis_results"]) > 0
    assert len(final_state["verified_claims"]) > 0
    assert len(final_state["graph_operations"]) > 0
    assert len(final_state["report_sections"]) > 0
