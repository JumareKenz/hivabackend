"""
RAG service for branch FAQs.

Provides async wrapper around the branch FAQ retriever.
"""

from __future__ import annotations

import asyncio
import hashlib
from typing import Optional

from app.rag.retriever import retrieve


class RAGService:
    """
    Async RAG service with caching for branch FAQs.
    """
    
    def __init__(self, cache_size: int = 256):
        """
        Initialize the service.
        
        Args:
            cache_size: Maximum number of cached query results (default: 256)
        """
        self.cache_size = cache_size
        self._cache: dict[str, str] = {}
        self._cache_access_order: list[str] = []

    def _cache_key(self, query: str, k: int, branch_id: Optional[str]) -> str:
        """Generate a cache key for a query."""
        key_str = f"{query}:{k}:{branch_id or 'none'}"
        return hashlib.md5(key_str.encode("utf-8")).hexdigest()

    async def retrieve_async(
        self, 
        query: str, 
        k: int = 5, 
        branch_id: Optional[str] = None,
        use_cache: bool = True
    ) -> str:
        """
        Retrieve documents asynchronously with caching.
        
        Args:
            query: User query string
            k: Number of documents to retrieve
            branch_id: Optional branch identifier for branch-specific retrieval
            use_cache: Whether to use cache (default: True)
            
        Returns:
            Formatted context string with retrieved documents
        """
        if not query or not query.strip():
            return ""

        # Check cache
        if use_cache:
            key = self._cache_key(query, k, branch_id)
            if key in self._cache:
                # Move to end (most recently used)
                if key in self._cache_access_order:
                    self._cache_access_order.remove(key)
                self._cache_access_order.append(key)
                return self._cache[key]

        # Retrieve from vector store (run in executor to avoid blocking)
        try:
            ctx = await asyncio.get_event_loop().run_in_executor(
                None, 
                lambda: retrieve(query, k, branch_id)
            )
        except Exception as e:
            import logging
            logging.error(f"Error in retrieve_async: {e}")
            return ""

        # Update cache
        if use_cache and ctx:
            key = self._cache_key(query, k, branch_id)
            
            # LRU eviction: remove oldest if cache is full
            if len(self._cache) >= self.cache_size:
                if self._cache_access_order:
                    oldest_key = self._cache_access_order.pop(0)
                    del self._cache[oldest_key]
            
            # Add new entry
            self._cache[key] = ctx
            self._cache_access_order.append(key)

        return ctx

    def clear_cache(self):
        """Clear the query cache."""
        self._cache.clear()
        self._cache_access_order.clear()

    def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        return {
            "cache_size": len(self._cache),
            "max_cache_size": self.cache_size,
            "cache_utilization": len(self._cache) / self.cache_size if self.cache_size > 0 else 0
        }


rag_service = RAGService()

