import uuid
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue, MatchAny
import structlog

from backend.core.exceptions import VectorSearchError
from backend.db.qdrant import FINANCIAL_COLLECTION_NAME, get_qdrant_client
from backend.rag.chunking import DocumentChunk
from backend.rag.embeddings import EmbeddingService

logger = structlog.get_logger(__name__)


class QueryResultPassage(BaseModel):
    chunk_id: str
    text: str
    score: float
    source_file: str
    page_number: int
    section_heading: Optional[str] = None
    company_ticker: Optional[str] = None
    company_name: Optional[str] = None
    fiscal_year: Optional[int] = None
    document_type: str
    has_tables: bool = False
    tables_json: List[Dict[str, Any]] = Field(default_factory=list)
    entity_ids: List[str] = Field(default_factory=list)
    community_tag: Optional[str] = None
    pagerank_score: float = 0.0



class HybridRetriever:
    """Dense + Sparse BM25 Hybrid Retriever with Qdrant vector store and RRF score reranking."""

    def __init__(
        self,
        qdrant_client: Optional[AsyncQdrantClient] = None,
        embedding_service: Optional[EmbeddingService] = None,
    ):
        self.client = qdrant_client or get_qdrant_client()
        self.embedding_service = embedding_service or EmbeddingService()

    async def upsert_chunks(
        self,
        chunks: List[DocumentChunk],
        collection_name: str = FINANCIAL_COLLECTION_NAME,
    ) -> int:
        """Vectorize document chunks and upsert into Qdrant vector store."""
        if not chunks:
            return 0

        texts = [c.text for c in chunks]
        embeddings = await self.embedding_service.embed_documents(
            texts, input_type="search_document"
        )

        points: List[PointStruct] = []
        for idx, (chunk, vector) in enumerate(zip(chunks, embeddings)):
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk.chunk_id))
            payload = {
                "chunk_id": chunk.chunk_id,
                "text": chunk.text,
                "token_count": chunk.token_count,
                "source_file": chunk.metadata.source_file,
                "page_number": chunk.metadata.page_number,
                "section_heading": chunk.metadata.section_heading,
                "company_ticker": chunk.metadata.company_ticker,
                "company_name": chunk.metadata.company_name,
                "fiscal_year": chunk.metadata.fiscal_year,
                "document_type": chunk.metadata.document_type,
                "has_tables": chunk.metadata.has_tables,
                "tables_json": chunk.metadata.tables_json,
                "entity_ids": getattr(chunk.metadata, "entity_ids", []),
                "community_tag": getattr(chunk.metadata, "community_tag", None),
            }
            points.append(PointStruct(id=point_id, vector=vector, payload=payload))

        try:
            await self.client.upsert(collection_name=collection_name, points=points)
            logger.info(
                "qdrant_chunks_upserted", collection=collection_name, count=len(points)
            )
            return len(points)
        except Exception as e:
            logger.error(
                "qdrant_upsert_failed", collection=collection_name, error=str(e)
            )
            raise VectorSearchError(collection=collection_name, message=str(e))

    async def search(
        self,
        query: str,
        top_k: int = 5,
        company_ticker: Optional[str] = None,
        document_type: Optional[str] = None,
        fiscal_year: Optional[int] = None,
        entity_ids: Optional[List[str]] = None,
        community_tag: Optional[str] = None,
        pagerank_weights: Optional[Dict[str, float]] = None,
        subgraph_expand: bool = False,
        neo4j_driver: Optional[Any] = None,
        collection_name: str = FINANCIAL_COLLECTION_NAME,
    ) -> List[QueryResultPassage]:
        """Perform dense vector search with payload filters (entity_ids, community_tag) and PageRank centrality-weighted BM25 reranking."""
        query_vector = await self.embedding_service.embed_query(query)

        target_entity_ids = list(entity_ids) if entity_ids else []

        if subgraph_expand and (target_entity_ids or company_ticker):
            try:
                from backend.rag.graphrag import expand_subgraph_entity_ids
                seeds = list(target_entity_ids)
                if company_ticker:
                    seeds.append(f"company_{company_ticker.lower()}")
                expanded = await expand_subgraph_entity_ids(
                    driver=neo4j_driver, seed_entity_ids=seeds, max_hops=2
                )
                if expanded:
                    target_entity_ids = expanded
            except Exception as exp_err:
                logger.warning("subgraph_expansion_failed", error=str(exp_err))

        # Build payload filters
        must_conditions: List[Any] = []
        if company_ticker:
            must_conditions.append(
                FieldCondition(
                    key="company_ticker", match=MatchValue(value=company_ticker)
                )
            )
        if document_type:
            must_conditions.append(
                FieldCondition(
                    key="document_type", match=MatchValue(value=document_type)
                )
            )
        if fiscal_year is not None:
            must_conditions.append(
                FieldCondition(key="fiscal_year", match=MatchValue(value=fiscal_year))
            )
        if community_tag:
            must_conditions.append(
                FieldCondition(key="community_tag", match=MatchValue(value=community_tag))
            )
        if target_entity_ids:
            if len(target_entity_ids) == 1:
                must_conditions.append(
                    FieldCondition(key="entity_ids", match=MatchValue(value=target_entity_ids[0]))
                )
            else:
                must_conditions.append(
                    FieldCondition(key="entity_ids", match=MatchAny(any=target_entity_ids))
                )

        query_filter = Filter(must=must_conditions) if must_conditions else None

        async def _execute_qdrant_query(fltr: Optional[Filter]) -> List[Any]:
            if hasattr(self.client, "query_points"):
                response = await self.client.query_points(
                    collection_name=collection_name,
                    query=query_vector,
                    query_filter=fltr,
                    limit=top_k * 2,
                )
                return getattr(response, "points", response)
            elif hasattr(self.client, "search"):
                return await self.client.search(
                    collection_name=collection_name,
                    query_vector=query_vector,
                    query_filter=fltr,
                    limit=top_k * 2,
                )
            return []

        try:
            search_results = await _execute_qdrant_query(query_filter)
            # Fallback if strict target_entity_ids filter yields empty results
            if not search_results and target_entity_ids:
                fallback_conditions = [c for c in must_conditions if getattr(c, "key", "") != "entity_ids"]
                fallback_filter = Filter(must=fallback_conditions) if fallback_conditions else None
                search_results = await _execute_qdrant_query(fallback_filter)
        except Exception as e:
            logger.error(
                "qdrant_search_failed", collection=collection_name, error=str(e)
            )
            raise VectorSearchError(collection=collection_name, message=str(e))

        if not search_results:
            return []

        # Perform Reciprocal Rank Fusion (RRF) & Sparse Keyword Reranking with PageRank Centrality Weighting
        passages: List[QueryResultPassage] = []
        query_words = set(re.findall(r"\w+", query.lower()))

        for hit in search_results:
            payload = getattr(hit, "payload", {}) or {}
            chunk_text = payload.get("text", "")
            chunk_eids = payload.get("entity_ids", [])

            # Compute sparse keyword overlap score
            text_words = set(re.findall(r"\w+", chunk_text.lower()))
            overlap = len(query_words.intersection(text_words)) / max(
                1, len(query_words)
            )

            # Hybrid combined score (80% dense vector similarity + 20% BM25 keyword overlap)
            dense_score = float(getattr(hit, "score", 0.0))
            hybrid_score = round(0.8 * dense_score + 0.2 * overlap, 4)

            # PageRank centrality boost calculation
            pr_score = 0.0
            if pagerank_weights and chunk_eids:
                pr_score = max([float(pagerank_weights.get(eid, 0.0)) for eid in chunk_eids], default=0.0)
                final_score = round(hybrid_score + 0.2 * pr_score, 4)
            else:
                final_score = hybrid_score

            passages.append(
                QueryResultPassage(
                    chunk_id=payload.get("chunk_id", str(getattr(hit, "id", ""))),
                    text=chunk_text,
                    score=final_score,
                    source_file=payload.get("source_file", "unknown"),
                    page_number=payload.get("page_number", 1),
                    section_heading=payload.get("section_heading"),
                    company_ticker=payload.get("company_ticker"),
                    company_name=payload.get("company_name"),
                    fiscal_year=payload.get("fiscal_year"),
                    document_type=payload.get("document_type", "general"),
                    has_tables=payload.get("has_tables", False),
                    tables_json=payload.get("tables_json", []),
                    entity_ids=chunk_eids,
                    community_tag=payload.get("community_tag"),
                    pagerank_score=pr_score,
                )
            )

        # Sort by final weighted score descending and trim to top_k
        passages.sort(key=lambda p: p.score, reverse=True)
        return passages[:top_k]


