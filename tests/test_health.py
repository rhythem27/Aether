import pytest
from fastapi.testclient import TestClient
from backend.api.main import app
from backend.core.config import settings

client = TestClient(app)

def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == settings.PROJECT_NAME
    assert data["version"] == settings.VERSION

def test_readiness_probe():
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "services" in data
    assert "qdrant" in data["services"]
    assert "neo4j" in data["services"]
    assert "postgres" in data["services"]
    assert "redis" in data["services"]

@pytest.mark.asyncio
async def test_sec_edgar_mcp_tools():
    from backend.mcp.servers.sec_edgar import search_filings, extract_financials, get_company_profile
    
    filings = await search_filings("AAPL", "10-K", 2)
    assert isinstance(filings, list)
    assert len(filings) > 0
    
    financials = await extract_financials("https://example.com/filing")
    assert "revenue" in financials
    assert "net_income" in financials
    
    profile = await get_company_profile("AAPL")
    assert "AAPL" in profile
