"""
Pydantic schemas for the Provider RAG System.

Provides strict validation for all data structures to ensure
data integrity throughout the pipeline.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator


class ConfidenceLevel(str, Enum):
    """Confidence levels for retrieval results."""
    
    HIGH = "high"  # Very confident - strong semantic match
    MEDIUM = "medium"  # Moderately confident - decent match
    LOW = "low"  # Low confidence - marginal match
    NONE = "none"  # No relevant information found


class DocumentSource(BaseModel):
    """Source document metadata."""
    
    document_name: str = Field(description="Name of the source document")
    section: str = Field(default="", description="Section within the document")
    page: Optional[int] = Field(default=None, description="Page number if applicable")
    chunk_index: int = Field(default=0, description="Index of chunk within document")
    
    class Config:
        frozen = True


class KnowledgeEntry(BaseModel):
    """
    Schema for a knowledge base entry (Q&A pair).
    
    This is the validated schema for ingesting provider knowledge documents.
    """
    
    question: str = Field(
        min_length=5,
        max_length=1000,
        description="The question or query this entry answers"
    )
    answer: str = Field(
        min_length=10,
        max_length=5000,
        description="The authoritative answer"
    )
    intent: str = Field(
        default="",
        max_length=100,
        description="Intent classification for the entry"
    )
    section: str = Field(
        default="",
        max_length=200,
        description="Section of the knowledge base"
    )
    source_document: str = Field(
        default="Providers FAQ",
        max_length=200,
        description="Source document name"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )
    
    @field_validator("question", "answer")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()
    
    @field_validator("intent", "section")
    @classmethod
    def normalize_identifier(cls, v: str) -> str:
        return v.strip().lower().replace(" ", "_") if v else ""


class DocumentChunk(BaseModel):
    """
    A chunk of knowledge with embedding metadata.
    
    Represents a single retrievable unit of information.
    """
    
    id: str = Field(description="Unique identifier for the chunk")
    content: str = Field(description="The text content of the chunk")
    embedding: Optional[list[float]] = Field(
        default=None,
        description="Vector embedding of the content"
    )
    
    # Metadata for retrieval and citation
    source: DocumentSource = Field(description="Source document information")
    intent: str = Field(default="", description="Intent classification")
    section: str = Field(default="", description="Section classification")
    
    # Original Q&A if this is a Q&A chunk
    original_question: Optional[str] = Field(
        default=None,
        description="Original question if from Q&A pair"
    )
    original_answer: Optional[str] = Field(
        default=None,
        description="Original answer if from Q&A pair"
    )
    
    # BM25 tokens for sparse retrieval
    bm25_tokens: Optional[list[str]] = Field(
        default=None,
        description="Tokenized content for BM25"
    )
    
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp of chunk creation"
    )
    
    class Config:
        frozen = False  # Allow modification during processing


class RetrievalResult(BaseModel):
    """
    Result from the retrieval engine.
    
    Contains matched documents with their similarity scores.
    """
    
    chunks: list[DocumentChunk] = Field(
        default_factory=list,
        description="Retrieved document chunks"
    )
    scores: list[float] = Field(
        default_factory=list,
        description="Similarity scores for each chunk (0-1)"
    )
    confidence: ConfidenceLevel = Field(
        default=ConfidenceLevel.NONE,
        description="Overall confidence level"
    )
    
    # Retrieval metadata
    query: str = Field(description="Original query")
    dense_scores: Optional[list[float]] = Field(
        default=None,
        description="Scores from dense retrieval"
    )
    sparse_scores: Optional[list[float]] = Field(
        default=None,
        description="Scores from BM25 retrieval"
    )
    retrieval_time_ms: float = Field(
        default=0.0,
        description="Time taken for retrieval in milliseconds"
    )
    
    @property
    def has_relevant_results(self) -> bool:
        """Check if any relevant results were found."""
        return len(self.chunks) > 0 and self.confidence != ConfidenceLevel.NONE
    
    @property
    def top_score(self) -> float:
        """Get the highest similarity score."""
        return max(self.scores) if self.scores else 0.0
    
    @property
    def avg_score(self) -> float:
        """Get the average similarity score."""
        return sum(self.scores) / len(self.scores) if self.scores else 0.0


class Citation(BaseModel):
    """A citation reference to source material."""
    
    text: str = Field(description="Cited text or summary")
    source: str = Field(description="Source document/section")
    relevance_score: float = Field(
        ge=0.0, le=1.0,
        description="How relevant this citation is"
    )


class QueryResult(BaseModel):
    """
    Final result of a RAG query.
    
    This is the main output of the Provider RAG service.
    """
    
    # Core response
    answer: str = Field(description="The generated answer")
    confidence: ConfidenceLevel = Field(
        description="Confidence level of the answer"
    )
    confidence_score: float = Field(
        ge=0.0, le=1.0,
        description="Numeric confidence score"
    )
    
    # Source attribution
    citations: list[Citation] = Field(
        default_factory=list,
        description="Citations supporting the answer"
    )
    
    # Response metadata
    query: str = Field(description="Original user query")
    is_grounded: bool = Field(
        default=True,
        description="Whether the answer is grounded in retrieved documents"
    )
    is_refusal: bool = Field(
        default=False,
        description="Whether this is a refusal response"
    )
    needs_clarification: bool = Field(
        default=False,
        description="Whether clarification is needed"
    )
    
    # Debug/audit information
    retrieval_result: Optional[RetrievalResult] = Field(
        default=None,
        description="Underlying retrieval result for debugging"
    )
    processing_time_ms: float = Field(
        default=0.0,
        description="Total processing time in milliseconds"
    )
    
    # Response metadata
    session_id: Optional[str] = Field(
        default=None,
        description="Session identifier"
    )
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class IngestionResult(BaseModel):
    """Result of a knowledge base ingestion operation."""
    
    status: str = Field(description="Status of ingestion (ok, error, partial)")
    total_entries: int = Field(default=0, description="Total entries processed")
    successful_entries: int = Field(default=0, description="Successfully ingested entries")
    failed_entries: int = Field(default=0, description="Failed entries")
    
    # Validation details
    validation_errors: list[str] = Field(
        default_factory=list,
        description="List of validation errors encountered"
    )
    
    # Statistics
    sections_indexed: list[str] = Field(
        default_factory=list,
        description="List of sections indexed"
    )
    intents_indexed: list[str] = Field(
        default_factory=list,
        description="List of intents indexed"
    )
    
    collection_name: str = Field(default="", description="ChromaDB collection name")
    ingestion_time_seconds: float = Field(default=0.0, description="Time taken")


class HealthStatus(BaseModel):
    """Health status of the Provider RAG service."""
    
    status: str = Field(description="Overall status (healthy, unhealthy, degraded)")
    collection_count: int = Field(default=0, description="Number of documents in collection")
    embedding_model_loaded: bool = Field(default=False)
    bm25_index_loaded: bool = Field(default=False)
    last_ingestion: Optional[datetime] = Field(default=None)
    error_message: Optional[str] = Field(default=None)
