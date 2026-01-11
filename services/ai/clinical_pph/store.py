"""
Vector store helpers for Clinical PPH knowledge base (ChromaDB).

This module provides a persistent vector store using ChromaDB, isolated
from other knowledge bases in the system.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from chromadb import PersistentClient
from chromadb.config import Settings as ChromaSettings
from chromadb.api.models.Collection import Collection


# Base directory for the clinical_pph module
BASE_DIR = Path(__file__).resolve().parent
CHROMA_DIR = BASE_DIR / "db"
COLLECTION_NAME = "clinical_pph_collection"

_client: Optional[PersistentClient] = None


def get_client() -> PersistentClient:
    """
    Get or create the ChromaDB persistent client.
    
    Returns:
        Persistent ChromaDB client instance
    """
    global _client
    if _client is None:
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        _client = PersistentClient(
            path=str(CHROMA_DIR),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
    return _client


def get_or_create_collection() -> Collection:
    """
    Get or create the Clinical PPH collection in ChromaDB.
    
    Returns:
        ChromaDB collection for Clinical PPH documents
    """
    client = get_client()
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={
            "kb_id": "clinical_pph",
            "description": "Clinical PPH (Postpartum Hemorrhage) knowledge base - FAQs and policy documents",
            "domain": "clinical",
            "topic": "postpartum_hemorrhage"
        },
    )


def delete_collection():
    """
    Delete the Clinical PPH collection.
    Useful for re-ingestion or cleanup.
    """
    client = get_client()
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass


def get_collection_count() -> int:
    """
    Get the number of documents in the collection.
    
    Returns:
        Number of documents in the collection, or 0 if collection doesn't exist
    """
    try:
        collection = get_or_create_collection()
        return collection.count()
    except Exception:
        return 0


