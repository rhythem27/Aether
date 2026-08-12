# ADR 0002: LangGraph Supervisor Pattern for Multi-Agent Orchestration

* **Status:** Accepted
* **Date:** 2026-08-12
* **Deciders:** Multi-Agent Architecture Team
* **Technical Area:** Agent Workflow Orchestration & State Management

---

## Context & Problem Statement

Comprehensive financial due diligence requires coordinated specialized tasks: SEC disclosure analysis, valuation modeling, primary source claim auditing, knowledge graph population, and final report generation. Unstructured agent loops often loop infinitely, struggle with state synchronization, or produce hallucinated conclusions without human oversight.

---

## Decision Driver Options

1. **Sequential Chain Execution:** Rigid linear execution pipelines (A -> B -> C).
2. **Autonomous Agent Swarm (Flat/Peer-to-Peer):** Fully autonomous agents passing messages without a central controller.
3. **LangGraph Stateful Supervisor Orchestration:** Central Supervisor router controlling state transitions across specialized agents with explicit state schemas and human-in-the-loop (HITL) checkpoints.

---

## Decision Outcome

**Chosen Option:** **Option 3 — LangGraph Stateful Supervisor Orchestration**.

We established a central `supervisor` node governing transitions across `research_agent`, `analysis_agent`, `verify_agent`, `graph_builder_agent`, and `report_agent`.

### Consequences & Benefits

* **State Persistence:** `AgentState` schema maintains typed context (ticker, fiscal year, verified claims, token counts) backed by Postgres checkpointers.
* **Deterministic Routing:** Supervisor evaluates state completeness and routes dynamically or terminates cleanly.
* **Human-in-the-Loop Checkpoints:** Enables `interrupt()` gates before high-risk financial claims are finalized.
* **Granular Traceability:** Integrated with Langfuse `@observe()` tracing for per-agent latency and token cost analysis.
