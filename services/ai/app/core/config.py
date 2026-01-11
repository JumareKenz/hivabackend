"""
Main HIVA AI service configuration.

This module is imported throughout the codebase as `from app.core.config import settings`.
It intentionally mirrors the style used by `admin_chat/app/core/config.py`, but is scoped to
the main AI service (port 8000).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic_settings import BaseSettings


# Load a shared .env from the ai/ directory (if present).
app_root = Path(__file__).parent.parent.parent  # .../ai/app -> .../ai
env_path = app_root / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()


class Settings(BaseSettings):
    """HIVA AI Service Configuration (RAG + Chat)."""

    # Service configuration
    SERVICE_NAME: str = "hiva-ai"
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    ALLOWED_ORIGINS: list[str] = [
        "https://hiva.chat",
        "https://api.hiva.chat",
        "http://localhost:3000",
        "http://localhost:5173",
        "https://hiva-two.vercel.app",
    ]

    # LLM configuration (defaults to local Ollama-compatible server)
    LLM_API_URL: str = "http://localhost:11434"
    LLM_MODEL: str = "openai/gpt-oss-20b"  # Using GPT OSS 20B model
    LLM_API_KEY: Optional[str] = None  # For Groq/OpenAI APIs
    LLM_TIMEOUT_SECONDS: int = 120
    TEMPERATURE: float = 0.2

    # Embeddings / RAG configuration
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    RAG_CHUNK_SIZE: int = 900  # characters (fast, language-agnostic)
    RAG_CHUNK_OVERLAP: int = 120
    RAG_DEFAULT_TOP_K: int = 5

    # Vector store configuration for state/provider knowledge bases
    # Currently implemented: "chroma"
    STATE_KB_VECTOR_STORE: str = "chroma"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "allow"  # allow shared env fields (admin_chat, etc.)


settings = Settings()


