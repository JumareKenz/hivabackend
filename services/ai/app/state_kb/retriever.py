"""
Retriever for state/provider KBs.

Each KB has its own ChromaDB collection, so retrieval is naturally isolated.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from sentence_transformers import SentenceTransformer

from app.core.config import settings
from app.state_kb.store import get_or_create_collection

logger = logging.getLogger(__name__)


_embedder: Optional[SentenceTransformer] = None


def _get_embedder() -> SentenceTransformer:
    """Get or create the embedding model singleton."""
    global _embedder
    if _embedder is None:
        model_name = getattr(settings, "EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
        logger.info(f"Initializing embedding model: {model_name}")
        try:
            _embedder = SentenceTransformer(model_name)
            logger.info(f"Embedding model loaded successfully: {model_name}")
        except Exception as e:
            logger.error(f"Failed to load embedding model {model_name}: {e}")
            raise
    return _embedder


def retrieve(kb_id: str, query: str, k: int = 5) -> str:
    """
    Retrieve relevant documents from a knowledge base.
    
    Args:
        kb_id: Knowledge base identifier (e.g., 'adamawa', 'providers')
        query: User query string
        k: Number of documents to retrieve (default: 5)
        
    Returns:
        Formatted context string with retrieved documents, or empty string on error
    """
    query = (query or "").strip()
    if not query:
        logger.warning(f"Empty query provided for kb_id={kb_id}")
        return ""

    try:
        # Get collection for this KB
        collection = get_or_create_collection(kb_id)
        logger.debug(f"Retrieving from kb_id={kb_id}, collection={collection.name}, k={k}")
        
        # Check if collection has any documents
        collection_count = collection.count()
        if collection_count == 0:
            logger.warning(f"Collection {collection.name} for kb_id={kb_id} is empty. Run ingestion first.")
            return ""
        
        # Generate query embedding
        embedder = _get_embedder()
        try:
            query_embedding = embedder.encode([query], show_progress_bar=False).tolist()[0]
        except Exception as e:
            logger.error(f"Failed to encode query for kb_id={kb_id}: {e}")
            return ""

        # Query the collection
        try:
            res = collection.query(
                query_embeddings=[query_embedding],
                n_results=max(int(k), 1),
                include=["documents", "metadatas", "distances"],
            )
        except Exception as e:
            logger.error(f"Failed to query collection for kb_id={kb_id}: {e}")
            return ""

        docs = (res.get("documents") or [[]])[0]
        mds = (res.get("metadatas") or [[]])[0]
        distances = (res.get("distances") or [[]])[0]

        if not docs:
            logger.info(f"No documents retrieved for kb_id={kb_id}, query='{query[:50]}...'")
            return ""

        # Format retrieved documents (without source markers - they're for internal use only)
        parts: list[str] = []
        for i, doc in enumerate(docs):
            # Just include the document text, no source markers
            # Source information is kept in metadata for internal tracking but not shown to users
            parts.append(doc.strip())

        result = "\n\n---\n\n".join(parts).strip()
        logger.debug(f"Retrieved {len(docs)} documents for kb_id={kb_id}, query length={len(query)}")
        return result

    except Exception as e:
        logger.error(f"Error retrieving from kb_id={kb_id}: {e}", exc_info=True)
        return ""


