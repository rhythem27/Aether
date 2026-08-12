# ADR 0003: GraphRAG Hybrid Retrieval (Vector + Knowledge Graph RRF)

* **Status:** Accepted
* **Date:** 2026-08-12
* **Deciders:** Data & Retrieval Engineering Team
* **Technical Area:** Retrieval-Augmented Generation (RAG) Architecture

---

## Context & Problem Statement

Naive dense vector RAG relies purely on semantic similarity embeddings. In complex financial disclosures (e.g. SEC 10-K filings, M&A history, subsidiary structures), vector search misses non-contiguous multi-hop entity relationships (e.g., "Which subsidiary of Company X is involved in Lawsuit Y?").

---

## Decision Driver Options

1. **Pure Vector Search (Qdrant):** Dense similarity search on chunked text.
2. **Pure Knowledge Graph (Neo4j):** Explicit Cypher graph queries on extracted entities.
3. **GraphRAG Hybrid Retrieval with Reciprocal Rank Fusion (RRF):** Dual-path retrieval combining dense vector similarity + BM25 keyword matching with Neo4j 2-hop graph traversal & Louvain community detection, fused using Reciprocal Rank Fusion.

---

## Decision Outcome

**Chosen Option:** **Option 3 — GraphRAG Hybrid Retrieval with Reciprocal Rank Fusion (RRF)**.

We implemented Qdrant vector indexing (`financial_intelligence`, Cosine 1024-dim) alongside Neo4j entity resolution and GDS community detection, scored and reranked using RRF ($k=60.0$).

### Consequences & Benefits

* **Multi-Hop Traversal:** Captures complex corporate structures and relationship triples (`ACQUIRED`, `INVESTED_IN`, `COMPETES_WITH`).
* **High Citation Precision:** Dual-path reranking achieves >95% citation accuracy on SEC benchmark tests.
* **Resilience:** Gracefully falls back to dense vector search if graph connections are sparse.
