"""
Embedding generation module for Zamfara RAG system.

Generates high-quality vector embeddings using SentenceTransformers
for both document chunks and queries.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Union
import numpy as np

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """
    Generates embeddings for documents and queries.
    
    Features:
    - Singleton model instance for efficiency
    - Batch processing support
    - Query-specific optimization
    - Caching for repeated embeddings
    """
    
    _instance: Optional["EmbeddingGenerator"] = None
    _model: Optional[SentenceTransformer] = None
    
    def __new__(cls, *args, **kwargs):
        """Singleton pattern for embedding generator."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(
        self,
        model_name: str = "BAAI/bge-small-en-v1.5",
        device: Optional[str] = None,
        normalize: bool = True,
    ):
        """
        Initialize the embedding generator.
        
        Args:
            model_name: HuggingFace model name for embeddings
            device: Device to run model on (None for auto)
            normalize: Whether to L2-normalize embeddings
        """
        if SentenceTransformer is None:
            raise ImportError(
                "sentence-transformers is required. "
                "Install with: pip install sentence-transformers"
            )
        
        self.model_name = model_name
        self.device = device
        self.normalize = normalize
        
        # Initialize model if not already done
        if EmbeddingGenerator._model is None:
            logger.info(f"Loading embedding model: {model_name}")
            EmbeddingGenerator._model = SentenceTransformer(
                model_name,
                device=device
            )
            logger.info(f"Embedding model loaded: {model_name}")
        
        self._model = EmbeddingGenerator._model
        self._embedding_dim = self._model.get_sentence_embedding_dimension()
        
        # Simple cache for query embeddings
        self._query_cache: dict[str, List[float]] = {}
        self._cache_max_size = 1000
    
    @property
    def embedding_dimension(self) -> int:
        """Get the embedding dimension."""
        return self._embedding_dim
    
    def embed_documents(
        self,
        texts: List[str],
        batch_size: int = 32,
        show_progress: bool = True
    ) -> np.ndarray:
        """
        Generate embeddings for documents.
        
        Args:
            texts: List of document texts to embed
            batch_size: Batch size for encoding
            show_progress: Show progress bar
            
        Returns:
            NumPy array of embeddings (n_docs, embedding_dim)
        """
        if not texts:
            return np.array([])
        
        logger.info(f"Generating embeddings for {len(texts)} documents")
        
        # Clean texts
        cleaned_texts = [self._prepare_text(t) for t in texts]
        
        # Generate embeddings
        embeddings = self._model.encode(
            cleaned_texts,
            batch_size=batch_size,
            show_progress_bar=show_progress,
            normalize_embeddings=self.normalize,
        )
        
        logger.info(f"Generated {len(embeddings)} embeddings")
        
        return embeddings
    
    def embed_query(
        self,
        query: str,
        use_cache: bool = True
    ) -> List[float]:
        """
        Generate embedding for a single query.
        
        Args:
            query: Query text to embed
            use_cache: Whether to use cached embeddings
            
        Returns:
            List of floats representing the embedding
        """
        if not query or not query.strip():
            return [0.0] * self._embedding_dim
        
        # Check cache
        cache_key = query.strip().lower()
        if use_cache and cache_key in self._query_cache:
            return self._query_cache[cache_key]
        
        # Prepare query
        prepared_query = self._prepare_query(query)
        
        # Generate embedding
        embedding = self._model.encode(
            [prepared_query],
            normalize_embeddings=self.normalize,
            show_progress_bar=False,
        )[0].tolist()
        
        # Cache result
        if use_cache:
            self._update_cache(cache_key, embedding)
        
        return embedding
    
    def embed_queries(
        self,
        queries: List[str],
        use_cache: bool = True
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple queries.
        
        Args:
            queries: List of query texts
            use_cache: Whether to use cache
            
        Returns:
            List of embedding lists
        """
        results = []
        uncached_queries = []
        uncached_indices = []
        
        # Check cache for each query
        for i, query in enumerate(queries):
            cache_key = query.strip().lower()
            if use_cache and cache_key in self._query_cache:
                results.append(self._query_cache[cache_key])
            else:
                results.append(None)
                uncached_queries.append(query)
                uncached_indices.append(i)
        
        # Embed uncached queries
        if uncached_queries:
            prepared = [self._prepare_query(q) for q in uncached_queries]
            embeddings = self._model.encode(
                prepared,
                normalize_embeddings=self.normalize,
                show_progress_bar=False,
            ).tolist()
            
            # Update results and cache
            for i, (idx, embedding) in enumerate(zip(uncached_indices, embeddings)):
                results[idx] = embedding
                if use_cache:
                    cache_key = uncached_queries[i].strip().lower()
                    self._update_cache(cache_key, embedding)
        
        return results
    
    def _prepare_text(self, text: str) -> str:
        """Prepare document text for embedding."""
        if not text:
            return ""
        
        # Basic cleaning
        text = text.strip()
        
        # Truncate very long texts (model max is typically 512 tokens)
        max_chars = 8000  # ~2000 tokens
        if len(text) > max_chars:
            text = text[:max_chars]
        
        return text
    
    def _prepare_query(self, query: str) -> str:
        """
        Prepare query for embedding.
        
        Some models benefit from query prefixes for asymmetric search.
        BGE models use "query: " prefix for better retrieval.
        """
        if not query:
            return ""
        
        query = query.strip()
        
        # Add query prefix for BGE models
        if "bge" in self.model_name.lower():
            if not query.lower().startswith("query:"):
                query = f"query: {query}"
        
        return query
    
    def _update_cache(self, key: str, embedding: List[float]) -> None:
        """Update the query cache with LRU eviction."""
        if len(self._query_cache) >= self._cache_max_size:
            # Remove oldest entry (simple FIFO)
            oldest_key = next(iter(self._query_cache))
            del self._query_cache[oldest_key]
        
        self._query_cache[key] = embedding
    
    def clear_cache(self) -> None:
        """Clear the query embedding cache."""
        self._query_cache.clear()
        logger.info("Embedding cache cleared")
    
    def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        return {
            "cache_size": len(self._query_cache),
            "max_cache_size": self._cache_max_size,
            "model_name": self.model_name,
            "embedding_dimension": self._embedding_dim,
        }




