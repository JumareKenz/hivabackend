"""
Knowledge Ingestion Pipeline for Provider RAG.

Features:
- Schema validation on all entries
- Normalized metadata extraction
- Intelligent chunking (preserves Q&A pairs)
- BM25 token preparation
- Embedding generation

Usage:
    from app.providers_rag.ingestion import ProviderIngestionPipeline
    
    pipeline = ProviderIngestionPipeline()
    result = await pipeline.ingest()
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Generator, Optional

from chromadb import PersistentClient
from chromadb.config import Settings as ChromaSettings
from pydantic import ValidationError
from sentence_transformers import SentenceTransformer

from app.providers_rag.config import provider_rag_config
from app.providers_rag.schemas import (
    DocumentChunk,
    DocumentSource,
    IngestionResult,
    KnowledgeEntry,
)

logger = logging.getLogger(__name__)


class ProviderIngestionPipeline:
    """
    Production-grade ingestion pipeline for provider knowledge.
    
    Responsibilities:
    1. Load and validate knowledge entries from JSONL
    2. Generate stable document IDs
    3. Create embeddings with SentenceTransformers
    4. Prepare BM25 tokens for sparse retrieval
    5. Store in ChromaDB with rich metadata
    """
    
    def __init__(self, config: Optional[Any] = None):
        self.config = config or provider_rag_config
        self._embedder: Optional[SentenceTransformer] = None
        self._chroma_client: Optional[PersistentClient] = None
        
    def _get_embedder(self) -> SentenceTransformer:
        """Lazy load the embedding model."""
        if self._embedder is None:
            logger.info(f"Loading embedding model: {self.config.embedding_model}")
            self._embedder = SentenceTransformer(self.config.embedding_model)
            logger.info("Embedding model loaded successfully")
        return self._embedder
    
    def _get_chroma_client(self) -> PersistentClient:
        """Get or create ChromaDB client."""
        if self._chroma_client is None:
            db_path = self.config.vector_store_path
            db_path.mkdir(parents=True, exist_ok=True)
            self._chroma_client = PersistentClient(
                path=str(db_path),
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            logger.info(f"ChromaDB client initialized at: {db_path}")
        return self._chroma_client
    
    def _generate_stable_id(self, *parts: str) -> str:
        """Generate a stable, reproducible document ID."""
        key = "::".join(str(p) for p in parts)
        return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    
    def _tokenize_for_bm25(self, text: str) -> list[str]:
        """
        Tokenize text for BM25 sparse retrieval.
        
        Simple but effective tokenization:
        - Lowercase
        - Remove punctuation
        - Split on whitespace
        - Remove stopwords
        """
        # Common English stopwords
        stopwords = {
            "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will", "would",
            "could", "should", "may", "might", "can", "this", "that", "these",
            "those", "i", "you", "he", "she", "it", "we", "they", "what", "which",
            "who", "when", "where", "why", "how", "all", "each", "every", "both",
            "few", "more", "most", "other", "some", "such", "no", "not", "only",
            "same", "so", "than", "too", "very", "just", "also", "now", "if"
        }
        
        # Clean and tokenize
        text = text.lower()
        text = re.sub(r"[^\w\s]", " ", text)  # Remove punctuation
        tokens = text.split()
        
        # Filter stopwords and short tokens
        tokens = [t for t in tokens if t not in stopwords and len(t) > 2]
        
        return tokens
    
    def _load_and_validate_entries(self) -> Generator[KnowledgeEntry, None, None]:
        """
        Load and validate entries from JSONL files.
        
        Yields validated KnowledgeEntry objects.
        Logs validation errors but continues processing.
        """
        kb_path = self.config.knowledge_base_path
        jsonl_files = list(kb_path.glob("*.jsonl"))
        
        if not jsonl_files:
            logger.warning(f"No JSONL files found in: {kb_path}")
            return
        
        for jsonl_file in jsonl_files:
            logger.info(f"Processing: {jsonl_file}")
            line_num = 0
            
            with open(jsonl_file, "r", encoding="utf-8") as f:
                for line in f:
                    line_num += 1
                    line = line.strip()
                    
                    # Skip empty lines and comments
                    if not line or not line.startswith("{"):
                        continue
                    
                    try:
                        data = json.loads(line)
                        entry = KnowledgeEntry(**data)
                        yield entry
                    except json.JSONDecodeError as e:
                        logger.warning(
                            f"JSON decode error in {jsonl_file}:{line_num}: {e}"
                        )
                    except ValidationError as e:
                        logger.warning(
                            f"Validation error in {jsonl_file}:{line_num}: {e}"
                        )
    
    def _create_chunk_from_entry(
        self,
        entry: KnowledgeEntry,
        chunk_index: int = 0
    ) -> DocumentChunk:
        """
        Create a DocumentChunk from a validated KnowledgeEntry.
        
        For Q&A pairs, we keep them as a single unit to preserve
        the semantic relationship between question and answer.
        """
        # Create combined content for embedding
        # Format optimized for retrieval: question + answer
        content = f"Question: {entry.question}\n\nAnswer: {entry.answer}"
        
        # Add section context if available
        if entry.section:
            content = f"Section: {entry.section.replace('_', ' ').title()}\n\n{content}"
        
        # Generate stable ID
        doc_id = self._generate_stable_id(
            entry.source_document,
            entry.section,
            entry.intent,
            entry.question
        )
        
        # Create source metadata
        source = DocumentSource(
            document_name=entry.source_document,
            section=entry.section.replace("_", " ").title(),
            chunk_index=chunk_index,
        )
        
        # Tokenize for BM25
        bm25_tokens = self._tokenize_for_bm25(content)
        
        return DocumentChunk(
            id=doc_id,
            content=content,
            source=source,
            intent=entry.intent,
            section=entry.section,
            original_question=entry.question,
            original_answer=entry.answer,
            bm25_tokens=bm25_tokens,
        )
    
    def ingest(self, clear: bool = False) -> IngestionResult:
        """
        Ingest all provider knowledge into the vector store.
        
        Args:
            clear: If True, clear the existing collection first.
            
        Returns:
            IngestionResult with status and statistics.
        """
        start_time = time.time()
        
        # Initialize result tracking
        total_entries = 0
        successful_entries = 0
        failed_entries = 0
        validation_errors: list[str] = []
        sections_seen: set[str] = set()
        intents_seen: set[str] = set()
        
        # Get ChromaDB client and collection
        client = self._get_chroma_client()
        
        if clear:
            try:
                client.delete_collection(self.config.collection_name)
                logger.info(f"Cleared existing collection: {self.config.collection_name}")
            except Exception:
                pass
        
        collection = client.get_or_create_collection(
            name=self.config.collection_name,
            metadata={
                "description": "Provider Knowledge Base - Production Grade",
                "version": "2.0",
                "hnsw:space": "cosine",  # Use cosine similarity
            },
        )
        
        # Prepare batches for ingestion
        chunks: list[DocumentChunk] = []
        
        # Load and validate all entries
        logger.info("Loading and validating knowledge entries...")
        for entry in self._load_and_validate_entries():
            total_entries += 1
            
            try:
                chunk = self._create_chunk_from_entry(entry, chunk_index=len(chunks))
                chunks.append(chunk)
                
                # Track metadata
                if entry.section:
                    sections_seen.add(entry.section)
                if entry.intent:
                    intents_seen.add(entry.intent)
                    
                successful_entries += 1
                
            except Exception as e:
                failed_entries += 1
                error_msg = f"Failed to process entry: {entry.question[:50]}... - {e}"
                validation_errors.append(error_msg)
                logger.error(error_msg)
        
        if not chunks:
            logger.error("No valid chunks to ingest!")
            return IngestionResult(
                status="error",
                total_entries=total_entries,
                successful_entries=0,
                failed_entries=failed_entries,
                validation_errors=validation_errors,
            )
        
        # Generate embeddings in batches
        logger.info(f"Generating embeddings for {len(chunks)} chunks...")
        embedder = self._get_embedder()
        
        contents = [c.content for c in chunks]
        embeddings = embedder.encode(
            contents,
            show_progress_bar=True,
            batch_size=32,
            normalize_embeddings=True,  # Important for cosine similarity
        ).tolist()
        
        # Prepare data for ChromaDB
        ids = [c.id for c in chunks]
        documents = [c.content for c in chunks]
        metadatas = [
            {
                "source_document": c.source.document_name,
                "section": c.section,
                "intent": c.intent,
                "original_question": c.original_question or "",
                "original_answer": (c.original_answer or "")[:500],  # Truncate long answers
                "bm25_tokens": " ".join(c.bm25_tokens or []),  # Store as space-separated string
            }
            for c in chunks
        ]
        
        # Upsert to ChromaDB
        logger.info("Upserting to ChromaDB...")
        try:
            collection.upsert(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas,
            )
            logger.info(f"Successfully ingested {len(chunks)} chunks")
        except Exception as e:
            logger.error(f"Failed to upsert to ChromaDB: {e}")
            return IngestionResult(
                status="error",
                total_entries=total_entries,
                successful_entries=0,
                failed_entries=total_entries,
                validation_errors=[str(e)],
            )
        
        elapsed = time.time() - start_time
        
        return IngestionResult(
            status="ok",
            total_entries=total_entries,
            successful_entries=successful_entries,
            failed_entries=failed_entries,
            validation_errors=validation_errors,
            sections_indexed=sorted(sections_seen),
            intents_indexed=sorted(intents_seen),
            collection_name=self.config.collection_name,
            ingestion_time_seconds=elapsed,
        )


def main():
    """CLI entry point for ingestion."""
    import argparse
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    parser = argparse.ArgumentParser(description="Ingest provider knowledge base")
    parser.add_argument("--clear", action="store_true", help="Clear existing collection")
    args = parser.parse_args()
    
    pipeline = ProviderIngestionPipeline()
    result = pipeline.ingest(clear=args.clear)
    
    print(json.dumps(result.model_dump(), indent=2, default=str))


if __name__ == "__main__":
    main()
