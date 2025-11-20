"""
Optimized RAG service with caching and async operations
"""
import asyncio
from typing import List, Optional
from functools import lru_cache
import hashlib
from app.rag.retriever import retrieve
from app.core.config import settings


class RAGService:
    """High-performance RAG service with caching"""
    
    def __init__(self, cache_size: int = 128):
        self.cache_size = cache_size
        self._cache: dict = {}
    
    def _get_cache_key(self, query: str, k: int, branch_id: Optional[str] = None) -> str:
        """Generate cache key for query"""
        key_str = f"{query}:{k}:{branch_id or ''}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    async def retrieve_async(
        self,
        query: str,
        k: int = 5,
        branch_id: Optional[str] = None,
        use_cache: bool = True,
        fast_mode: bool = True  # Reduce k for faster retrieval
    ) -> str:
        """
        Async retrieval with caching
        
        Args:
            query: User query
            k: Number of documents to retrieve
            branch_id: Optional branch ID for branch-specific retrieval
            use_cache: Whether to use cache
        """
        # Check cache
        if use_cache:
            cache_key = self._get_cache_key(query, k, branch_id)
            if cache_key in self._cache:
                return self._cache[cache_key]
        
        # Optimize k for speed if fast_mode
        effective_k = min(k, 3) if fast_mode else k
        
        # Run retrieval in executor to avoid blocking
        # Use None to get the default ThreadPoolExecutor (Python 3.12 compatible)
        # Pass branch_id to retrieve function for filtering
        context = await asyncio.get_event_loop().run_in_executor(
            None,  # None uses default ThreadPoolExecutor
            retrieve,
            query,
            effective_k,
            branch_id  # Pass branch_id for branch-specific retrieval
        )
        
        # Cache result
        if use_cache and context:
            cache_key = self._get_cache_key(query, k, branch_id)
            if len(self._cache) >= self.cache_size:
                # Remove oldest entry (simple FIFO)
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
            self._cache[cache_key] = context
        
        return context
    
    def clear_cache(self):
        """Clear the retrieval cache"""
        self._cache.clear()


# Global RAG service instance
rag_service = RAGService()

