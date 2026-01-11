"""
FAQ ingestion for branch knowledge base (ChromaDB).

Usage:
  - Ingest everything:
      python -m app.rag.ingest
  - Ingest a specific branch:
      python -m app.rag.ingest kano
  - Clear and re-ingest:
      python -m app.rag.ingest --clear

Sources:
  - General docs: `app/rag/faqs/*` (excluding `branches/`)
  - Branch docs:  `app/rag/faqs/branches/{branch_id}/**/*`
  - Curated JSONL: `app/rag/faqs/faqs.jsonl` and `providers.jsonl` (optional)
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Iterable
import hashlib

from chromadb import PersistentClient
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer

from app.core.config import settings
from app.rag.utils import extract_text_from_pdf, extract_text_from_docx, chunk_text


BASE_DIR = Path(__file__).resolve().parent
FAQS_DIR = BASE_DIR / "faqs"
BRANCHES_DIR = FAQS_DIR / "branches"
CHROMA_DIR = BASE_DIR / "db"
COLLECTION_NAME = "faq_collection"


def _iter_files(root: Path) -> Iterable[Path]:
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in {".pdf", ".docx", ".txt", ".md"}:
            yield p


def _read_text_file(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore").strip()


def _extract_text(p: Path) -> str:
    suffix = p.suffix.lower()
    if suffix == ".pdf":
        return extract_text_from_pdf(str(p))
    if suffix == ".docx":
        return extract_text_from_docx(str(p))
    if suffix in {".txt", ".md"}:
        return _read_text_file(p)
    return ""


def _stable_id(*parts: str) -> str:
    h = hashlib.md5("::".join(parts).encode("utf-8")).hexdigest()
    return h


def _load_jsonl_qas(path: Path) -> list[dict[str, Any]]:
    """
    Supports files that contain occasional header lines like 'ADAMAWA:'.
    """
    items: list[dict[str, Any]] = []
    if not path.exists():
        return items
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.endswith(":") and line[:-1].isalpha():
            # header marker, ignore (state name)
            continue
        if not line.startswith("{"):
            continue
        try:
            items.append(json.loads(line))
        except Exception:
            continue
    return items


def ingest(branch_id: Optional[str] = None, clear: bool = False) -> dict[str, Any]:
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = PersistentClient(
        path=str(CHROMA_DIR),
        settings=ChromaSettings(anonymized_telemetry=False),
    )

    if clear:
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"description": "Branch FAQs + policies (chunked)"},
    )

    embedder = SentenceTransformer(getattr(settings, "EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"))

    docs: list[str] = []
    metadatas: list[dict[str, Any]] = []
    ids: list[str] = []

    # 1) General docs (root, excluding branches/)
    for p in _iter_files(FAQS_DIR):
        if BRANCHES_DIR in p.parents:
            continue
        text = _extract_text(p)
        if not text:
            continue
        for i, chunk in enumerate(
            chunk_text(
                text,
                chunk_size=getattr(settings, "RAG_CHUNK_SIZE", 900),
                overlap=getattr(settings, "RAG_CHUNK_OVERLAP", 120),
            )
        ):
            doc_id = _stable_id(str(p), "general", str(i))
            docs.append(chunk)
            metadatas.append({"source_path": str(p), "doc_type": "general", "chunk_index": i})
            ids.append(doc_id)

    # 2) Branch docs
    if BRANCHES_DIR.exists():
        branch_dirs = [BRANCHES_DIR / branch_id] if branch_id else [p for p in BRANCHES_DIR.iterdir() if p.is_dir()]
        for bdir in branch_dirs:
            bid = bdir.name
            for p in _iter_files(bdir):
                text = _extract_text(p)
                if not text:
                    continue
                for i, chunk in enumerate(
                    chunk_text(
                        text,
                        chunk_size=getattr(settings, "RAG_CHUNK_SIZE", 900),
                        overlap=getattr(settings, "RAG_CHUNK_OVERLAP", 120),
                    )
                ):
                    doc_id = _stable_id(str(p), bid, str(i))
                    docs.append(chunk)
                    metadatas.append(
                        {
                            "source_path": str(p),
                            "doc_type": "branch",
                            "branch_id": bid,
                            "chunk_index": i,
                        }
                    )
                    ids.append(doc_id)

    # 3) Curated FAQ jsonl (optional)
    # `faqs.jsonl` contains state-prefixed Q/As; we store them as branch-tagged chunks.
    curated = _load_jsonl_qas(FAQS_DIR / "faqs.jsonl")
    for idx, qa in enumerate(curated):
        q = (qa.get("question") or "").strip()
        a = (qa.get("answer") or "").strip()
        if not q or not a:
            continue
        doc = f"Q: {q}\nA: {a}"
        # Attempt to infer branch_id from `source_document` conventions
        source_doc = (qa.get("source_document") or "").lower()
        inferred_branch = None
        for bid in ["adamawa", "fct", "kano", "zamfara", "kogi", "osun", "rivers", "sokoto", "kaduna"]:
            if bid in source_doc:
                inferred_branch = bid
                break
        # If ingesting a single branch, only include matching items
        if branch_id and inferred_branch and inferred_branch != branch_id:
            continue
        doc_id = _stable_id("faqs.jsonl", inferred_branch or "general", str(idx))
        docs.append(doc)
        metadatas.append(
            {
                "doc_type": "curated_qa",
                "branch_id": inferred_branch,
                "section": qa.get("section"),
                "source_document": qa.get("source_document"),
            }
        )
        ids.append(doc_id)

    if not docs:
        return {"status": "no_documents", "count": 0}

    embeddings = embedder.encode(docs, show_progress_bar=True).tolist()

    # Prefer upsert (Chroma >= 0.5), fallback to add
    try:
        collection.upsert(documents=docs, embeddings=embeddings, metadatas=metadatas, ids=ids)
    except Exception:
        collection.add(documents=docs, embeddings=embeddings, metadatas=metadatas, ids=ids)

    return {"status": "ok", "count": len(docs), "collection": COLLECTION_NAME, "db_path": str(CHROMA_DIR)}


def main():
    parser = argparse.ArgumentParser(description="Ingest branch FAQs into ChromaDB.")
    parser.add_argument("branch_id", nargs="?", default=None, help="Optional branch_id (e.g., kano)")
    parser.add_argument("--clear", action="store_true", help="Clear the existing collection before ingesting")
    args = parser.parse_args()

    result = ingest(branch_id=args.branch_id, clear=args.clear)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()


