import time
import pytest
from langchain_core.messages import HumanMessage

from backend.agents.state import AgentState
from backend.core.cache import SemanticCacheManager
from backend.agents.cost_management import cost_management_node, calculate_token_cost, MAX_BUDGET_CAP
from backend.agents.supervisor import supervisor_router
from backend.agents.report import report_node


@pytest.mark.asyncio
async def test_semantic_cache_hit_and_miss():
    """Verify SemanticCacheManager returns cached payload for similarity > 0.98 and handles TTL expiration."""
    SemanticCacheManager.clear_cache()

    query1 = "What is the revenue growth rate and profit margin for NVIDIA Corporation in 2025?"
    query2 = "What is the revenue growth rate & profit margin for NVIDIA Corp in 2025?"
    query_different = "Tell me about Tesla battery storage production capacity and factories."

    payload = {"status": "SUCCESS", "ticker": "NVDA", "revenue_growth": "55%"}

    # Store query in cache
    SemanticCacheManager.set_cached_query(query1, payload, ttl_seconds=3600)

    # 1. High similarity match (> 0.98) -> Cache HIT
    hit_res = SemanticCacheManager.get_cached_query(query2, threshold=0.98)
    assert hit_res is not None
    assert hit_res["ticker"] == "NVDA"

    # 2. Low similarity query -> Cache MISS
    miss_res = SemanticCacheManager.get_cached_query(query_different, threshold=0.98)
    assert miss_res is None

    # 3. Expired TTL entry -> Cache MISS
    SemanticCacheManager.set_cached_query("Expired Query Test", {"data": "old"}, ttl_seconds=0)

    # Small delay to ensure TTL expiry
    time.sleep(0.05)

    expired_res = SemanticCacheManager.get_cached_query("Expired Query Test", ttl_seconds=0)
    assert expired_res is None


@pytest.mark.asyncio
async def test_cost_management_node_budget_tracking():
    """Verify CostManagementAgent computes API spend and enforces $1.50 budget cap."""
    token_usage = {
        "prompt_tokens": 100_000,
        "completion_tokens": 25_000,
        "total_tokens": 125_000,
    }

    cost = calculate_token_cost(token_usage)
    assert cost > 0.0
    assert cost < MAX_BUDGET_CAP

    state: AgentState = {
        "messages": [],
        "company_ticker": "AAPL",
        "company_name": "Apple Inc",
        "fiscal_year": 2025,
        "research_data": {},
        "analysis_results": {},
        "verified_claims": [],
        "graph_operations": [],
        "report_sections": {},
        "human_approval": True,
        "errors": [],
        "token_usage": token_usage,
    }

    res = await cost_management_node(state)
    assert res["budget_exceeded"] is False
    assert len(res["messages"]) > 0


@pytest.mark.asyncio
async def test_cost_management_node_circuit_breaker():
    """Verify CostManagementAgent triggers circuit breaker when token spend reaches $1.50 cap."""
    state: AgentState = {
        "messages": [],
        "company_ticker": "NVDA",
        "company_name": "NVIDIA Corp",
        "fiscal_year": 2025,
        "research_data": {},
        "analysis_results": {},
        "verified_claims": [],
        "graph_operations": [],
        "report_sections": {},
        "human_approval": True,
        "errors": [],
        "token_usage": {},
        "force_simulated_cost": 1.65,  # Exceeds $1.50 cap
    }

    res = await cost_management_node(state)
    assert res["budget_exceeded"] is True
    assert any("BUDGET_CAP_EXCEEDED" in str(e) for e in res["errors"])


@pytest.mark.asyncio
async def test_supervisor_router_budget_truncation():
    """Verify supervisor_router routes directly to report_agent when budget limit is reached."""
    state: AgentState = {
        "messages": [],
        "company_ticker": "AMZN",
        "company_name": "Amazon Inc",
        "fiscal_year": 2025,
        "research_data": {},
        "analysis_results": {},
        "verified_claims": [],
        "graph_operations": [],
        "report_sections": {},
        "human_approval": True,
        "errors": ["BUDGET_CAP_EXCEEDED: API spend reached $1.65 limit."],
        "budget_exceeded": True,
    }

    next_step = supervisor_router(state)
    assert next_step == "report_agent"


@pytest.mark.asyncio
async def test_report_node_budget_truncation_notice():
    """Verify report_node appends transparent system notice when report is compiled under budget cap truncation."""
    state: AgentState = {
        "messages": [],
        "company_ticker": "GOOGL",
        "company_name": "Alphabet Inc",
        "fiscal_year": 2025,
        "research_data": {"company_profile": "Search & Cloud Leader"},
        "analysis_results": {
            "profit_margin_pct": 24.0,
            "financial_risk_score": 15.0,
            "risk_rating": "Low Risk",
        },
        "verified_claims": [],
        "graph_operations": [],
        "report_sections": {},
        "human_approval": True,
        "errors": ["BUDGET_CAP_EXCEEDED: API spend reached $1.55 limit."],
        "budget_exceeded": True,
    }

    res = await report_node(state)
    assert "report_sections" in res
    rep = res["report_sections"]
    assert "budget_truncation_warning" in rep
    assert "[SYSTEM NOTICE: Report compiled under API Budget Truncation Cap" in rep["executive_summary"]
