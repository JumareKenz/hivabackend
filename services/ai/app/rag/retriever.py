"""
Branch FAQ retriever (ChromaDB + SentenceTransformers).

`app/services/rag_service.py` imports `retrieve()` from here.

Design goals:
- Persistent local vector store (stored under `app/rag/db/`)
- Branch-aware retrieval:
  - If `branch_id` is provided, retrieve branch-specific chunks first
  - Fall back to general chunks (no branch_id) for remaining slots
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
import hashlib

from chromadb import PersistentClient
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer

from app.core.config import settings


BASE_DIR = Path(__file__).resolve().parent
CHROMA_DIR = BASE_DIR / "db"
COLLECTION_NAME = "faq_collection"


_embedding_model: Optional[SentenceTransformer] = None
_chroma_client: Optional[PersistentClient] = None


def _get_embedding_model() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(getattr(settings, "EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"))
    return _embedding_model


def _get_chroma_client() -> PersistentClient:
    global _chroma_client
    if _chroma_client is None:
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        _chroma_client = PersistentClient(
            path=str(CHROMA_DIR),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
    return _chroma_client


def _get_collection():
    client = _get_chroma_client()
    # get_or_create_collection exists on Chroma's client
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"description": "Branch FAQs + policies (chunked)"},
    )


def _format_context(documents: list[str], metadatas: list[dict[str, Any]]) -> str:
    # Format documents without source markers - they're for internal use only
    # Source information is kept in metadata for internal tracking but not shown to users
    parts: list[str] = []
    for doc in documents:
        parts.append(doc.strip())
    return "\n\n---\n\n".join(parts).strip()


def retrieve(query: str, k: int = 5, branch_id: Optional[str] = None) -> str:
    """
    Retrieve up to k relevant chunks as a single context string.
    This is a synchronous function (called in a thread executor by the API layer).
    """
    query = (query or "").strip()
    if not query:
        return ""

    collection = _get_collection()
    embedder = _get_embedding_model()
    query_embedding = embedder.encode([query]).tolist()[0]

    documents: list[str] = []
    metadatas: list[dict[str, Any]] = []

    remaining = max(int(k), 1)

    # 1) Branch-specific search first (if branch_id is provided)
    if branch_id:
        try:
            res = collection.query(
                query_embeddings=[query_embedding],
                n_results=remaining,
                where={"branch_id": branch_id},
                include=["documents", "metadatas"],
            )
            docs = (res.get("documents") or [[]])[0]
            mds = (res.get("metadatas") or [[]])[0]
            documents.extend([d for d in docs if isinstance(d, str)])
            metadatas.extend([m for m in mds if isinstance(m, dict)])
            remaining = max(0, remaining - len(docs))
        except Exception:
            # If the collection doesn't have where filtering or the metadata isn't present,
            # we just skip branch-pref.
            remaining = max(int(k), 1)

    # 2) General fallback (no branch_id)
    if remaining > 0:
        try:
            res = collection.query(
                query_embeddings=[query_embedding],
                n_results=remaining,
                include=["documents", "metadatas"],
            )
            docs = (res.get("documents") or [[]])[0]
            mds = (res.get("metadatas") or [[]])[0]
            documents.extend([d for d in docs if isinstance(d, str)])
            metadatas.extend([m for m in mds if isinstance(m, dict)])
        except Exception:
            return ""

    # De-duplicate by content hash (helps when branch + general overlap)
    seen: set[str] = set()
    dedup_docs: list[str] = []
    dedup_mds: list[dict[str, Any]] = []
    for doc, md in zip(documents, metadatas):
        h = hashlib.md5(doc.encode("utf-8")).hexdigest()
        if h in seen:
            continue
        seen.add(h)
        dedup_docs.append(doc)
        dedup_mds.append(md)

    return _format_context(dedup_docs[:k], dedup_mds[:k])


