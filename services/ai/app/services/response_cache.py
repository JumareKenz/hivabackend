"""
Smart response cache that maintains context and accuracy
"""
import hashlib
import json
from typing import Optional, Dict, Tuple
from datetime import datetime, timedelta
from collections import OrderedDict


class SmartResponseCache:
    """
    Intelligent response cache that:
    - Maintains context awareness
    - Respects branch-specific responses
    - Invalidates when conversation changes
    - Only caches when safe (no recent context changes)
    """
    
    def __init__(self, max_size: int = 256, ttl_minutes: int = 60):
        """
        Args:
            max_size: Maximum number of cached responses
            ttl_minutes: Time to live for cached responses in minutes
        """
        self.max_size = max_size
        self.ttl = timedelta(minutes=ttl_minutes)
        self._cache: OrderedDict[str, Dict] = OrderedDict()
        self._context_hashes: Dict[str, str] = {}  # session_id -> context hash
    
    def _get_context_hash(self, conversation_history: list, branch_id: Optional[str] = None) -> str:
        """Generate hash of conversation context"""
        # Only use last 2 messages for context hash (recent context matters most)
        recent_context = conversation_history[-2:] if len(conversation_history) >= 2 else conversation_history
        context_str = json.dumps({
            "history": [{"role": m.get("role"), "content": m.get("content", "")[:100]} for m in recent_context],
            "branch": branch_id
        }, sort_keys=True)
        return hashlib.md5(context_str.encode()).hexdigest()
    
    def _get_cache_key(
        self,
        query: str,
        branch_id: Optional[str] = None,
        context_hash: Optional[str] = None
    ) -> str:
        """Generate cache key including context"""
        key_parts = [query.lower().strip(), branch_id or "", context_hash or ""]
        key_str = "|".join(key_parts)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def get(
        self,
        query: str,
        session_id: str,
        conversation_history: list,
        branch_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Get cached response if available and context matches
        
        Returns:
            Cached response if found and context matches, None otherwise
        """
        # Get current context hash
        current_context_hash = self._get_context_hash(conversation_history, branch_id)
        
        # Check if context has changed significantly
        if session_id in self._context_hashes:
            previous_hash = self._context_hashes[session_id]
            # If context changed significantly, don't use cache
            if previous_hash != current_context_hash:
                return None
        
        # Generate cache key
        cache_key = self._get_cache_key(query, branch_id, current_context_hash)
        
        # Check cache
        if cache_key in self._cache:
            entry = self._cache[cache_key]
            
            # Check TTL
            if datetime.now() - entry["timestamp"] > self.ttl:
                del self._cache[cache_key]
                return None
            
            # Move to end (LRU)
            self._cache.move_to_end(cache_key)
            
            return entry["response"]
        
        return None
    
    def set(
        self,
        query: str,
        response: str,
        session_id: str,
        conversation_history: list,
        branch_id: Optional[str] = None,
        min_length: int = 20
    ):
        """
        Cache response if conditions are met
        
        Args:
            query: User query
            response: AI response
            session_id: Session ID
            conversation_history: Current conversation history
            branch_id: Branch ID
            min_length: Minimum response length to cache
        """
        # Only cache substantial responses
        if len(response) < min_length:
            return
        
        # Only cache if conversation history is short (recent queries)
        # This ensures cached responses are still contextually relevant
        if len(conversation_history) > 5:
            return  # Don't cache if too much conversation history
        
        # Get context hash
        context_hash = self._get_context_hash(conversation_history, branch_id)
        
        # Store context hash for session
        self._context_hashes[session_id] = context_hash
        
        # Generate cache key
        cache_key = self._get_cache_key(query, branch_id, context_hash)
        
        # Store in cache
        self._cache[cache_key] = {
            "response": response,
            "timestamp": datetime.now(),
            "query": query,
            "branch_id": branch_id
        }
        
        # Move to end (LRU)
        self._cache.move_to_end(cache_key)
        
        # Evict oldest if over limit
        if len(self._cache) > self.max_size:
            self._cache.popitem(last=False)  # Remove oldest
    
    def invalidate_session(self, session_id: str):
        """Invalidate cache for a specific session"""
        if session_id in self._context_hashes:
            del self._context_hashes[session_id]
    
    def clear(self):
        """Clear all cache"""
        self._cache.clear()
        self._context_hashes.clear()
    
    def get_stats(self) -> Dict:
        """Get cache statistics"""
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "sessions": len(self._context_hashes)
        }


# Global response cache instance (will be initialized after settings)
response_cache = None


def get_response_cache():
    """Get or create response cache instance"""
    global response_cache
    if response_cache is None:
        from app.core.config import settings
        response_cache = SmartResponseCache(
            max_size=getattr(settings, "RESPONSE_CACHE_SIZE", 256),
            ttl_minutes=60
        )
    return response_cache

