"""
FastAPI Router for Provider RAG Service.

Provides HTTP endpoints for:
- /ask - Query the knowledge base
- /stream - Streaming query (compatibility)
- /health - Service health check
- /ingest - Trigger knowledge base ingestion

Usage:
    from app.providers_rag.router import router
    app.include_router(router, prefix="/api/v1/providers")
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.providers_rag.schemas import ConfidenceLevel
from app.providers_rag.service import get_provider_rag_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["providers-rag"])


# ============================================
# REQUEST/RESPONSE MODELS
# ============================================

class QueryRequest(BaseModel):
    """Request model for query endpoint."""
    
    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="User query to the knowledge base"
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Optional session identifier for conversation tracking"
    )
    top_k: Optional[int] = Field(
        default=None,
        ge=1,
        le=20,
        description="Number of documents to retrieve (default: from config)"
    )


class QueryResponse(BaseModel):
    """Response model for query endpoint."""
    
    answer: str = Field(description="Generated answer")
    confidence: str = Field(description="Confidence level (high, medium, low, none)")
    confidence_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Numeric confidence score"
    )
    is_grounded: bool = Field(description="Whether response is grounded in knowledge base")
    is_refusal: bool = Field(description="Whether this is a refusal response")
    session_id: str = Field(description="Session identifier")
    
    # Optional detailed fields
    citations: Optional[list[dict]] = Field(
        default=None,
        description="Source citations (if enabled)"
    )
    processing_time_ms: Optional[float] = Field(
        default=None,
        description="Processing time in milliseconds"
    )
    
    # Compatibility fields for existing frontend
    kb_id: str = Field(default="providers", description="Knowledge base ID")
    kb_name: str = Field(default="Providers", description="Knowledge base name")


class HealthResponse(BaseModel):
    """Response model for health check endpoint."""
    
    status: str = Field(description="Service status (healthy, degraded, unhealthy)")
    kb_id: str = Field(default="providers")
    kb_name: str = Field(default="Providers")
    collection_count: int = Field(description="Number of documents in collection")
    embedding_model_loaded: bool = Field(description="Whether embedding model is loaded")
    bm25_index_loaded: bool = Field(description="Whether BM25 index is built")
    error_message: Optional[str] = Field(default=None)


class IngestRequest(BaseModel):
    """Request model for ingestion endpoint."""
    
    clear: bool = Field(
        default=False,
        description="Clear existing data before ingesting"
    )


class IngestResponse(BaseModel):
    """Response model for ingestion endpoint."""
    
    status: str = Field(description="Ingestion status")
    total_entries: int = Field(description="Total entries processed")
    successful_entries: int = Field(description="Successfully ingested entries")
    failed_entries: int = Field(description="Failed entries")
    sections_indexed: list[str] = Field(description="Sections indexed")
    ingestion_time_seconds: float = Field(description="Time taken")


# ============================================
# ENDPOINTS
# ============================================

@router.post("/ask", response_model=QueryResponse)
async def ask(request: QueryRequest):
    """
    Query the Provider Knowledge Base.
    
    Returns a grounded response based on the provider documentation.
    If information is not available, returns a clear refusal.
    """
    try:
        service = get_provider_rag_service()
        
        # Generate session ID if not provided
        session_id = request.session_id or str(uuid.uuid4())
        
        logger.info(
            f"Query received: session={session_id}, "
            f"query_length={len(request.query)}"
        )
        
        # Process query
        result = await service.query(
            query=request.query,
            session_id=session_id,
            top_k=request.top_k,
        )
        
        # Build response
        response = QueryResponse(
            answer=result.answer,
            confidence=result.confidence.value,
            confidence_score=result.confidence_score,
            is_grounded=result.is_grounded,
            is_refusal=result.is_refusal,
            session_id=session_id,
            processing_time_ms=result.processing_time_ms,
            citations=[
                {
                    "text": c.text,
                    "source": c.source,
                    "relevance_score": c.relevance_score,
                }
                for c in result.citations
            ] if result.citations else None,
        )
        
        logger.info(
            f"Response generated: session={session_id}, "
            f"confidence={result.confidence.value}, "
            f"time={result.processing_time_ms:.0f}ms"
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error processing query: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "answer": "An error occurred while processing your request. Please try again.",
                "confidence": "none",
                "confidence_score": 0.0,
                "is_grounded": True,
                "is_refusal": True,
                "session_id": request.session_id or "unknown",
                "error": str(e),
                "kb_id": "providers",
                "kb_name": "Providers",
            }
        )


@router.post("/stream")
async def stream(request: QueryRequest):
    """
    Streaming query endpoint (compatibility layer).
    
    Currently returns the same as /ask. 
    Can be enhanced for Server-Sent Events streaming in the future.
    """
    return await ask(request)


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Check the health of the Provider RAG service.
    
    Returns status information about:
    - Document collection
    - Embedding model
    - BM25 index
    """
    try:
        service = get_provider_rag_service()
        health = service.health_check()
        
        return HealthResponse(
            status=health.status,
            collection_count=health.collection_count,
            embedding_model_loaded=health.embedding_model_loaded,
            bm25_index_loaded=health.bm25_index_loaded,
            error_message=health.error_message,
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="unhealthy",
            collection_count=0,
            embedding_model_loaded=False,
            bm25_index_loaded=False,
            error_message=str(e),
        )


@router.post("/ingest", response_model=IngestResponse)
async def ingest(request: IngestRequest):
    """
    Trigger knowledge base ingestion.
    
    This endpoint re-ingests the provider knowledge base.
    Use with caution in production.
    """
    try:
        service = get_provider_rag_service()
        
        logger.info(f"Ingestion triggered: clear={request.clear}")
        
        result = await service.ingest(clear=request.clear)
        
        return IngestResponse(
            status=result.status,
            total_entries=result.total_entries,
            successful_entries=result.successful_entries,
            failed_entries=result.failed_entries,
            sections_indexed=result.sections_indexed,
            ingestion_time_seconds=result.ingestion_time_seconds,
        )
        
    except Exception as e:
        logger.error(f"Ingestion failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# BACKWARD COMPATIBILITY ENDPOINTS
# ============================================

@router.post("")
async def ask_root(payload: dict):
    """
    Backward compatibility endpoint for existing integrations.
    
    Accepts the same payload format as the old kb_factory router.
    """
    query = payload.get("query", "")
    session_id = payload.get("session_id")
    top_k = payload.get("top_k")
    
    request = QueryRequest(
        query=query,
        session_id=session_id,
        top_k=top_k,
    )
    
    response = await ask(request)
    
    # Return in legacy format
    return {
        "answer": response.answer,
        "session_id": response.session_id,
        "kb_id": response.kb_id,
        "kb_name": response.kb_name,
    }
