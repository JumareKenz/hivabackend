"""
Zamfara RAG Pipeline - Main Orchestration Module

This module provides the main entry point for the Zamfara FAQ Chatbot RAG system.
It orchestrates document ingestion, indexing, retrieval, and answer generation.

Usage:
    # Ingest documents
    python -m zamfara_rag.main ingest --clear
    
    # Query the system
    python -m zamfara_rag.main query "What is the policy on health services?"
    
    # Interactive mode
    python -m zamfara_rag.main interactive
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Import local modules
from zamfara_rag.config.settings import rag_settings
from zamfara_rag.preprocessing.loader import DocumentLoader
from zamfara_rag.preprocessing.cleaner import TextCleaner
from zamfara_rag.preprocessing.normalizer import TextNormalizer
from zamfara_rag.preprocessing.chunker import SemanticChunker, DocumentChunk
from zamfara_rag.preprocessing.metadata import MetadataExtractor
from zamfara_rag.embeddings.generator import EmbeddingGenerator
from zamfara_rag.vector_store.store import VectorStore
from zamfara_rag.retrieval.retriever import Retriever, RetrievalResponse
from zamfara_rag.generation.generator import AnswerGenerator, GeneratedAnswer
from zamfara_rag.evaluation.hallucination_guard import HallucinationGuard


@dataclass
class QueryResult:
    """Complete result from a RAG query."""
    
    query: str
    answer: str
    citations: List[str]
    sources: List[str]
    confidence: float
    is_grounded: bool
    verification_passed: bool
    retrieval_time_ms: float
    generation_time_ms: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "query": self.query,
            "answer": self.answer,
            "citations": self.citations,
            "sources": self.sources,
            "confidence": self.confidence,
            "is_grounded": self.is_grounded,
            "verification_passed": self.verification_passed,
            "retrieval_time_ms": self.retrieval_time_ms,
            "generation_time_ms": self.generation_time_ms,
        }
    
    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


class ZamfaraRAGPipeline:
    """
    Main RAG pipeline for Zamfara FAQ Chatbot.
    
    This class orchestrates the entire RAG workflow:
    1. Document ingestion and preprocessing
    2. Chunking and metadata extraction
    3. Embedding generation and vector indexing
    4. Query processing and retrieval
    5. Answer generation with citations
    6. Hallucination verification
    """
    
    def __init__(
        self,
        source_dir: Optional[Path] = None,
        vector_store_dir: Optional[Path] = None,
        llm_api_url: Optional[str] = None,
        llm_model: Optional[str] = None,
        llm_api_key: Optional[str] = None,
    ):
        """
        Initialize the RAG pipeline.
        
        Args:
            source_dir: Directory containing source documents
            vector_store_dir: Directory for vector store persistence
            llm_api_url: URL for LLM API
            llm_model: Model name for generation
            llm_api_key: API key for LLM service
        """
        # Use settings defaults if not provided
        self.source_dir = source_dir or rag_settings.source_docs_dir
        self.vector_store_dir = vector_store_dir or rag_settings.vector_store_dir
        self.llm_api_url = llm_api_url or rag_settings.llm_api_url
        self.llm_model = llm_model or rag_settings.llm_model
        self.llm_api_key = llm_api_key or rag_settings.llm_api_key
        
        # Initialize components
        self._init_components()
        
        logger.info(f"ZamfaraRAGPipeline initialized")
        logger.info(f"  Source directory: {self.source_dir}")
        logger.info(f"  Vector store: {self.vector_store_dir}")
        logger.info(f"  LLM: {self.llm_model}")
    
    def _init_components(self) -> None:
        """Initialize all pipeline components."""
        # Preprocessing components
        self.loader = DocumentLoader(
            source_dir=self.source_dir,
            supported_formats=rag_settings.supported_formats,
            max_file_size_mb=rag_settings.max_file_size_mb,
        )
        self.cleaner = TextCleaner()
        self.normalizer = TextNormalizer()
        self.chunker = SemanticChunker(
            chunk_size_chars=rag_settings.chunk_size_chars,
            overlap_percent=rag_settings.chunk_overlap_percent,
            min_chunk_size=rag_settings.min_chunk_size_chars,
        )
        self.metadata_extractor = MetadataExtractor()
        
        # Embedding and storage
        self.embedding_generator = EmbeddingGenerator(
            model_name=rag_settings.embedding_model,
        )
        self.vector_store = VectorStore(
            persist_dir=self.vector_store_dir,
            collection_name=rag_settings.collection_name,
        )
        
        # Retrieval
        self.retriever = Retriever(
            vector_store=self.vector_store,
            embedding_generator=self.embedding_generator,
            default_k=rag_settings.default_top_k,
            enable_reranking=rag_settings.enable_reranking,
            min_similarity=rag_settings.min_similarity_threshold,
        )
        
        # Generation
        self.generator = AnswerGenerator(
            llm_api_url=self.llm_api_url,
            llm_model=self.llm_model,
            llm_api_key=self.llm_api_key,
            temperature=rag_settings.temperature,
            max_tokens=rag_settings.max_tokens,
        )
        
        # Verification
        self.hallucination_guard = HallucinationGuard(
            confidence_threshold=rag_settings.verification_threshold,
            strict_mode=True,
        )
    
    def ingest(self, clear: bool = False) -> Dict[str, Any]:
        """
        Ingest all documents from the source directory.
        
        Args:
            clear: If True, clear existing vector store before ingesting
            
        Returns:
            Ingestion statistics
        """
        logger.info("Starting document ingestion...")
        
        if clear:
            logger.info("Clearing existing vector store...")
            self.vector_store.clear()
        
        stats = {
            "documents_loaded": 0,
            "chunks_created": 0,
            "chunks_indexed": 0,
            "errors": [],
            "start_time": datetime.now().isoformat(),
        }
        
        # Load and process documents
        all_chunks: List[DocumentChunk] = []
        
        for doc in self.loader.load_all():
            try:
                stats["documents_loaded"] += 1
                
                # Clean text
                cleaned_text, cleaning_stats = self.cleaner.clean(doc.text)
                
                # Normalize text
                normalized_text = self.normalizer.normalize(cleaned_text)
                
                # Extract document-level metadata
                doc_metadata = self.metadata_extractor.extract(
                    text=normalized_text,
                    file_path=str(doc.file_path),
                    file_name=doc.file_name,
                    last_modified=doc.last_modified,
                    extraction_method=doc.extraction_method,
                )
                
                # Chunk document
                chunks = list(self.chunker.chunk_document(
                    text=normalized_text,
                    document_title=doc_metadata.document_title,
                    document_type=doc_metadata.document_type,
                    file_path=str(doc.file_path),
                    file_name=doc.file_name,
                    department=doc_metadata.department,
                    last_updated=doc_metadata.last_updated,
                ))
                
                all_chunks.extend(chunks)
                stats["chunks_created"] += len(chunks)
                
                logger.info(
                    f"Processed: {doc.file_name} → {len(chunks)} chunks "
                    f"(type: {doc_metadata.document_type}, dept: {doc_metadata.department})"
                )
                
            except Exception as e:
                error_msg = f"Error processing {doc.file_name}: {str(e)}"
                logger.error(error_msg)
                stats["errors"].append(error_msg)
        
        if not all_chunks:
            logger.warning("No chunks to index!")
            return stats
        
        # Generate embeddings
        logger.info(f"Generating embeddings for {len(all_chunks)} chunks...")
        texts = [chunk.text for chunk in all_chunks]
        embeddings = self.embedding_generator.embed_documents(texts)
        
        # Index chunks
        logger.info("Indexing chunks in vector store...")
        ids = [chunk.chunk_id for chunk in all_chunks]
        metadatas = [chunk.to_dict() for chunk in all_chunks]
        
        indexed = self.vector_store.add_documents(
            ids=ids,
            documents=texts,
            embeddings=embeddings.tolist(),
            metadatas=metadatas,
        )
        
        stats["chunks_indexed"] = indexed
        stats["end_time"] = datetime.now().isoformat()
        
        logger.info(f"Ingestion complete: {stats['documents_loaded']} documents, {indexed} chunks indexed")
        
        return stats
    
    async def query(
        self,
        question: str,
        k: int = 5,
        document_type: Optional[str] = None,
        department: Optional[str] = None,
        verify: bool = True,
    ) -> QueryResult:
        """
        Process a query through the RAG pipeline.
        
        Args:
            question: User question
            k: Number of documents to retrieve
            document_type: Filter by document type
            department: Filter by department
            verify: Whether to run hallucination verification
            
        Returns:
            QueryResult with answer and metadata
        """
        logger.info(f"Processing query: '{question[:50]}...'")
        
        # Retrieve relevant documents
        retrieval_response = self.retriever.retrieve(
            query=question,
            k=k,
            document_type=document_type,
            department=department,
        )
        
        # Generate answer
        generated = await self.generator.generate(
            query=question,
            retrieval_response=retrieval_response,
        )
        
        # Verify answer (if enabled and not a fallback)
        verification_passed = True
        if verify and not generated.is_fallback:
            source_texts = [r.text for r in retrieval_response.results]
            verification = self.hallucination_guard.verify(
                answer=generated.answer,
                source_texts=source_texts,
                citations=generated.citations,
            )
            verification_passed = verification.passed
            
            # If verification fails, try regeneration or fallback
            if not verification_passed and rag_settings.max_regeneration_attempts > 0:
                if verification.needs_regeneration:
                    logger.info("Verification failed, attempting regeneration...")
                    generated = await self.generator.generate(
                        query=question,
                        retrieval_response=retrieval_response,
                    )
                    # Re-verify
                    verification = self.hallucination_guard.verify(
                        answer=generated.answer,
                        source_texts=source_texts,
                        citations=generated.citations,
                    )
                    verification_passed = verification.passed
                
                if verification.fallback_recommended:
                    logger.info("Verification recommends fallback response")
                    generated.answer = self.generator.FALLBACK_RESPONSE
                    generated.is_fallback = True
        
        return QueryResult(
            query=question,
            answer=generated.answer,
            citations=generated.citations,
            sources=generated.sources_used,
            confidence=generated.confidence,
            is_grounded=generated.grounded,
            verification_passed=verification_passed,
            retrieval_time_ms=retrieval_response.retrieval_time_ms,
            generation_time_ms=generated.generation_time_ms,
        )
    
    def query_sync(self, question: str, **kwargs) -> QueryResult:
        """Synchronous wrapper for query()."""
        return asyncio.run(self.query(question, **kwargs))
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pipeline statistics."""
        return {
            "source_directory": str(self.source_dir),
            "vector_store": self.vector_store.get_stats(),
            "embedding_cache": self.embedding_generator.get_cache_stats(),
        }


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Zamfara RAG Pipeline - FAQ Chatbot powered by document retrieval"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Ingest command
    ingest_parser = subparsers.add_parser(
        "ingest",
        help="Ingest documents from the Zamfara directory"
    )
    ingest_parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing vector store before ingesting"
    )
    ingest_parser.add_argument(
        "--source-dir",
        type=str,
        help="Source directory (defaults to Zamfara folder)"
    )
    
    # Query command
    query_parser = subparsers.add_parser(
        "query",
        help="Query the RAG system"
    )
    query_parser.add_argument(
        "question",
        type=str,
        help="Question to ask"
    )
    query_parser.add_argument(
        "-k", "--top-k",
        type=int,
        default=5,
        help="Number of documents to retrieve"
    )
    query_parser.add_argument(
        "--type",
        type=str,
        help="Filter by document type (policy, guideline, sop, etc.)"
    )
    query_parser.add_argument(
        "--department",
        type=str,
        help="Filter by department"
    )
    query_parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip hallucination verification"
    )
    
    # Interactive command
    interactive_parser = subparsers.add_parser(
        "interactive",
        help="Start interactive query mode"
    )
    
    # Stats command
    stats_parser = subparsers.add_parser(
        "stats",
        help="Show pipeline statistics"
    )
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Initialize pipeline
    source_dir = None
    if hasattr(args, "source_dir") and args.source_dir:
        source_dir = Path(args.source_dir)
    
    pipeline = ZamfaraRAGPipeline(source_dir=source_dir)
    
    if args.command == "ingest":
        result = pipeline.ingest(clear=args.clear)
        print(json.dumps(result, indent=2))
    
    elif args.command == "query":
        result = pipeline.query_sync(
            question=args.question,
            k=args.top_k,
            document_type=args.type,
            department=args.department,
            verify=not args.no_verify,
        )
        print("\n" + "="*60)
        print("QUESTION:", args.question)
        print("="*60)
        print("\nANSWER:")
        print(result.answer)
        print("\n" + "-"*60)
        print("SOURCES:", ", ".join(result.sources) if result.sources else "N/A")
        print("CONFIDENCE:", f"{result.confidence:.2f}")
        print("VERIFIED:", "Yes" if result.verification_passed else "No")
        print("="*60)
    
    elif args.command == "interactive":
        print("\nZamfara RAG Interactive Mode")
        print("Type 'quit' or 'exit' to stop")
        print("="*60)
        
        while True:
            try:
                question = input("\nQuestion: ").strip()
                
                if question.lower() in ("quit", "exit", "q"):
                    print("Goodbye!")
                    break
                
                if not question:
                    continue
                
                result = pipeline.query_sync(question)
                
                print("\nAnswer:", result.answer)
                if result.citations:
                    print("\nSources:", ", ".join(result.citations))
                print(f"\n[Confidence: {result.confidence:.2f}, Verified: {'Yes' if result.verification_passed else 'No'}]")
                
            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"\nError: {e}")
    
    elif args.command == "stats":
        stats = pipeline.get_stats()
        print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()




