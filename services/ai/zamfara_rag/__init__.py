"""
Zamfara RAG System - Enterprise-grade Retrieval-Augmented Generation

A high-quality FAQ chatbot system designed for government and administrative
use cases. Uses the Zamfara directory containing policy documents and
operational guidelines.

Modules:
- preprocessing: Document loading, cleaning, and normalization
- embeddings: Vector embedding generation and management
- vector_store: ChromaDB-based vector storage and indexing
- retrieval: Query processing and document retrieval with re-ranking
- generation: LLM-powered answer generation with citations
- evaluation: Answer quality verification and hallucination detection

Usage:
    # Ingest documents
    python -m zamfara_rag.main ingest --clear
    
    # Query
    python -m zamfara_rag.main query "What is the health policy?"
    
    # Interactive mode
    python -m zamfara_rag.main interactive
"""

__version__ = "1.0.0"
__author__ = "HIVA AI Team"

# Lazy imports to avoid circular dependencies
def get_pipeline():
    """Get the ZamfaraRAGPipeline class."""
    from zamfara_rag.main import ZamfaraRAGPipeline
    return ZamfaraRAGPipeline

def get_settings():
    """Get the RAG settings."""
    from zamfara_rag.config.settings import rag_settings
    return rag_settings

__all__ = [
    "get_pipeline",
    "get_settings",
    "__version__",
]

