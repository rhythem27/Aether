import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.agents.provenance import create_provenance_record, compute_sha256
from backend.agents.audit_export import generate_compliance_trace, audit_export_node
from backend.db.postgres import (
    append_provenance_records,
    get_provenance_records_by_report_id,
    InMemoryPostgresLedger,
)

test_client = TestClient(app)


def test_provenance_record_creation_and_cryptographic_signature():
    record = create_provenance_record(
        agent_name="research_agent",
        model_id="gpt-4o-mini",
        prompt_text="Gather SEC EDGAR 10-K filings for AAPL",
        source_doc_ids=["chunk_aapl_1", "chunk_aapl_2"],
        previous_hash="GENESIS_BLOCK",
    )

    assert "record_id" in record
    assert record["agent_name"] == "research_agent"
    assert record["model_id"] == "gpt-4o-mini"
    assert record["prompt_hash"] == compute_sha256("Gather SEC EDGAR 10-K filings for AAPL")
    assert record["previous_hash"] == "GENESIS_BLOCK"
    assert len(record["signature_hash"]) == 64
    assert len(record["source_doc_ids"]) == 2


@pytest.mark.asyncio
async def test_append_only_postgres_ledger():
    report_id = "test_rep_123"
    company_ticker = "AAPL"

    r1 = create_provenance_record(
        agent_name="research_agent",
        model_id="gpt-4o-mini",
        prompt_text="Step 1",
        source_doc_ids=["doc_1"],
    )

    r2 = create_provenance_record(
        agent_name="analysis_agent",
        model_id="gpt-4o-mini",
        prompt_text="Step 2",
        source_doc_ids=["doc_2"],
        previous_hash=r1["signature_hash"],
    )

    count = await append_provenance_records(
        report_id=report_id,
        company_ticker=company_ticker,
        records=[r1, r2],
    )

    assert count == 2

    fetched = await get_provenance_records_by_report_id(report_id=report_id)
    assert len(fetched) >= 2
    record_ids = [f["record_id"] for f in fetched]
    assert r1["record_id"] in record_ids
    assert r2["record_id"] in record_ids


def test_compliance_trace_artifact_generation():
    prov_record = create_provenance_record(
        agent_name="verify_agent",
        model_id="gpt-4o-mini",
        prompt_text="Verify revenue statement",
        source_doc_ids=["aapl_10k.pdf"],
    )

    state = {
        "company_ticker": "AAPL",
        "company_name": "Apple Inc.",
        "provenance_chain": [prov_record],
        "verified_claims": [
            {
                "claim": "Revenue was $90 billion",
                "status": "VERIFIED",
                "source": "SEC EDGAR Form 10-K",
            }
        ],
        "research_data": {
            "retrieved_passages": [{"source_file": "aapl_10k.pdf"}]
        },
    }

    trace = generate_compliance_trace(state, report_id="rep_aapl_test")

    assert trace["report_id"] == "rep_aapl_test"
    assert trace["company_ticker"] == "AAPL"
    assert trace["sebi_compliance_status"] == "COMPLIANT"
    assert len(trace["provenance_chain"]) == 1
    assert len(trace["claims_audit_map"]) == 1
    assert trace["claims_audit_map"][0]["verification_status"] == "VERIFIED"


@pytest.mark.asyncio
async def test_audit_export_node_execution():
    r1 = create_provenance_record(
        agent_name="research_agent",
        prompt_text="Gather data",
    )

    state = {
        "company_ticker": "TSLA",
        "company_name": "Tesla Inc.",
        "provenance_chain": [r1],
        "verified_claims": [],
        "research_data": {},
        "report_sections": {},
        "errors": [],
    }

    res = await audit_export_node(state)
    assert "provenance_chain" in res
    assert "report_sections" in res
    rep_sections = res["report_sections"]
    assert "compliance_trace" in rep_sections
    trace = rep_sections["compliance_trace"]
    assert trace["company_ticker"] == "TSLA"
    assert trace["sebi_compliance_status"] == "COMPLIANT"


def test_fastapi_compliance_trace_endpoint():
    # Seed ledger with test record
    rec = create_provenance_record(
        agent_name="research_agent",
        prompt_text="API endpoint test",
    )
    InMemoryPostgresLedger.get_instance().append(
        report_id="rep_api_test_404",
        company_ticker="NVDA",
        record=rec,
    )

    resp = test_client.get("/api/v1/reports/rep_api_test_404/compliance-trace")
    assert resp.status_code == 200
    data = resp.json()
    assert data["report_id"] == "rep_api_test_404"
    assert data["company_ticker"] == "NVDA"
    assert data["sebi_compliance_status"] == "COMPLIANT"
    assert data["total_provenance_records"] >= 1
