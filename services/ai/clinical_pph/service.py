"""
Async Clinical PPH retrieval service with caching and error handling.

This service provides an async interface to the Clinical PPH retriever,
with built-in caching for improved performance and comprehensive error handling.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import Optional

from .retriever import retrieve

logger = logging.getLogger(__name__)


class ClinicalPPHService:
    """
    Async service for retrieving documents from the Clinical PPH knowledge base.
    
    Features:
    - LRU cache for frequently accessed queries
    - Async execution to avoid blocking
    - Error handling and logging
    - Configurable cache size
    """
    
    def __init__(self, cache_size: int = 256):
        """
        Initialize the service.
        
        Args:
            cache_size: Maximum number of cached query results (default: 256)
        """
        self.cache_size = cache_size
        self._cache: dict[str, str] = {}
        self._cache_access_order: list[str] = []  # For LRU eviction
        logger.info(f"ClinicalPPHService initialized with cache_size={cache_size}")

    def _cache_key(self, query: str, k: int) -> str:
        """
        Generate a cache key for a query.
        
        Args:
            query: User query string
            k: Number of documents to retrieve
            
        Returns:
            MD5 hash of the cache key
        """
        return hashlib.md5(f"clinical_pph:{query}:{k}".encode("utf-8")).hexdigest()

    async def retrieve_async(
        self, 
        query: str, 
        k: int = 5, 
        use_cache: bool = True
    ) -> str:
        """
        Retrieve documents asynchronously with caching.
        
        Args:
            query: User query string
            k: Number of documents to retrieve (default: 5)
            use_cache: Whether to use cache (default: True)
            
        Returns:
            Formatted context string with retrieved documents
        """
        if not query or not query.strip():
            logger.warning("Empty query provided to retrieve_async")
            return ""

        # Check cache
        if use_cache:
            key = self._cache_key(query, k)
            if key in self._cache:
                # Move to end (most recently used)
                if key in self._cache_access_order:
                    self._cache_access_order.remove(key)
                self._cache_access_order.append(key)
                logger.debug(f"Cache hit for query='{query[:50]}...'")
                return self._cache[key]

        # Retrieve from vector store (run in executor to avoid blocking)
        try:
            ctx = await asyncio.get_event_loop().run_in_executor(
                None, 
                retrieve, 
                query, 
                k
            )
        except Exception as e:
            logger.error(f"Error in retrieve_async: {e}", exc_info=True)
            return ""

        # Update cache
        if use_cache and ctx:
            key = self._cache_key(query, k)
            
            # LRU eviction: remove oldest if cache is full
            if len(self._cache) >= self.cache_size:
                if self._cache_access_order:
                    oldest_key = self._cache_access_order.pop(0)
                    del self._cache[oldest_key]
                    logger.debug(f"Cache evicted oldest entry (cache_size={self.cache_size})")
            
            # Add new entry
            self._cache[key] = ctx
            self._cache_access_order.append(key)
            logger.debug(f"Cached result for query='{query[:50]}...'")

        return ctx

    def clear_cache(self):
        """Clear the query cache."""
        self._cache.clear()
        self._cache_access_order.clear()
        logger.info("ClinicalPPHService cache cleared")

    def get_cache_stats(self) -> dict:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache size, max size, and utilization percentage
        """
        return {
            "cache_size": len(self._cache),
            "max_cache_size": self.cache_size,
            "cache_utilization": len(self._cache) / self.cache_size if self.cache_size > 0 else 0
        }


# Global service instance
clinical_pph_service = ClinicalPPHService()


