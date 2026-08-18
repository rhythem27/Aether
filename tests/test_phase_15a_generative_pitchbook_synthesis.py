import os
import pytest
from fastapi.testclient import TestClient

from backend.agents.state import AgentState
from backend.reports.pptx_templates import PPTXTemplateManager
from backend.agents.deck_synthesis import deck_synthesis_node
from backend.agents.report import report_node
from backend.api.main import app


@pytest.mark.asyncio
async def test_pptx_template_manager_deck_creation(tmp_path):
    """Verify PPTXTemplateManager generates a valid corporate .pptx deck."""
    output_file = str(tmp_path / "NVDA_Pitchbook_Test.pptx")

    path = PPTXTemplateManager.create_corporate_pitchbook(
        ticker="NVDA",
        company_name="NVIDIA Corporation",
        executive_summary="NVIDIA GPU dominance drives AI data center hyper-growth.",
        financial_ratios={"profit_margin_pct": 55.0},
        valuation_multiples={"pe_ratio": 45.0, "ev_ebitda": 38.0},
        risk_matrix={"financial_risk_score": 12.0, "risk_rating": "Low Risk"},
        sentiment_momentum={"momentum_direction": "BULLISH_EXPANSION", "sentiment_momentum_score": 0.65},
        graph_summary={"nodes_committed": 8, "relationships_committed": 6},
        output_path=output_file,
    )

    assert os.path.exists(path)
    assert os.path.getsize(path) > 0


@pytest.mark.asyncio
async def test_deck_synthesis_node_execution():
    """Verify DeckSynthesisAgent node transforms AgentState into pitch book presentation."""
    initial_state: AgentState = {
        "messages": [],
        "company_ticker": "AAPL",
        "company_name": "Apple Inc",
        "fiscal_year": 2025,
        "research_data": {},
        "analysis_results": {
            "profit_margin_pct": 26.5,
            "pe_ratio": 29.1,
            "ev_ebitda": 23.4,
            "financial_risk_score": 14.0,
            "risk_rating": "Low Risk",
            "sentiment_momentum": {
                "momentum_direction": "BULLISH_EXPANSION",
                "sentiment_momentum_score": 0.52,
            },
        },
        "verified_claims": [],
        "graph_operations": [{"nodes_committed": 5, "relationships_committed": 4}],
        "report_sections": {
            "executive_summary": "Apple ecosystem monetization continues steady expansion."
        },
        "human_approval": True,
        "errors": [],
        "token_usage": {},
    }

    res = await deck_synthesis_node(initial_state)
    assert "report_sections" in res
    rep = res["report_sections"]
    assert "pitchbook_deck_path" in rep
    assert os.path.exists(rep["pitchbook_deck_path"])
    assert rep["pitchbook_status"] == "GENERATED"


@pytest.mark.asyncio
async def test_report_node_generates_pitchbook():
    """Verify Report Agent synthesizes both textual report and .pptx pitch book."""
    state: AgentState = {
        "messages": [],
        "company_ticker": "MSFT",
        "company_name": "Microsoft Corp",
        "fiscal_year": 2025,
        "research_data": {"company_profile": "Hyperscale Cloud & AI Leader"},
        "analysis_results": {
            "profit_margin_pct": 36.0,
            "financial_risk_score": 10.0,
            "risk_rating": "Low Risk",
        },
        "verified_claims": [
            {
                "claim": "Azure growth verified",
                "source": "SEC EDGAR 10-K",
                "status": "VERIFIED",
                "confidence_score": 0.98,
            }
        ],
        "graph_operations": [{"nodes_committed": 6, "relationships_committed": 5}],
        "report_sections": {},
        "human_approval": True,
        "errors": [],
        "token_usage": {},
    }

    res = await report_node(state)
    assert "report_sections" in res
    rep = res["report_sections"]
    assert rep["status"] == "FINALIZED"
    assert "pitchbook_deck_path" in rep
    assert os.path.exists(rep["pitchbook_deck_path"])


def test_fastapi_download_deck_endpoint():
    """Verify FastAPI /api/v1/reports/{id}/download-deck endpoint serves .pptx presentation file."""
    client = TestClient(app)
    response = client.get("/api/v1/reports/report_nvda/download-deck")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    assert len(response.content) > 0
