"""
Production-Grade Provider RAG System

A world-class, hallucination-free knowledge assistant for provider documentation.

Key Features:
- Strict retrieval-first architecture
- Hybrid retrieval (dense + sparse/BM25)
- Confidence gating and refusal logic
- Grounded answer generation with citations
- Zero hallucination guarantee

Usage:
    from app.providers_rag import ProviderRAGService
    
    service = ProviderRAGService()
    await service.initialize()
    
    result = await service.query("How do I submit a claim?")
    print(result.answer)
    print(result.confidence)
    print(result.citations)
"""

from app.providers_rag.service import ProviderRAGService
from app.providers_rag.schemas import (
    QueryResult,
    RetrievalResult,
    DocumentChunk,
    ConfidenceLevel,
)

__all__ = [
    "ProviderRAGService",
    "QueryResult",
    "RetrievalResult",
    "DocumentChunk",
    "ConfidenceLevel",
]

__version__ = "1.0.0"
