# Aether: Autonomous Multi-Agent Financial Intelligence Platform

[![CI Pipeline](https://github.com/aether/aether/actions/workflows/ci.yml/badge.svg)](https://github.com/aether/aether/actions/workflows/ci.yml)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-Multi--Agent-orange.svg)](https://github.com/langchain-ai/langgraph)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Aether** is an enterprise-grade autonomous multi-agent financial intelligence and due diligence platform. Powered by **LangGraph**, **Model Context Protocol (MCP)**, **Qdrant Vector Database**, and **Neo4j GraphRAG**, Aether automates deep financial analysis, SEC filing audits, and corporate entity relationship extraction with human-in-the-loop safety verification.

---

## 🎯 Key Recruiter & Engineering Highlights

Here are 5 core architectural achievements implemented in this project:

1. 🤖 **LangGraph Supervisor Orchestration:** Built a stateful multi-agent system featuring 6 specialized agents orchestrated by a dynamic Supervisor router with typed state persistence backed by PostgreSQL checkpointers.
2. 🔌 **Model Context Protocol (MCP) Native:** Built custom FastMCP servers (SEC EDGAR, Crunchbase, NewsAPI, Neo4j), decoupling data tool execution from LLM agent logic via JSON-RPC protocol compliance.
3. 🕸️ **GraphRAG Hybrid Retrieval:** Solved key financial RAG limitations by combining Qdrant dense vector similarity (Cosine, 1024-dim) with Neo4j 2-hop graph traversal and GDS Louvain community detection, fused via Reciprocal Rank Fusion (RRF).
4. 📊 **Observability & Evaluation Suite:** Integrated end-to-end tracing via **Langfuse** `@observe()`, real-time Prometheus metrics, and automated Pytest evaluation benchmarks for hallucination and citation accuracy.
5. 🛡️ **Human-in-the-Loop Checkpoints:** Integrated `interrupt()` state validation gates before high-risk financial claims or valuation metrics are finalized into due diligence reports.

---

## 🚀 Quick Start Guide

Follow these commands to set up and launch Aether on your local environment:

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/aether.git
cd aether

# 2. Install dependencies via Poetry
poetry install

# 3. Configure environment variables
cp .env.example .env

# 4. Spin up infrastructure services (Qdrant, Neo4j, Redis, Postgres, Langfuse)
docker compose up -d

# 5. Run initial database schema migrations
poetry run python -m backend.db.init_db

# 6. Start the FastAPI backend API server
poetry run uvicorn backend.api.main:app --reload --host 0.0.0.0 --port 8000

# 7. Start the Celery research worker node
poetry run celery -A backend.workers.research_tasks worker --loglevel=info --concurrency=4

# 8. Execute test suite with coverage report
poetry run pytest --cov=backend --cov-report=html
```

---

## 📐 Architecture Decision Records (ADRs)

Our design choices and technical trade-offs are documented cleanly in `docs/adr/`:

* 📄 **[ADR 0001: Model Context Protocol (MCP) Adoption](file:///c:/git-hub/Aether/docs/adr/0001-mcp-adoption.md)** — Standardizing external data tooling via FastMCP microservers.
* 📄 **[ADR 0002: LangGraph Supervisor Pattern](file:///c:/git-hub/Aether/docs/adr/0002-langgraph-supervisor.md)** — Stateful supervisor orchestration for multi-agent workflows.
* 📄 **[ADR 0003: GraphRAG Hybrid Retrieval](file:///c:/git-hub/Aether/docs/adr/0003-graphrag-hybrid-retrieval.md)** — Combining Qdrant vector search with Neo4j graph traversal & RRF score fusion.

---

## 🗺️ Master Documentation & Roadmap

* 📖 **[Project Technical Specification](file:///c:/git-hub/Aether/building-base/aether/PROJECT_SPEC.md)** — Full technical spec and data schema.
* 🗺️ **[Master Roadmap Tracker](file:///c:/git-hub/Aether/building-base/aether/ROADMAP.md)** — Phase breakdowns, timelines, and milestones.
* 📄 **[Task Hub Dashboard](file:///c:/git-hub/Aether/building-base/aether/README.md)** — Granular task tracking from v1 to v8.