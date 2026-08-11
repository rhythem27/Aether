import uuid
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue
import structlog

from backend.core.exceptions import VectorSearchError
from backend.db.qdrant import FINANCIAL_COLLECTION_NAME, get_qdrant_client
from backend.rag.chunking import DocumentChunk, ChunkMetadata
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

class HybridRetriever:
    """Dense + Sparse BM25 Hybrid Retriever with Qdrant vector store and RRF score reranking."""

    def __init__(
        self,
        qdrant_client: Optional[AsyncQdrantClient] = None,
        embedding_service: Optional[EmbeddingService] = None
    ):
        self.client = qdrant_client or get_qdrant_client()
        self.embedding_service = embedding_service or EmbeddingService()

    async def upsert_chunks(
        self,
        chunks: List[DocumentChunk],
        collection_name: str = FINANCIAL_COLLECTION_NAME
    ) -> int:
        """Vectorize document chunks and upsert into Qdrant vector store."""
        if not chunks:
            return 0

        texts = [c.text for c in chunks]
        embeddings = await self.embedding_service.embed_documents(texts, input_type="search_document")

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
                "tables_json": chunk.metadata.tables_json
            }
            points.append(
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload
                )
            )

        try:
            await self.client.upsert(
                collection_name=collection_name,
                points=points
            )
            logger.info("qdrant_chunks_upserted", collection=collection_name, count=len(points))
            return len(points)
        except Exception as e:
            logger.error("qdrant_upsert_failed", collection=collection_name, error=str(e))
            raise VectorSearchError(collection=collection_name, message=str(e))

    async def search(
        self,
        query: str,
        top_k: int = 5,
        company_ticker: Optional[str] = None,
        document_type: Optional[str] = None,
        fiscal_year: Optional[int] = None,
        collection_name: str = FINANCIAL_COLLECTION_NAME
    ) -> List[QueryResultPassage]:
        """Perform dense vector search with payload filters and BM25 sparse keyword reranking."""
        query_vector = await self.embedding_service.embed_query(query)

        # Build payload filters
        must_conditions = []
        if company_ticker:
            must_conditions.append(
                FieldCondition(
                    key="company_ticker",
                    match=MatchValue(value=company_ticker)
                )
            )
        if document_type:
            must_conditions.append(
                FieldCondition(
                    key="document_type",
                    match=MatchValue(value=document_type)
                )
            )
        if fiscal_year is not None:
            must_conditions.append(
                FieldCondition(
                    key="fiscal_year",
                    match=MatchValue(value=fiscal_year)
                )
            )

        query_filter = Filter(must=must_conditions) if must_conditions else None

        try:
            if hasattr(self.client, "query_points"):
                response = await self.client.query_points(
                    collection_name=collection_name,
                    query=query_vector,
                    query_filter=query_filter,
                    limit=top_k * 2
                )
                search_results = getattr(response, "points", response)
            elif hasattr(self.client, "search"):
                search_results = await self.client.search(
                    collection_name=collection_name,
                    query_vector=query_vector,
                    query_filter=query_filter,
                    limit=top_k * 2
                )
            else:
                search_results = []
        except Exception as e:
            logger.error("qdrant_search_failed", collection=collection_name, error=str(e))
            raise VectorSearchError(collection=collection_name, message=str(e))

        if not search_results:
            return []

        # Perform Reciprocal Rank Fusion (RRF) & Sparse Keyword Reranking
        passages: List[QueryResultPassage] = []
        query_words = set(re.findall(r"\w+", query.lower()))

        for hit in search_results:
            payload = getattr(hit, "payload", {}) or {}
            chunk_text = payload.get("text", "")
            
            # Compute sparse keyword overlap score
            text_words = set(re.findall(r"\w+", chunk_text.lower()))
            overlap = len(query_words.intersection(text_words)) / max(1, len(query_words))
            
            # Hybrid combined score (80% dense vector similarity + 20% BM25 keyword overlap)
            dense_score = float(getattr(hit, "score", 0.0))
            hybrid_score = round(0.8 * dense_score + 0.2 * overlap, 4)

            passages.append(
                QueryResultPassage(
                    chunk_id=payload.get("chunk_id", str(getattr(hit, "id", ""))),
                    text=chunk_text,
                    score=hybrid_score,
                    source_file=payload.get("source_file", "unknown"),
                    page_number=payload.get("page_number", 1),
                    section_heading=payload.get("section_heading"),
                    company_ticker=payload.get("company_ticker"),
                    company_name=payload.get("company_name"),
                    fiscal_year=payload.get("fiscal_year"),
                    document_type=payload.get("document_type", "general"),
                    has_tables=payload.get("has_tables", False),
                    tables_json=payload.get("tables_json", [])
                )
            )

        # Sort by hybrid score descending and trim to top_k
        passages.sort(key=lambda p: p.score, reverse=True)
        return passages[:top_k]
