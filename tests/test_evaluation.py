import pytest

from backend.agents.verify import verify_node
from backend.agents.analysis import analysis_node
from backend.agents.state import AgentState


@pytest.mark.asyncio
async def test_citation_accuracy_metric():
    state: AgentState = {
        "messages": [],
        "company_ticker": "AAPL",
        "company_name": "Apple Inc.",
        "fiscal_year": 2025,
        "research_data": {
            "financial_extracts": {"revenue": 394_300_000_000},
            "retrieved_passages": [{"text": "Apple 10-K filing."}],
        },
        "analysis_results": {"revenue": 394_300_000_000, "profit_margin_pct": 24.6},
        "verified_claims": [],
        "graph_operations": [],
        "report_sections": {},
        "human_approval": True,
        "errors": [],
        "token_usage": {},
    }

    res = await verify_node(state)
    claims = res["verified_claims"]

    total_claims = len(claims)
    cited_claims = sum(1 for c in claims if c.get("source"))
    citation_accuracy = cited_claims / max(total_claims, 1)

    assert (
        citation_accuracy >= 0.95
    ), f"Citation accuracy {citation_accuracy} is below threshold 0.95"


@pytest.mark.asyncio
async def test_hallucination_rate_metric():
    state: AgentState = {
        "messages": [],
        "company_ticker": "NVDA",
        "company_name": "NVIDIA Corp",
        "fiscal_year": 2025,
        "research_data": {
            "financial_extracts": {"revenue": 60_000_000_000},
            "retrieved_passages": [{"text": "NVIDIA disclosures"}],
        },
        "analysis_results": {"revenue": 60_000_000_000, "profit_margin_pct": 45.0},
        "verified_claims": [],
        "graph_operations": [],
        "report_sections": {},
        "human_approval": True,
        "errors": [],
        "token_usage": {},
    }

    res = await verify_node(state)
    claims = res["verified_claims"]

    unverified_count = sum(1 for c in claims if c.get("status") == "UNVERIFIED_CLAIM")
    hallucination_rate = unverified_count / max(len(claims), 1)

    assert (
        hallucination_rate < 0.02
    ), f"Hallucination rate {hallucination_rate} exceeds threshold 0.02"


@pytest.mark.asyncio
async def test_financial_metric_precision_metric():
    state: AgentState = {
        "messages": [],
        "company_ticker": "MSFT",
        "company_name": "Microsoft Corporation",
        "fiscal_year": 2025,
        "research_data": {
            "financial_extracts": {
                "revenue": 245_000_000_000,
                "net_income": 88_000_000_000,
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
    analysis = res["analysis_results"]

    expected_margin = round((88_000_000_000 / 245_000_000_000) * 100, 2)
    actual_margin = analysis["profit_margin_pct"]

    precision = 1.0 if abs(expected_margin - actual_margin) < 0.01 else 0.0
    assert (
        precision >= 0.90
    ), f"Financial metric precision {precision} is below threshold 0.90"
