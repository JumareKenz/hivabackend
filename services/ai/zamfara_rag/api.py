"""
FastAPI API routes for Zamfara RAG system.

Provides REST endpoints for:
- Document ingestion
- FAQ queries
- System statistics

Usage:
    # In your FastAPI app
    from zamfara_rag.api import router as zamfara_router
    app.include_router(zamfara_router, prefix="/zamfara", tags=["zamfara-faq"])
"""

from __future__ import annotations

import logging
from typing import Optional, List
from pydantic import BaseModel, Field, model_validator

try:
    from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
    from fastapi.responses import JSONResponse
except ImportError:
    raise ImportError("FastAPI is required. Install with: pip install fastapi")

from zamfara_rag.main import ZamfaraRAGPipeline

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter()

# Global pipeline instance (singleton)
_pipeline: Optional[ZamfaraRAGPipeline] = None


def get_pipeline() -> ZamfaraRAGPipeline:
    """Get or create the pipeline singleton."""
    global _pipeline
    if _pipeline is None:
        logger.info("Initializing Zamfara RAG Pipeline with Groq...")
        # Always use Groq configuration
        import os
        groq_api_url = os.getenv("LLM_API_URL", "https://api.groq.com/openai/v1")
        groq_model = os.getenv("LLM_MODEL", "openai/gpt-oss-20b")
        groq_api_key = os.getenv("LLM_API_KEY")
        
        # Ensure we're using Groq (override if needed)
        if "groq" not in groq_api_url.lower():
            groq_api_url = "https://api.groq.com/openai/v1"
        if "gpt-oss" not in groq_model.lower():
            groq_model = "openai/gpt-oss-20b"
            
        _pipeline = ZamfaraRAGPipeline(
            llm_api_url=groq_api_url,
            llm_model=groq_model,
            llm_api_key=groq_api_key,
        )
        logger.info(f"Pipeline initialized with LLM: {groq_model} via {groq_api_url}")
    return _pipeline


# === Request/Response Models ===

class QueryRequest(BaseModel):
    """Request model for FAQ queries."""
    question: Optional[str] = Field(None, max_length=1000, description="Question to ask (legacy field)")
    query: Optional[str] = Field(None, max_length=1000, description="Question to ask (preferred field)")
    
    @model_validator(mode='after')
    def validate_question(self):
        """Validate that at least one field is provided and has minimum length."""
        # Check if at least one is provided
        if not self.query and not self.question:
            raise ValueError("Either 'query' or 'question' field is required")
        
        # Validate length if provided (allow 2 chars for greetings)
        question_text = self.query or self.question or ""
        if len(question_text) < 2:
            raise ValueError("Question must be at least 2 characters")
        
        return self
    top_k: int = Field(5, ge=1, le=20, description="Number of documents to retrieve")
    document_type: Optional[str] = Field(None, description="Filter by document type (policy, guideline, sop, etc.)")
    department: Optional[str] = Field(None, description="Filter by department")
    verify: bool = Field(False, description="Run hallucination verification")
    session_id: Optional[str] = Field(None, description="Session ID for conversation context")
    user_role: Optional[str] = Field(None, description="User role (customer, provider, etc.)")
    
    @model_validator(mode='after')
    def validate_question_present(self):
        """Ensure at least one of 'query' or 'question' is provided."""
        if not self.query and not self.question:
            raise ValueError("Either 'query' or 'question' field is required")
        return self
        return self
    
    def get_question(self) -> str:
        """Get the question from either 'query' or 'question' field."""
        return self.query or self.question or ""


class QueryResponse(BaseModel):
    """Response model for FAQ queries."""
    query: str
    answer: str
    citations: List[str]
    sources: List[str]
    confidence: float
    is_grounded: bool
    verification_passed: bool
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "What is the health policy?",
                "answer": "According to the ZAMCHEMA OPG, the health policy...",
                "citations": ["ZAMCHEMA OPG - Section 3"],
                "sources": ["ZAMCHEMA OPG"],
                "confidence": 0.85,
                "is_grounded": True,
                "verification_passed": True
            }
        }


class IngestRequest(BaseModel):
    """Request model for document ingestion."""
    clear: bool = Field(False, description="Clear existing vector store before ingesting")


class IngestResponse(BaseModel):
    """Response model for ingestion results."""
    documents_loaded: int
    chunks_created: int
    chunks_indexed: int
    errors: List[str]
    start_time: str
    end_time: Optional[str] = None


class StatsResponse(BaseModel):
    """Response model for system statistics."""
    source_directory: str
    vector_store: dict
    embedding_cache: dict


# === API Endpoints ===

@router.post("/ask", response_model=QueryResponse)
async def ask_question(request: QueryRequest):
    """
    Ask a question about Zamfara State policies and guidelines.
    
    The system will:
    1. Search the document knowledge base
    2. Retrieve relevant sections
    3. Generate a grounded answer with citations
    4. Verify the answer for hallucinations
    
    Returns a response grounded in official documents only.
    """
    try:
        pipeline = get_pipeline()
        
        # Get question from either 'query' or 'question' field
        question_text = request.get_question()
        if not question_text:
            raise HTTPException(
                status_code=422,
                detail="Either 'query' or 'question' field is required"
            )
        
        result = await pipeline.query(
            question=question_text,
            k=request.top_k,
            document_type=request.document_type,
            department=request.department,
            verify=request.verify,
        )
        
        return QueryResponse(
            query=result.query,
            answer=result.answer,
            citations=result.citations,
            sources=result.sources,
            confidence=result.confidence,
            is_grounded=result.is_grounded,
            verification_passed=result.verification_passed,
        )
    
    except Exception as e:
        logger.error(f"Query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ask")
async def ask_question_get(
    question: str = Query(..., min_length=3, max_length=1000, description="Question to ask"),
    top_k: int = Query(5, ge=1, le=20, description="Number of documents to retrieve"),
    document_type: Optional[str] = Query(None, description="Filter by document type"),
    department: Optional[str] = Query(None, description="Filter by department"),
):
    """
    GET endpoint for asking questions (convenient for testing).
    
    Example:
        GET /zamfara/ask?question=What%20is%20the%20health%20policy?
    """
    request = QueryRequest(
        question=question,  # GET uses 'question' query param
        top_k=top_k,
        document_type=document_type,
        department=department,
    )
    return await ask_question(request)


@router.post("/ingest", response_model=IngestResponse)
async def ingest_documents(
    request: IngestRequest,
    background_tasks: BackgroundTasks,
):
    """
    Ingest documents from the Zamfara directory.
    
    This operation may take some time for large document sets.
    Use `clear=true` to rebuild the entire index.
    """
    try:
        pipeline = get_pipeline()
        
        # For large ingestion, this could be run in background
        # For now, run synchronously for simplicity
        result = pipeline.ingest(clear=request.clear)
        
        return IngestResponse(
            documents_loaded=result.get("documents_loaded", 0),
            chunks_created=result.get("chunks_created", 0),
            chunks_indexed=result.get("chunks_indexed", 0),
            errors=result.get("errors", []),
            start_time=result.get("start_time", ""),
            end_time=result.get("end_time"),
        )
    
    except Exception as e:
        logger.error(f"Ingestion failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=StatsResponse)
async def get_stats():
    """
    Get system statistics including document counts and cache status.
    """
    try:
        pipeline = get_pipeline()
        stats = pipeline.get_stats()
        
        return StatsResponse(
            source_directory=stats.get("source_directory", ""),
            vector_store=stats.get("vector_store", {}),
            embedding_cache=stats.get("embedding_cache", {}),
        )
    
    except Exception as e:
        logger.error(f"Stats retrieval failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """
    Health check endpoint.
    """
    try:
        pipeline = get_pipeline()
        stats = pipeline.vector_store.get_stats()
        
        return {
            "status": "healthy",
            "documents_indexed": stats.get("document_count", 0),
            "collection": stats.get("collection_name", ""),
        }
    
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
            }
        )


@router.get("/document-types")
async def get_document_types():
    """
    Get available document types for filtering.
    """
    return {
        "document_types": [
            {"id": "policy", "name": "Policy Documents", "description": "Official policies, regulations, acts"},
            {"id": "guideline", "name": "Guidelines", "description": "Guidance documents and manuals"},
            {"id": "sop", "name": "Standard Operating Procedures", "description": "Procedures and workflows"},
            {"id": "faq", "name": "FAQs", "description": "Frequently asked questions"},
            {"id": "gazette", "name": "Gazettes", "description": "Official government publications"},
            {"id": "opg", "name": "Operational Guidelines", "description": "Operational and administrative guides"},
        ]
    }


@router.get("/departments")
async def get_departments():
    """
    Get available departments for filtering.
    """
    return {
        "departments": [
            {"id": "health", "name": "Health"},
            {"id": "finance", "name": "Finance"},
            {"id": "education", "name": "Education"},
            {"id": "agriculture", "name": "Agriculture"},
            {"id": "infrastructure", "name": "Infrastructure"},
            {"id": "administration", "name": "Administration"},
            {"id": "legal", "name": "Legal"},
            {"id": "security", "name": "Security"},
            {"id": "social_welfare", "name": "Social Welfare"},
        ]
    }




