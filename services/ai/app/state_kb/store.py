"""
Vector store helpers for state/provider KBs (ChromaDB).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from chromadb import PersistentClient
from chromadb.config import Settings as ChromaSettings
from chromadb.api.models.Collection import Collection


BASE_DIR = Path(__file__).resolve().parent
CHROMA_DIR = BASE_DIR / "db"

_client: Optional[PersistentClient] = None


def get_client() -> PersistentClient:
    global _client
    if _client is None:
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        _client = PersistentClient(
            path=str(CHROMA_DIR),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
    return _client


def collection_name(kb_id: str) -> str:
    # Keep collection names stable and filesystem-safe
    return f"kb_{kb_id.strip().lower()}"


def get_or_create_collection(kb_id: str) -> Collection:
    client = get_client()
    name = collection_name(kb_id)
    return client.get_or_create_collection(
        name=name,
        metadata={"kb_id": kb_id, "description": f"KB collection for {kb_id}"},
    )


def delete_collection(kb_id: str):
    client = get_client()
    name = collection_name(kb_id)
    try:
        client.delete_collection(name)
    except Exception:
        pass


