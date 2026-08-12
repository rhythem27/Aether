# Aether Developer & Setup Guide

This guide walks you through setting up, configuring, running, and testing the **Aether** platform locally.

---

## 📋 Prerequisites

* **Python 3.11** or higher
* **Poetry 1.8** or higher
* **Docker & Docker Compose**

---

## 🛠️ Step-by-Step Installation

### 1. Clone & Dependencies

```bash
git clone https://github.com/rhythem27/aether.git
cd aether

poetry install
```

### 2. Configure Environment Variables

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Edit `.env` to configure your API keys:

```ini
# LLM Providers
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
COHERE_API_KEY=ch-...

# Data Sources
EDGAR_API_KEY=your_email@domain.com
CRUNCHBASE_KEY=your_key
NEWS_API_KEY=your_key

# Database Hosts
QDRANT_URL=http://localhost:6333
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
REDIS_URL=redis://localhost:6379/0
```

---

## 🐳 Running Infrastructure Services

Start database and caching containers in background mode:

```bash
docker compose up -d
```

Verify service containers are running:
* **Qdrant Vector DB:** `http://localhost:6333`
* **Neo4j Browser:** `http://localhost:7474`
* **Langfuse Dashboard:** `http://localhost:3000`
* **Prometheus:** `http://localhost:9090`
* **Grafana:** `http://localhost:3001`

---

## 🚀 Running the Platform Services

### 1. Initialize Database Collections

```bash
poetry run python -m backend.db.init_db
```

### 2. Start FastAPI Server

```bash
poetry run uvicorn backend.api.main:app --reload --host 0.0.0.0 --port 8000
```
Interactive Swagger docs: `http://localhost:8000/docs`

### 3. Start Celery Worker

In a separate terminal window:

```bash
poetry run celery -A backend.workers.research_tasks worker --loglevel=info --concurrency=4
```

---

## 🧪 Running Tests & Quality Checks

```bash
# Run Ruff Linter
poetry run ruff check .

# Run Black Code Formatter
poetry run black --check .

# Run MyPy Static Type Check
poetry run mypy backend

# Run Pytest Suite with Coverage
poetry run pytest --cov=backend --cov-report=html
```
