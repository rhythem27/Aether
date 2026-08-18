import os
import pytest
import openpyxl
from fastapi.testclient import TestClient

from backend.agents.state import AgentState
from backend.reports.excel_modeler import ExcelModelerEngine
from backend.agents.financial_modeling import financial_modeling_node
from backend.agents.subgraphs.quantitative import quantitative_node
from backend.api.main import app


@pytest.mark.asyncio
async def test_excel_modeler_engine_formulas(tmp_path):
    """Verify ExcelModelerEngine builds Three-Statement .xlsx workbook with native formulas."""
    output_file = str(tmp_path / "NVDA_Three_Statement_Test.xlsx")

    path = ExcelModelerEngine.create_three_statement_model(
        ticker="NVDA",
        company_name="NVIDIA Corporation",
        revenue=60_000_000_000,
        net_income=30_000_000_000,
        growth_rate_pct=12.0,
        output_path=output_file,
    )

    assert os.path.exists(path)

    # Load workbook and inspect formulas
    wb = openpyxl.load_workbook(path, data_only=False)
    sheet_names = wb.sheetnames
    assert "Income Statement" in sheet_names
    assert "Balance Sheet" in sheet_names
    assert "Cash Flow Statement" in sheet_names
    assert "Assumption Grounding Audit" in sheet_names

    ws_is = wb["Income Statement"]
    # Check projection formula in cell D4
    assert str(ws_is["D4"].value).startswith("=")
    # Check Gross Profit formula in cell C6
    assert str(ws_is["C6"].value) == "=C4-C5"
    # Check Profit Margin formula in cell C12
    assert str(ws_is["C12"].value) == "=C10/C4"

    ws_bs = wb["Balance Sheet"]
    # Check Total Assets formula in cell C7
    assert str(ws_bs["C7"].value) == "=SUM(C4:C6)"


@pytest.mark.asyncio
async def test_financial_modeling_agent_node():
    """Verify FinancialModelingAgent node processes AgentState and audits Qdrant assumptions."""
    initial_state: AgentState = {
        "messages": [],
        "company_ticker": "TSLA",
        "company_name": "Tesla Inc",
        "fiscal_year": 2025,
        "research_data": {
            "financial_extracts": {"revenue": 96_000_000_000, "net_income": 15_000_000_000},
            "retrieved_passages": [{"text": "Tesla revenue growth driven by EV deliveries."}],
        },
        "analysis_results": {
            "revenue": 96_000_000_000,
            "net_income": 15_000_000_000,
            "estimated_yoy_growth_pct": 10.5,
        },
        "verified_claims": [
            {
                "claim": "TSLA Revenue verified",
                "source": "10-K",
                "status": "VERIFIED",
                "confidence_score": 0.98,
            }
        ],
        "graph_operations": [],
        "report_sections": {},
        "human_approval": True,
        "errors": [],
        "token_usage": {},
    }

    res = await financial_modeling_node(initial_state)
    assert "report_sections" in res
    rep = res["report_sections"]
    assert "financial_model_excel_path" in rep
    assert os.path.exists(rep["financial_model_excel_path"])
    assert rep["financial_model_status"] == "GENERATED"


@pytest.mark.asyncio
async def test_quantitative_subgraph_with_excel_modeling():
    """Verify Quantitative Sub-Graph executes ratio calculator, valuation model, risk score, and financial modeling."""
    initial_state: AgentState = {
        "messages": [],
        "company_ticker": "AAPL",
        "company_name": "Apple Inc",
        "fiscal_year": 2025,
        "research_data": {
            "financial_extracts": {"revenue": 380_000_000_000, "net_income": 95_000_000_000}
        },
        "analysis_results": {},
        "verified_claims": [],
        "graph_operations": [],
        "report_sections": {},
        "human_approval": True,
        "errors": [],
        "token_usage": {},
    }

    res = await quantitative_node(initial_state)
    assert "analysis_results" in res
    anal = res["analysis_results"]
    assert anal["profit_margin_pct"] > 0
    assert "report_sections" in res
    assert "financial_model_excel_path" in res["report_sections"]
    assert os.path.exists(res["report_sections"]["financial_model_excel_path"])


def test_fastapi_excel_model_download_endpoint():
    """Verify FastAPI /api/v1/reports/{id}/excel-model endpoint serves .xlsx financial model file."""
    client = TestClient(app)
    response = client.get("/api/v1/reports/report_tsla/excel-model")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert len(response.content) > 0
