"""
Configuration settings for the Zamfara RAG system.

Centralizes all configurable parameters for document processing,
chunking, embedding, retrieval, and generation.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Set
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@dataclass
class RAGSettings:
    """Configuration settings for the Zamfara RAG system."""
    
    # === Paths ===
    # Base directory for all RAG data
    base_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent)
    
    # Source documents directory (Zamfara folder)
    source_docs_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent.parent / "app" / "rag" / "faqs" / "branches" / "zamfara")
    
    # Vector store directory
    vector_store_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent / "vector_store" / "db")
    
    # === Document Processing ===
    # Supported file formats
    supported_formats: Set[str] = field(default_factory=lambda: {".pdf", ".docx", ".txt", ".md"})
    
    # Maximum file size to process (in MB)
    max_file_size_mb: int = 50
    
    # === Chunking Strategy ===
    # Target chunk size in tokens (semantic units)
    chunk_size_tokens: int = 500  # ~300-700 token range
    
    # Character-based chunk size (fallback)
    chunk_size_chars: int = 1500  # Approx 375 tokens at 4 chars/token
    
    # Overlap percentage (10-20% as specified)
    chunk_overlap_percent: float = 0.15
    
    # Minimum chunk size to prevent tiny fragments
    min_chunk_size_chars: int = 200
    
    # === Embedding Model ===
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    
    # Batch size for embedding generation
    embedding_batch_size: int = 32
    
    # === Vector Store ===
    collection_name: str = "zamfara_kb"
    
    # Similarity metric
    distance_metric: str = "cosine"
    
    # === Retrieval ===
    # Default number of documents to retrieve
    default_top_k: int = 5
    
    # Maximum number of documents to retrieve
    max_top_k: int = 15
    
    # Re-ranking enabled by default
    enable_reranking: bool = True
    
    # Minimum similarity score threshold (0-1)
    min_similarity_threshold: float = 0.3
    
    # === Generation ===
    # LLM API configuration
    llm_api_url: str = field(default_factory=lambda: os.getenv("LLM_API_URL", "http://localhost:11434"))
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "llama3:latest"))
    llm_api_key: Optional[str] = field(default_factory=lambda: os.getenv("LLM_API_KEY"))
    
    # Generation parameters
    temperature: float = 0.1  # Low for factual accuracy
    max_tokens: int = 1024
    
    # === Hallucination Guard ===
    # Enable self-verification
    enable_verification: bool = True
    
    # Verification confidence threshold
    verification_threshold: float = 0.7
    
    # Maximum regeneration attempts
    max_regeneration_attempts: int = 2
    
    # === Document Type Classification ===
    # Keywords for document type inference
    document_type_keywords: dict = field(default_factory=lambda: {
        "policy": ["policy", "regulation", "act", "law", "statute", "decree", "directive"],
        "guideline": ["guideline", "guidance", "guide", "manual", "handbook"],
        "sop": ["procedure", "sop", "standard operating", "process", "workflow"],
        "faq": ["faq", "frequently asked", "questions", "answers", "q&a"],
        "gazette": ["gazette", "official", "government", "publication"],
        "opg": ["operational", "operations", "opg", "administrative"]
    })
    
    # Department/topic keywords for metadata inference
    department_keywords: dict = field(default_factory=lambda: {
        "health": ["health", "medical", "hospital", "clinic", "disease", "treatment"],
        "finance": ["finance", "budget", "revenue", "expenditure", "fiscal", "tax"],
        "education": ["education", "school", "student", "teacher", "curriculum"],
        "agriculture": ["agriculture", "farming", "crop", "livestock", "rural"],
        "infrastructure": ["infrastructure", "road", "building", "construction", "water"],
        "administration": ["administration", "civil service", "government", "public", "ministry"],
        "legal": ["legal", "court", "justice", "law", "judicial"]
    })
    
    def __post_init__(self):
        """Ensure directories exist."""
        self.vector_store_dir.mkdir(parents=True, exist_ok=True)
        (self.base_dir / "data" / "raw_docs").mkdir(parents=True, exist_ok=True)


# Global settings instance
rag_settings = RAGSettings()




