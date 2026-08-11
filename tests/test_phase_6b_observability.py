import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.agents.state import AgentState
from backend.agents.verify import high_risk_validator_node
from backend.core.observability import observe_agent

client = TestClient(app)

def test_prometheus_metrics_endpoint():
    response = client.get("/metrics")
    assert response.status_code == 200
    text = response.text
    assert "aether_research_jobs_total" in text
    assert "aether_active_research_jobs" in text

@pytest.mark.asyncio
async def test_high_risk_validator_node_pass():
    state: AgentState = {
        "messages": [],
        "company_ticker": "AAPL",
        "company_name": "Apple Inc.",
        "fiscal_year": 2025,
        "research_data": {},
        "analysis_results": {},
        "verified_claims": [{"claim": "Revenue verified", "status": "VERIFIED"}],
        "graph_operations": [],
        "report_sections": {},
        "human_approval": True,
        "errors": [],
        "token_usage": {}
    }

    res = await high_risk_validator_node(state)
    assert res["human_approval"] is True
    assert len(res["messages"]) == 1

@pytest.mark.asyncio
async def test_observe_agent_decorator():
    @observe_agent(agent_name="test_agent")
    async def sample_node(state: dict):
        return {"output": "ok"}

    res = await sample_node({"company_ticker": "AAPL"})
    assert res["output"] == "ok"
