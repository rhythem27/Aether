from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, UploadFile, status, HTTPException
from pydantic import BaseModel
from qdrant_client import AsyncQdrantClient
import structlog

from backend.api.dependencies import get_qdrant_db_client
from backend.db.qdrant import init_qdrant_collection
from backend.rag.anydoc_parser import AnyDocParser
from backend.rag.chunking import TokenAwareChunker
from backend.rag.retriever import HybridRetriever, QueryResultPassage

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


class DocumentUploadResponse(BaseModel):
    filename: str
    total_chunks: int
    document_type: str
    company_ticker: Optional[str] = None
    fiscal_year: Optional[int] = None
    status: str = "indexed"


class DocumentQueryRequest(BaseModel):
    query: str
    top_k: int = 5
    company_ticker: Optional[str] = None
    document_type: Optional[str] = None
    fiscal_year: Optional[int] = None


class DocumentQueryResponse(BaseModel):
    query: str
    total_results: int
    passages: List[QueryResultPassage]


parser = AnyDocParser()
chunker = TokenAwareChunker(max_tokens=512, overlap=50)


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: UploadFile = File(...),
    company_ticker: Optional[str] = Form(None),
    company_name: Optional[str] = Form(None),
    fiscal_year: Optional[int] = Form(None),
    document_type: str = Form("general"),
    q_client: AsyncQdrantClient = Depends(get_qdrant_db_client),
):
    """Upload, parse, chunk, and index a financial document into Qdrant."""
    logger.info("uploading_document", filename=file.filename, ticker=company_ticker)

    try:
        await init_qdrant_collection(client=q_client)
        content = await file.read()
        safe_filename = file.filename or "document.pdf"
        parsed_doc = parser.parse(
            file_path=safe_filename,
            content=content,
            company_ticker=company_ticker,
            fiscal_year=fiscal_year,
        )

        chunks = chunker.chunk_document(
            document=parsed_doc,
            company_ticker=company_ticker,
            company_name=company_name,
            fiscal_year=fiscal_year,
            document_type=document_type,
        )

        retriever = HybridRetriever(qdrant_client=q_client)
        total_upserted = await retriever.upsert_chunks(chunks)

        return DocumentUploadResponse(
            filename=safe_filename,
            total_chunks=total_upserted,
            document_type=document_type,
            company_ticker=company_ticker,
            fiscal_year=fiscal_year,
            status="indexed",
        )
    except Exception as e:
        logger.error("document_upload_failed", filename=file.filename, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document upload and indexing failed: {str(e)}",
        )


@router.post("/query", response_model=DocumentQueryResponse)
async def query_documents(
    request: DocumentQueryRequest,
    q_client: AsyncQdrantClient = Depends(get_qdrant_db_client),
):
    """Hybrid dense+sparse vector search with payload filtering and source citations."""
    logger.info(
        "querying_documents", query=request.query, ticker=request.company_ticker
    )

    try:
        await init_qdrant_collection(client=q_client)
        retriever = HybridRetriever(qdrant_client=q_client)
        passages = await retriever.search(
            query=request.query,
            top_k=request.top_k,
            company_ticker=request.company_ticker,
            document_type=request.document_type,
            fiscal_year=request.fiscal_year,
        )

        return DocumentQueryResponse(
            query=request.query, total_results=len(passages), passages=passages
        )
    except Exception as e:
        logger.error("document_query_failed", query=request.query, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document search failed: {str(e)}",
        )
