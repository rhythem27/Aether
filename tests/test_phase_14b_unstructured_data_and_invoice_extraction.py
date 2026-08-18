import pytest
from langchain_core.messages import HumanMessage

from backend.agents.state import AgentState
from backend.rag.vlm_extractor import VLMExtractionService, InvoiceExtractionSchema
from backend.agents.document_extraction import document_extraction_node
from backend.agents.subgraphs.ingestion import ingestion_node
from backend.agents.verify import verify_node, high_risk_validator_node


@pytest.mark.asyncio
async def test_vlm_extraction_service_schema_validation():
    """Verify VLM Extraction Service returns structured Pydantic InvoiceExtractionSchema."""
    service = VLMExtractionService()
    res = await service.extract_invoice_async(file_path="invoice_clean_sample.pdf")

    assert isinstance(res, InvoiceExtractionSchema)
    assert res.vendor_name == "Enterprise Cloud Systems Inc"
    assert res.invoice_number == "INV-2025-88492"
    assert len(res.line_items) == 2
    assert res.net_total == 19980.00
    assert res.overall_confidence > 0.90
    assert all(score >= 0.90 for score in res.confidence_scores.values())


@pytest.mark.asyncio
async def test_vlm_degraded_invoice_extraction():
    """Verify VLM Extraction Service correctly flags degraded invoice fields with < 90% confidence."""
    service = VLMExtractionService()
    res = await service.extract_invoice_async(
        file_path="scanned_blurry_receipt.png", force_low_confidence=True
    )

    assert isinstance(res, InvoiceExtractionSchema)
    assert res.confidence_scores["invoice_number"] < 0.90
    assert res.confidence_scores["transaction_date"] < 0.90
    assert res.overall_confidence < 0.90


@pytest.mark.asyncio
async def test_document_extraction_agent_node():
    """Verify Document Extraction Agent node updates research_data with extracted invoices."""
    initial_state: AgentState = {
        "messages": [],
        "company_ticker": "NVDA",
        "company_name": "NVIDIA Corp",
        "fiscal_year": 2025,
        "research_data": {
            "document_paths": ["nvda_supplier_invoice_2025.pdf"]
        },
        "analysis_results": {},
        "verified_claims": [],
        "graph_operations": [],
        "report_sections": {},
        "human_approval": True,
        "errors": [],
        "token_usage": {},
    }

    res = await document_extraction_node(initial_state)
    assert "research_data" in res
    invoices = res["research_data"]["extracted_invoices"]
    assert len(invoices) >= 1
    assert invoices[0]["vendor_name"] == "Enterprise Cloud Systems Inc"
    assert invoices[0]["net_total"] > 0


@pytest.mark.asyncio
async def test_ingestion_subgraph_with_document_extraction():
    """Verify Data Ingestion Sub-Graph executes DocumentExtractionAgent in the pipeline."""
    initial_state: AgentState = {
        "messages": [HumanMessage(content="Ingest NVDA supplier invoices")],
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
    }

    res = await ingestion_node(initial_state)
    assert "research_data" in res
    assert "extracted_invoices" in res["research_data"]
    assert len(res["research_data"]["extracted_invoices"]) > 0


@pytest.mark.asyncio
async def test_hitl_gate_low_confidence_invoice_routing():
    """Verify low-confidence invoice fields (< 90%) trigger the HITL interrupt gate before database commit."""
    # 1. Simulate state with degraded invoice extraction (< 90% confidence fields)
    service = VLMExtractionService()
    degraded_inv = await service.extract_invoice_async(
        file_path="degraded_receipt.png", force_low_confidence=True
    )

    state: AgentState = {
        "messages": [],
        "company_ticker": "MSFT",
        "company_name": "Microsoft Corp",
        "fiscal_year": 2025,
        "research_data": {
            "extracted_invoices": [degraded_inv.model_dump()]
        },
        "analysis_results": {},
        "verified_claims": [],
        "graph_operations": [],
        "report_sections": {},
        "human_approval": True,
        "errors": [],
        "token_usage": {},
    }

    # 2. Run verify_node -> should tag low-confidence fields as UNVERIFIED_CLAIM
    verify_res = await verify_node(state)
    claims = verify_res["verified_claims"]
    unverified = [c for c in claims if c["status"] == "UNVERIFIED_CLAIM"]
    assert len(unverified) >= 1
    assert any("invoice_number" in c["claim"] or "< 90%" in c["claim"] for c in unverified)

    # 3. Run high_risk_validator_node -> should trigger HITL gate and withhold human approval until manual review
    state["verified_claims"] = claims
    hitl_res = await high_risk_validator_node(state)
    assert hitl_res["human_approval"] is False
    assert "HITL" in hitl_res["messages"][0].content
