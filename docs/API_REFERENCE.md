# Aether API Specification & Endpoint Reference

Complete documentation for **Aether** REST API routes and WebSocket live log streaming interfaces.

---

## 🟢 System Health & Readiness

### `GET /health`
Returns system status and individual status of attached databases.

* **Response (`200 OK`):**
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "services": {
    "qdrant": "healthy",
    "neo4j": "healthy",
    "postgres": "healthy",
    "redis": "healthy"
  }
}
```

### `GET /ready`
Kubernetes readiness probe returning HTTP `200 OK`.

---

## 📄 Document Ingestion & RAG Queries

### `POST /api/v1/documents/upload`
Uploads, parses (`unstructured`), chunks, vectorizes, and indexes a financial document into Qdrant.

* **Form Data Parameters:**
  * `file`: UploadFile (PDF, HTML, DOCX, TXT)
  * `company_ticker`: String (optional, e.g. `NVDA`)
  * `company_name`: String (optional, e.g. `NVIDIA Corporation`)
  * `fiscal_year`: Integer (optional, e.g. `2025`)
  * `document_type`: String (default `"general"`)

* **Response (`201 Created`):**
```json
{
  "filename": "NVDA_10K_2025.pdf",
  "total_chunks": 42,
  "document_type": "financial_report",
  "company_ticker": "NVDA",
  "fiscal_year": 2025,
  "status": "indexed"
}
```

### `POST /api/v1/documents/query`
Executes hybrid dense+sparse vector search with payload metadata filtering.

* **Request Body:**
```json
{
  "query": "What are NVIDIA's gross margin risks?",
  "top_k": 5,
  "company_ticker": "NVDA",
  "fiscal_year": 2025
}
```

---

## 🤖 Multi-Agent Research Jobs

### `POST /api/v1/research/deep-dive`
Enqueues an asynchronous multi-agent due diligence research job.

* **Request Body:**
```json
{
  "target_company": "NVDA",
  "research_depth": "standard",
  "focus_areas": ["financials", "competition", "leadership", "risk"],
  "data_sources": ["sec_edgar", "crunchbase", "news"],
  "output_format": "markdown",
  "human_review_gates": ["high_risk_claims"]
}
```

* **Response (`202 Accepted`):**
```json
{
  "job_id": "job_a1b2c3d4e5f6",
  "status": "queued",
  "estimated_duration_seconds": 180,
  "poll_endpoint": "/api/v1/research/jobs/job_a1b2c3d4e5f6",
  "created_at": "2026-08-12T12:00:00Z"
}
```

### `GET /api/v1/research/jobs/{job_id}`
Polls job execution progress, current active agent, agent activity trail, and completed report.

---

## ⚡ Live WebSocket Streaming

### `WS /api/v1/ws/{job_id}`
Establishes a real-time WebSocket connection to stream agent activities, state updates, and thinking logs.

* **Event Frame Example:**
```json
{
  "job_id": "job_a1b2c3d4e5f6",
  "agent_name": "research_agent",
  "activity_type": "tool_call",
  "description": "Calling SEC EDGAR tool for 10-K filing",
  "timestamp": "2026-08-12T12:00:05Z",
  "progress_pct": 35.0
}
```
