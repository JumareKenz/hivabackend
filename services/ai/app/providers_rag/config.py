"""
Configuration for the Provider RAG System.

All parameters are tuned for production-grade, zero-hallucination operation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from app.core.config import settings


@dataclass(frozen=True)
class ProviderRAGConfig:
    """Production configuration for Provider RAG system."""
    
    # ============================================
    # KNOWLEDGE BASE SETTINGS
    # ============================================
    
    # Path to provider knowledge documents
    knowledge_base_path: Path = field(
        default_factory=lambda: Path(__file__).parent.parent / "rag" / "faqs" / "providers"
    )
    
    # ChromaDB collection name for providers
    collection_name: str = "provider_kb_v2"
    
    # Vector store path
    vector_store_path: Path = field(
        default_factory=lambda: Path(__file__).parent.parent / "rag" / "db" / "provider_kb"
    )
    
    # ============================================
    # CHUNKING SETTINGS (Optimized for Q&A format)
    # ============================================
    
    # Target chunk size (characters) - Q&A pairs are kept whole
    chunk_size: int = 500  # 300-600 tokens optimal for retrieval
    
    # Overlap between chunks
    chunk_overlap: int = 50
    
    # ============================================
    # EMBEDDING SETTINGS
    # ============================================
    
    # Embedding model - using high-quality model for semantic search
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    
    # ============================================
    # RETRIEVAL SETTINGS
    # ============================================
    
    # Number of documents to retrieve (Top-K)
    retrieval_top_k: int = 7  # Retrieve 7, filter to best 5
    
    # Minimum number of documents required for answer
    min_relevant_docs: int = 1
    
    # Maximum documents to use in final context
    max_context_docs: int = 5
    
    # ============================================
    # CONFIDENCE THRESHOLDS (CRITICAL FOR SAFETY)
    # ============================================
    
    # Minimum similarity score to consider a document relevant (0-1)
    # ChromaDB uses cosine similarity after configuration
    # Increased for stricter matching
    min_similarity_threshold: float = 0.5
    
    # High confidence threshold - very relevant match
    high_confidence_threshold: float = 0.75
    
    # Medium confidence threshold
    medium_confidence_threshold: float = 0.6
    
    # BM25 weight in hybrid retrieval (0-1)
    bm25_weight: float = 0.3
    
    # Dense (embedding) weight in hybrid retrieval
    dense_weight: float = 0.7
    
    # ============================================
    # LLM GENERATION SETTINGS
    # ============================================
    
    # Temperature for deterministic responses (CRITICAL: keep low)
    temperature: float = 0.1  # Even lower than 0.2 for maximum determinism
    
    # Maximum tokens for response
    max_response_tokens: int = 1024
    
    # ============================================
    # SAFETY SETTINGS
    # ============================================
    
    # Enable strict refusal mode (refuse if confidence below threshold)
    strict_refusal_mode: bool = True
    
    # Enable citation mode (include document references)
    # MANDATORY for production - all responses must have citations
    enable_citations: bool = True
    require_citations: bool = True  # Hard requirement - no citations = refuse
    
    # Maximum retries for retrieval
    max_retrieval_retries: int = 2
    
    # ============================================
    # RESPONSE MESSAGES
    # ============================================
    
    # Standard refusal message when information is not found
    refusal_message: str = (
        "I don't have specific information about this in the provider knowledge base. "
        "Please contact the ICT support team or visit the official portal for assistance."
    )
    
    # Low confidence message
    low_confidence_message: str = (
        "I found some potentially related information, but I'm not fully confident "
        "it addresses your specific question. Here's what I found, but please verify "
        "with ICT support if needed:\n\n"
    )
    
    # Clarification request message
    clarification_message: str = (
        "Could you please provide more details about your question? "
        "For example:\n"
        "- What specific action are you trying to perform?\n"
        "- Are you encountering a particular error message?\n"
        "- Which part of the portal are you using?"
    )


# Singleton configuration instance
provider_rag_config = ProviderRAGConfig()
