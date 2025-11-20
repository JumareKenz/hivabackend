"""
Performance optimization utilities
"""
import asyncio
from functools import lru_cache
from typing import Optional
from app.services.ollama_client import get_ollama_client
from app.core.config import settings


class PerformanceOptimizer:
    """Optimize system performance"""
    
    @staticmethod
    async def warmup_ollama():
        """Warm up Ollama with a simple request"""
        try:
            client = await get_ollama_client()
            await client.chat(
                messages=[{"role": "user", "content": "hi"}],
                options={"num_predict": 10, "temperature": 0.1}
            )
            print("✅ Ollama warmed up")
        except Exception as e:
            print(f"⚠️  Ollama warmup failed: {e}")
    
    @staticmethod
    def get_optimized_llm_options(query_length: int = 0) -> dict:
        """
        Get optimized LLM options based on query length
        
        Args:
            query_length: Length of user query
            
        Returns:
            Optimized options dict
        """
        # Shorter responses for simple queries
        if query_length < 50:
            num_predict = 256  # Shorter responses
        elif query_length < 150:
            num_predict = 384  # Medium responses
        else:
            num_predict = settings.DEFAULT_NUM_PREDICT  # Full length
        
        return {
            "num_predict": min(num_predict, 400),  # Cap at 400 for speed
            "temperature": 0.5,  # Lower = faster, more deterministic
            "top_p": 0.85,  # Slightly lower for speed
            "repeat_penalty": 1.1,
            "num_ctx": 2048,  # Smaller context window = faster
            "num_thread": 4,  # Use 4 threads (you have 20 CPUs)
        }

