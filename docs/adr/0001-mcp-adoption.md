# ADR 0001: Model Context Protocol (MCP) Adoption for Financial Data Tooling

* **Status:** Accepted
* **Date:** 2026-08-12
* **Deciders:** Architectural Engineering Team
* **Technical Area:** Data Tooling & MCP Integration Layer

---

## Context & Problem Statement

Financial due diligence requires fetching data from diverse, non-standard external APIs (SEC EDGAR filings, Crunchbase company funding, real-time financial market news, Neo4j graph stores). Hardcoding client integrations directly into agent nodes creates tight coupling, increases maintenance overhead, and makes adding new data sources error-prone.

---

## Decision Driver Options

1. **Direct API Integration:** Hardcode HTTP calls inside each agent function.
2. **LangChain Custom Tools:** Bind custom Python tools directly to LLMs.
3. **Model Context Protocol (MCP) Architecture:** Standardize tools as independent FastMCP microservers exposing standardized tool definitions over JSON-RPC / SSE protocols.

---

## Decision Outcome

**Chosen Option:** **Option 3 — Model Context Protocol (MCP) Architecture**.

We implemented custom FastMCP servers (`sec-edgar`, `crunchbase`, `newsapi`, `neo4j`) bound dynamically via `MCPClientManager` and `mcp_config.json`.

### Consequences & Benefits

* **Decoupled Architecture:** MCP tools run as isolated microservices without polluting agent code.
* **Standardized Protocol:** Standard JSON-RPC schema allows seamless tool discovery and capability negotiation across LLM providers.
* **Extensibility:** New financial data providers (e.g. Bloomberg, FactSet) can be added as standalone MCP servers without modifying the core agent orchestration engine.
* **Compliance & Auditing:** Tool calls and arguments are logged centrally before execution.
