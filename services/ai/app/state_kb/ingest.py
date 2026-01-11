"""
Ingest state/provider KB documents into isolated ChromaDB collections.

Usage:
  - Ingest everything:
      python -m app.state_kb.ingest
  - Ingest one KB:
      python -m app.state_kb.ingest adamawa
      python -m app.state_kb.ingest providers
  - Clear and re-ingest one KB:
      python -m app.state_kb.ingest adamawa --clear
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable, Optional
import hashlib

from sentence_transformers import SentenceTransformer

from app.core.config import settings
from app.rag.utils import extract_text_from_pdf, extract_text_from_docx, chunk_text
from app.state_kb.registry import get_kbs, require_kb
from app.state_kb.store import get_or_create_collection, delete_collection


def _iter_files(root: Path) -> Iterable[Path]:
    if not root.exists():
        return
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in {".pdf", ".docx", ".txt", ".md", ".jsonl"}:
            yield p


def _read_text_file(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore").strip()


def _load_jsonl(p: Path) -> list[dict[str, Any]]:
    """Load Q&A pairs from JSONL file."""
    items = []
    try:
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                    items.append(item)
                except json.JSONDecodeError:
                    continue
    except Exception:
        pass
    return items


def _extract_text(p: Path) -> str:
    suffix = p.suffix.lower()
    if suffix == ".pdf":
        return extract_text_from_pdf(str(p))
    if suffix == ".docx":
        return extract_text_from_docx(str(p))
    if suffix in {".txt", ".md"}:
        return _read_text_file(p)
    if suffix == ".jsonl":
        # JSONL files are handled separately
        return ""
    return ""


def _stable_id(*parts: str) -> str:
    return hashlib.md5("::".join(parts).encode("utf-8")).hexdigest()


def ingest_one(kb_id: str, clear: bool = False) -> dict[str, Any]:
    kb = require_kb(kb_id)
    if clear:
        delete_collection(kb.kb_id)
    collection = get_or_create_collection(kb.kb_id)

    embedder = SentenceTransformer(getattr(settings, "EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"))

    docs: list[str] = []
    metadatas: list[dict[str, Any]] = []
    ids: list[str] = []

    for src in kb.sources:
        for p in _iter_files(src):
            # Handle JSONL files specially (Q&A format)
            if p.suffix.lower() == ".jsonl":
                jsonl_items = _load_jsonl(p)
                for item in jsonl_items:
                    # Format Q&A as a single document chunk
                    question = item.get("question", "").strip()
                    answer = item.get("answer", "").strip()
                    if not question and not answer:
                        continue
                    
                    # Combine Q&A into a single text chunk
                    qa_text = f"Question: {question}\n\nAnswer: {answer}"
                    if item.get("section"):
                        qa_text = f"Section: {item.get('section')}\n\n{qa_text}"
                    
                    # Use the Q&A as-is (no chunking for JSONL items)
                    doc_id = _stable_id(kb.kb_id, str(p), item.get("intent", ""), question)
                    docs.append(qa_text)
                    metadatas.append(
                        {
                            "kb_id": kb.kb_id,
                            "source_path": str(p),
                            "doc_type": "qa_pair",
                            "intent": item.get("intent", ""),
                            "section": item.get("section", ""),
                            "question": question[:200],  # Store first 200 chars for reference
                        }
                    )
                    ids.append(doc_id)
                continue
            
            # Handle regular documents (PDF, DOCX, TXT, MD)
            text = _extract_text(p)
            if not text:
                continue
            chunks = chunk_text(
                text,
                chunk_size=getattr(settings, "RAG_CHUNK_SIZE", 900),
                overlap=getattr(settings, "RAG_CHUNK_OVERLAP", 120),
            )
            for i, chunk in enumerate(chunks):
                doc_id = _stable_id(kb.kb_id, str(p), str(i))
                docs.append(chunk)
                metadatas.append(
                    {
                        "kb_id": kb.kb_id,
                        "source_path": str(p),
                        "chunk_index": i,
                        "doc_type": "kb_doc",
                    }
                )
                ids.append(doc_id)

    if not docs:
        return {"kb_id": kb.kb_id, "status": "no_documents", "count": 0}

    embeddings = embedder.encode(docs, show_progress_bar=True).tolist()

    try:
        collection.upsert(documents=docs, embeddings=embeddings, metadatas=metadatas, ids=ids)
    except Exception:
        collection.add(documents=docs, embeddings=embeddings, metadatas=metadatas, ids=ids)

    return {"kb_id": kb.kb_id, "status": "ok", "count": len(docs), "collection": collection.name}


def main():
    parser = argparse.ArgumentParser(description="Ingest state/provider KB docs into ChromaDB.")
    parser.add_argument("kb_id", nargs="?", default=None, help="Optional kb_id (e.g., adamawa|providers)")
    parser.add_argument("--clear", action="store_true", help="Clear the KB collection before ingesting")
    args = parser.parse_args()

    results: list[dict[str, Any]] = []
    if args.kb_id:
        results.append(ingest_one(args.kb_id, clear=args.clear))
    else:
        for kb_id in get_kbs().keys():
            results.append(ingest_one(kb_id, clear=args.clear))

    print(json.dumps({"results": results}, indent=2))


if __name__ == "__main__":
    main()


