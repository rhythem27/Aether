import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.models.research import ResearchRequest, ResearchResponse, JobStatus

client = TestClient(app)

def test_research_models():
    req = ResearchRequest(target_company="AAPL", research_depth="deep")
    assert req.target_company == "AAPL"
    assert req.research_depth == "deep"
    assert "sec_edgar" in req.data_sources

def test_initiate_deep_dive_api():
    payload = {
        "target_company": "NVDA",
        "research_depth": "standard",
        "focus_areas": ["financials", "risk"],
        "data_sources": ["sec_edgar", "news"]
    }
    response = client.post("/api/v1/research/deep-dive", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "queued"
    assert "/api/v1/research/jobs/" in data["poll_endpoint"]
    assert "/api/v1/research/ws/" in data["websocket_endpoint"]

    job_id = data["job_id"]

    # Poll status endpoint
    poll_resp = client.get(f"/api/v1/research/jobs/{job_id}")
    assert poll_resp.status_code == 200
    job_data = poll_resp.json()
    assert job_data["job_id"] == job_id
    assert job_data["target_company"] == "NVDA"

    # List jobs endpoint
    list_resp = client.get("/api/v1/research/jobs")
    assert list_resp.status_code == 200
    jobs = list_resp.json()
    assert len(jobs) > 0
    assert any(j["job_id"] == job_id for j in jobs)

def test_websocket_streaming_endpoint():
    # 1. Enqueue a job
    resp = client.post("/api/v1/research/deep-dive", json={"target_company": "TSLA"})
    assert resp.status_code == 202
    job_id = resp.json()["job_id"]

    # 2. Connect via WebSocket
    with client.websocket_connect(f"/api/v1/research/ws/{job_id}") as websocket:
        data = websocket.receive_json()
        assert "event" in data
        assert data["job_id"] == job_id
