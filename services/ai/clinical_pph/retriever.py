"""
Retriever for Clinical PPH knowledge base.

This module handles semantic search and retrieval of relevant documents
from the Clinical PPH vector store using sentence transformers for embeddings.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from sentence_transformers import SentenceTransformer

from app.core.config import settings
from .store import get_or_create_collection

logger = logging.getLogger(__name__)

_embedder: Optional[SentenceTransformer] = None


def _get_embedder() -> SentenceTransformer:
    """
    Get or create the embedding model singleton.
    
    Uses the embedding model specified in settings, defaulting to
    BAAI/bge-small-en-v1.5 for efficient and accurate embeddings.
    
    Returns:
        SentenceTransformer model instance
    """
    global _embedder
    if _embedder is None:
        model_name = getattr(settings, "EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
        logger.info(f"Initializing embedding model for Clinical PPH: {model_name}")
        try:
            _embedder = SentenceTransformer(model_name)
            logger.info(f"Embedding model loaded successfully: {model_name}")
        except Exception as e:
            logger.error(f"Failed to load embedding model {model_name}: {e}")
            raise
    return _embedder


def retrieve(query: str, k: int = 5) -> str:
    """
    Retrieve relevant documents from the Clinical PPH knowledge base.
    
    This function performs semantic search using vector similarity to find
    the most relevant document chunks for the given query.
    
    Args:
        query: User query string (e.g., "What are the symptoms of PPH?")
        k: Number of documents to retrieve (default: 5)
        
    Returns:
        Formatted context string with retrieved documents, or empty string on error.
        Documents are formatted with separators for easy reading by the LLM.
    """
    query = (query or "").strip()
    if not query:
        logger.warning("Empty query provided to Clinical PPH retriever")
        return ""

    try:
        # Get collection for Clinical PPH
        collection = get_or_create_collection()
        logger.debug(f"Retrieving from Clinical PPH collection, k={k}")
        
        # Check if collection has any documents
        collection_count = collection.count()
        if collection_count == 0:
            logger.warning(
                "Clinical PPH collection is empty. Run ingestion first: "
                "python -m clinical_pph.ingest"
            )
            return ""
        
        # Generate query embedding
        embedder = _get_embedder()
        try:
            query_embedding = embedder.encode([query], show_progress_bar=False).tolist()[0]
        except Exception as e:
            logger.error(f"Failed to encode query for Clinical PPH: {e}")
            return ""

        # Query the collection
        try:
            res = collection.query(
                query_embeddings=[query_embedding],
                n_results=max(int(k), 1),
                include=["documents", "metadatas", "distances"],
            )
        except Exception as e:
            logger.error(f"Failed to query Clinical PPH collection: {e}")
            return ""

        docs = (res.get("documents") or [[]])[0]
        mds = (res.get("metadatas") or [[]])[0]
        distances = (res.get("distances") or [[]])[0]

        if not docs:
            logger.info(f"No documents retrieved for query: '{query[:50]}...'")
            return ""

        # Format retrieved documents (without source markers - for internal use only)
        # Source information is kept in metadata for internal tracking but not shown to users
        parts: list[str] = []
        for i, doc in enumerate(docs):
            # Include document text only, no source citations
            parts.append(doc.strip())
            # Log distance for debugging (lower is better)
            if distances and i < len(distances):
                logger.debug(f"Document {i+1} distance: {distances[i]:.4f}")

        result = "\n\n---\n\n".join(parts).strip()
        logger.debug(f"Retrieved {len(docs)} documents for query length={len(query)}")
        return result

    except Exception as e:
        logger.error(f"Error retrieving from Clinical PPH knowledge base: {e}", exc_info=True)
        return ""

