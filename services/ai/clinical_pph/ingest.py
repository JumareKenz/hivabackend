"""
Document ingestion for Clinical PPH knowledge base (ChromaDB).

This module handles ingestion of FAQ and policy documents into the vector store.
Supports multiple document formats: PDF, DOCX, TXT, MD, and JSONL.

Usage:
  - Ingest all documents:
      python -m clinical_pph.ingest
  - Clear and re-ingest:
      python -m clinical_pph.ingest --clear
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable
import hashlib
import logging

from sentence_transformers import SentenceTransformer

from app.core.config import settings
from app.rag.utils import extract_text_from_pdf, extract_text_from_docx, chunk_text
from .store import get_or_create_collection, delete_collection

logger = logging.getLogger(__name__)

# Base directory for Clinical PPH documents
BASE_DIR = Path(__file__).resolve().parent
DOCS_DIR = BASE_DIR / "docs"


def _iter_files(root: Path) -> Iterable[Path]:
    """
    Iterate over all supported document files in a directory tree.
    
    Args:
        root: Root directory to search
        
    Yields:
        Path objects for supported files
    """
    if not root.exists():
        logger.warning(f"Document directory does not exist: {root}")
        return
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in {".pdf", ".docx", ".txt", ".md", ".jsonl"}:
            yield p


def _read_text_file(p: Path) -> str:
    """Read text from a plain text file."""
    return p.read_text(encoding="utf-8", errors="ignore").strip()


def _load_jsonl(p: Path) -> list[dict[str, Any]]:
    """
    Load Q&A pairs from JSONL file.
    
    Expected format: One JSON object per line with 'question' and 'answer' fields.
    
    Args:
        p: Path to JSONL file
        
    Returns:
        List of Q&A dictionaries
    """
    items = []
    try:
        with open(p, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                    items.append(item)
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON on line {line_num} in {p}: {e}")
                    continue
    except Exception as e:
        logger.error(f"Error reading JSONL file {p}: {e}")
    return items


def _extract_text(p: Path) -> str:
    """
    Extract text content from a document file.
    
    Supports PDF, DOCX, TXT, and MD formats.
    Uses OCR fallback for PDFs that fail regular extraction.
    
    Args:
        p: Path to document file
        
    Returns:
        Extracted text content
    """
    suffix = p.suffix.lower()
    if suffix == ".pdf":
        # Try regular extraction first, then OCR if needed
        try:
            text = extract_text_from_pdf(str(p), use_ocr=False)
            if len(text) < 100:  # If minimal text, try OCR
                logger.info(f"Minimal text from {p.name}, trying OCR...")
                text = extract_text_from_pdf(str(p), use_ocr=True)
            return text
        except Exception as e:
            logger.warning(f"Regular PDF extraction failed for {p.name}: {e}, trying OCR...")
            try:
                return extract_text_from_pdf(str(p), use_ocr=True)
            except Exception as ocr_e:
                logger.error(f"OCR also failed for {p.name}: {ocr_e}")
                return ""
    if suffix == ".docx":
        return extract_text_from_docx(str(p))
    if suffix in {".txt", ".md"}:
        return _read_text_file(p)
    if suffix == ".jsonl":
        # JSONL files are handled separately
        return ""
    return ""


def _stable_id(*parts: str) -> str:
    """
    Generate a stable, deterministic ID from parts.
    
    Args:
        *parts: Parts to combine into an ID
        
    Returns:
        MD5 hash of combined parts
    """
    return hashlib.md5("::".join(parts).encode("utf-8")).hexdigest()


def ingest(clear: bool = False) -> dict[str, Any]:
    """
    Ingest all documents from the Clinical PPH docs directory into ChromaDB.
    
    This function:
    1. Scans the docs directory for supported document formats
    2. Extracts text from documents
    3. Chunks text into smaller pieces for embedding
    4. Generates embeddings using sentence transformers
    5. Stores documents, embeddings, and metadata in ChromaDB
    
    Args:
        clear: If True, delete existing collection before ingesting
        
    Returns:
        Dictionary with ingestion status and statistics
    """
    if clear:
        logger.info("Clearing existing Clinical PPH collection...")
        delete_collection()
    
    collection = get_or_create_collection()
    embedder = SentenceTransformer(
        getattr(settings, "EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
    )

    docs: list[str] = []
    metadatas: list[dict[str, Any]] = []
    ids: list[str] = []

    # Process all files in the docs directory
    files_processed = 0
    for p in _iter_files(DOCS_DIR):
        files_processed += 1
        logger.info(f"Processing file {files_processed}: {p.name}")
        
        # Handle JSONL files specially (Q&A format)
        if p.suffix.lower() == ".jsonl":
            jsonl_items = _load_jsonl(p)
            logger.info(f"Found {len(jsonl_items)} Q&A pairs in {p.name}")
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
                doc_id = _stable_id("clinical_pph", str(p), item.get("intent", ""), question)
                docs.append(qa_text)
                metadatas.append(
                    {
                        "kb_id": "clinical_pph",
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
            logger.warning(f"No text extracted from {p.name}")
            continue
        
        logger.info(f"Extracted {len(text)} characters from {p.name}, chunking...")
        chunks = chunk_text(
            text,
            chunk_size=getattr(settings, "RAG_CHUNK_SIZE", 900),
            overlap=getattr(settings, "RAG_CHUNK_OVERLAP", 120),
        )
        
        chunk_count = 0
        for i, chunk in enumerate(chunks):
            chunk_count += 1
            doc_id = _stable_id("clinical_pph", str(p), str(i))
            docs.append(chunk)
            metadatas.append(
                {
                    "kb_id": "clinical_pph",
                    "source_path": str(p),
                    "chunk_index": i,
                    "doc_type": "document",
                    "file_name": p.name,
                }
            )
            ids.append(doc_id)
        
        logger.info(f"Created {chunk_count} chunks from {p.name}")

    if not docs:
        logger.warning("No documents found to ingest")
        return {
            "kb_id": "clinical_pph",
            "status": "no_documents",
            "count": 0,
            "files_processed": files_processed,
        }

    logger.info(f"Generating embeddings for {len(docs)} document chunks...")
    embeddings = embedder.encode(docs, show_progress_bar=True).tolist()

    logger.info(f"Storing {len(docs)} documents in ChromaDB...")
    try:
        collection.upsert(documents=docs, embeddings=embeddings, metadatas=metadatas, ids=ids)
        logger.info("Successfully upserted documents")
    except Exception as e:
        logger.warning(f"Upsert failed, trying add: {e}")
        collection.add(documents=docs, embeddings=embeddings, metadatas=metadatas, ids=ids)
        logger.info("Successfully added documents")

    return {
        "kb_id": "clinical_pph",
        "status": "ok",
        "count": len(docs),
        "files_processed": files_processed,
        "collection": collection.name,
    }


def ingest_all() -> dict[str, Any]:
    """
    Convenience function to ingest all documents.
    
    Returns:
        Dictionary with ingestion status and statistics
    """
    return ingest(clear=False)


def main():
    """Command-line interface for document ingestion."""
    parser = argparse.ArgumentParser(
        description="Ingest Clinical PPH documents into ChromaDB."
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear the existing collection before ingesting"
    )
    args = parser.parse_args()

    result = ingest(clear=args.clear)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

