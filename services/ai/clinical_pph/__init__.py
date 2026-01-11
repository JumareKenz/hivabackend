"""
Clinical PPH (Postpartum Hemorrhage) RAG System

A dedicated RAG system for clinical PPH knowledge base, providing:
- Document ingestion from FAQ and policy documents
- Vector-based retrieval using ChromaDB
- Conversational context management
- RESTful API endpoints
"""

from .store import get_or_create_collection, delete_collection, get_client
from .retriever import retrieve
from .service import ClinicalPPHService, clinical_pph_service
from .ingest import ingest, ingest_all

__all__ = [
    "get_or_create_collection",
    "delete_collection",
    "get_client",
    "retrieve",
    "ClinicalPPHService",
    "clinical_pph_service",
    "ingest",
    "ingest_all",
]


