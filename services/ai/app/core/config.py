# core/config.py
from pydantic_settings import BaseSettings
from pydantic import AnyHttpUrl
from typing import Optional

class Settings(BaseSettings):
    SERVICE_NAME: str = "hiva-llm-engine"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    API_BASE_URL: str = "http://localhost:8000"  # Update with your server's public URL
    ALLOWED_ORIGINS: list = [
        "https://hiva-two.vercel.app",
        "http://localhost:3000",
        "http://localhost:5173",
    ]
    LLM_API_URL: AnyHttpUrl = "http://localhost:11434"
    LLM_MODEL: str = "phi3:latest"  # Use phi3:latest (or phi3:mini if you have it)
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"  # Better accuracy than all-MiniLM-L6-v2, optimized for retrieval
    LLM_TIMEOUT: int = 300  # Increased for better reliability
    WARMUP_PROMPT: str = "warm up"
    DEFAULT_NUM_PREDICT: int = 300  # Optimized for speed and frontend UX (was 512)
    ENABLE_WARMUP: bool = True  # Warm up Ollama on startup
    OPTIMIZE_FOR_SPEED: bool = True  # Enable speed optimizations
    STREAM_CHUNK_SIZE: int = 64
    STREAM_BUFFER_SIZE: int = 30  # Buffer size for streaming (chars before sending)
    MAX_CONVERSATION_HISTORY: int = 10
    RAG_TOP_K: int = 5
    CACHE_SIZE: int = 128
    RESPONSE_CACHE_SIZE: int = 256  # Full response cache size
    RESPONSE_CACHE_ENABLED: bool = True  # Enable smart response caching
    RESPONSE_CACHE_MIN_LENGTH: int = 20  # Minimum response length to cache
    RESPONSE_CACHE_SIZE: int = 256  # Full response cache size
    RESPONSE_CACHE_ENABLED: bool = True  # Enable smart response caching
    RESPONSE_CACHE_MIN_LENGTH: int = 20  # Minimum response length to cache

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
