"""
Hybrid Retrieval Engine for Provider RAG.

Combines dense (semantic) and sparse (BM25) retrieval for optimal results.

Features:
- Dense retrieval using SentenceTransformer embeddings
- Sparse retrieval using BM25 keyword matching
- Reciprocal Rank Fusion (RRF) for combining results
- Confidence scoring and thresholding
- Automatic fallback strategies

Usage:
    from app.providers_rag.retriever import HybridRetriever
    
    retriever = HybridRetriever()
    result = await retriever.retrieve("How do I submit a claim?")
"""

from __future__ import annotations

import logging
import math
import re
import time
from collections import defaultdict
from typing import Any, Optional

from chromadb import PersistentClient
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer

from app.providers_rag.config import provider_rag_config
from app.providers_rag.schemas import (
    ConfidenceLevel,
    DocumentChunk,
    DocumentSource,
    RetrievalResult,
)

logger = logging.getLogger(__name__)


class BM25Index:
    """
    Simple but effective BM25 implementation for sparse retrieval.
    
    Uses the BM25 Okapi variant with standard parameters:
    - k1 = 1.5 (term frequency saturation)
    - b = 0.75 (document length normalization)
    """
    
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        
        # Index storage
        self.doc_ids: list[str] = []
        self.doc_tokens: list[list[str]] = []
        self.doc_lengths: list[int] = []
        self.avg_doc_length: float = 0.0
        
        # Inverted index: term -> list of (doc_idx, term_freq)
        self.inverted_index: dict[str, list[tuple[int, int]]] = defaultdict(list)
        
        # Document frequencies
        self.doc_freqs: dict[str, int] = defaultdict(int)
        
        self.n_docs: int = 0
        self.is_built: bool = False
    
    def _tokenize(self, text: str) -> list[str]:
        """Simple tokenization for BM25."""
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
        
        text = text.lower()
        text = re.sub(r"[^\w\s]", " ", text)
        tokens = text.split()
        tokens = [t for t in tokens if t not in stopwords and len(t) > 2]
        
        return tokens
    
    def build_index(
        self,
        doc_ids: list[str],
        documents: list[str],
        precomputed_tokens: Optional[list[list[str]]] = None
    ):
        """
        Build the BM25 index from documents.
        
        Args:
            doc_ids: List of document IDs
            documents: List of document texts
            precomputed_tokens: Optional pre-tokenized documents
        """
        self.doc_ids = doc_ids
        self.n_docs = len(documents)
        
        # Tokenize documents
        if precomputed_tokens:
            self.doc_tokens = precomputed_tokens
        else:
            self.doc_tokens = [self._tokenize(doc) for doc in documents]
        
        self.doc_lengths = [len(tokens) for tokens in self.doc_tokens]
        self.avg_doc_length = sum(self.doc_lengths) / self.n_docs if self.n_docs > 0 else 0
        
        # Build inverted index
        self.inverted_index.clear()
        self.doc_freqs.clear()
        
        for doc_idx, tokens in enumerate(self.doc_tokens):
            # Count term frequencies in this document
            term_freqs: dict[str, int] = defaultdict(int)
            for token in tokens:
                term_freqs[token] += 1
            
            # Update inverted index and document frequencies
            for term, freq in term_freqs.items():
                self.inverted_index[term].append((doc_idx, freq))
                self.doc_freqs[term] += 1
        
        self.is_built = True
        logger.info(f"BM25 index built with {self.n_docs} documents, {len(self.inverted_index)} unique terms")
    
    def search(self, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        """
        Search the index and return top-k documents with BM25 scores.
        
        Args:
            query: Search query
            top_k: Number of results to return
            
        Returns:
            List of (doc_id, score) tuples, sorted by score descending
        """
        if not self.is_built:
            logger.warning("BM25 index not built, returning empty results")
            return []
        
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []
        
        # Calculate BM25 scores for all documents
        scores: dict[int, float] = defaultdict(float)
        
        for term in query_tokens:
            if term not in self.inverted_index:
                continue
            
            # IDF calculation
            df = self.doc_freqs[term]
            idf = math.log((self.n_docs - df + 0.5) / (df + 0.5) + 1)
            
            # Score documents containing this term
            for doc_idx, tf in self.inverted_index[term]:
                doc_len = self.doc_lengths[doc_idx]
                
                # BM25 formula
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / self.avg_doc_length)
                score = idf * (numerator / denominator)
                
                scores[doc_idx] += score
        
        # Sort by score and return top-k
        sorted_results = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        
        return [(self.doc_ids[doc_idx], score) for doc_idx, score in sorted_results]


class HybridRetriever:
    """
    Hybrid retriever combining dense and sparse retrieval.
    
    Uses Reciprocal Rank Fusion (RRF) to combine results from:
    - Dense: ChromaDB vector search with SentenceTransformer embeddings
    - Sparse: BM25 keyword search
    
    Provides confidence scoring and automatic thresholding.
    """
    
    def __init__(self, config: Optional[Any] = None):
        self.config = config or provider_rag_config
        
        self._embedder: Optional[SentenceTransformer] = None
        self._chroma_client: Optional[PersistentClient] = None
        self._collection: Optional[Any] = None
        self._bm25_index: Optional[BM25Index] = None
        
        self._is_initialized: bool = False
    
    def _get_embedder(self) -> SentenceTransformer:
        """Lazy load the embedding model."""
        if self._embedder is None:
            logger.info(f"Loading embedding model: {self.config.embedding_model}")
            self._embedder = SentenceTransformer(self.config.embedding_model)
            logger.info("Embedding model loaded successfully")
        return self._embedder
    
    def _get_collection(self):
        """Get the ChromaDB collection."""
        if self._collection is None:
            db_path = self.config.vector_store_path
            db_path.mkdir(parents=True, exist_ok=True)
            
            self._chroma_client = PersistentClient(
                path=str(db_path),
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            
            self._collection = self._chroma_client.get_or_create_collection(
                name=self.config.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info(f"Connected to collection: {self.config.collection_name}")
        
        return self._collection
    
    def initialize(self):
        """
        Initialize the retriever by building the BM25 index.
        
        Should be called once at startup.
        """
        if self._is_initialized:
            return
        
        logger.info("Initializing hybrid retriever...")
        
        # Get all documents from ChromaDB for BM25 index
        collection = self._get_collection()
        
        # Check if collection has documents
        count = collection.count()
        if count == 0:
            logger.warning("Collection is empty - run ingestion first")
            self._is_initialized = True
            return
        
        # Fetch all documents for BM25 index
        logger.info(f"Building BM25 index from {count} documents...")
        
        # ChromaDB doesn't support getting all docs easily, so we query with a large limit
        result = collection.get(
            include=["documents", "metadatas"],
            limit=count,
        )
        
        doc_ids = result.get("ids", [])
        documents = result.get("documents", [])
        metadatas = result.get("metadatas", [])
        
        # Extract precomputed BM25 tokens from metadata if available
        precomputed_tokens = None
        if metadatas and metadatas[0].get("bm25_tokens"):
            precomputed_tokens = [
                m.get("bm25_tokens", "").split() for m in metadatas
            ]
        
        # Build BM25 index
        self._bm25_index = BM25Index()
        self._bm25_index.build_index(doc_ids, documents, precomputed_tokens)
        
        self._is_initialized = True
        logger.info("Hybrid retriever initialized successfully")
    
    def _convert_distance_to_similarity(self, distance: float) -> float:
        """
        Convert ChromaDB distance to similarity score (0-1).
        
        ChromaDB uses L2 distance by default, but we configured cosine.
        For cosine distance: similarity = 1 - distance/2
        """
        # Cosine distance is in [0, 2], convert to similarity in [0, 1]
        return max(0.0, min(1.0, 1 - distance / 2))
    
    def _normalize_bm25_scores(self, scores: list[float]) -> list[float]:
        """Normalize BM25 scores to [0, 1] range."""
        if not scores:
            return []
        
        max_score = max(scores)
        if max_score == 0:
            return [0.0] * len(scores)
        
        return [s / max_score for s in scores]
    
    def _reciprocal_rank_fusion(
        self,
        dense_results: list[tuple[str, float]],
        sparse_results: list[tuple[str, float]],
        k: int = 60,  # RRF constant
    ) -> list[tuple[str, float]]:
        """
        Combine dense and sparse results using Reciprocal Rank Fusion.
        
        RRF score = sum over rankings of 1 / (k + rank)
        
        This method is robust to score scale differences between retrieval methods.
        """
        # Create rank maps
        rrf_scores: dict[str, float] = defaultdict(float)
        
        # Weight configuration
        dense_weight = self.config.dense_weight
        sparse_weight = self.config.bm25_weight
        
        # Process dense results
        for rank, (doc_id, _score) in enumerate(dense_results, 1):
            rrf_scores[doc_id] += dense_weight * (1 / (k + rank))
        
        # Process sparse results
        for rank, (doc_id, _score) in enumerate(sparse_results, 1):
            rrf_scores[doc_id] += sparse_weight * (1 / (k + rank))
        
        # Sort by combined RRF score
        sorted_results = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        
        return sorted_results
    
    def _determine_confidence(self, scores: list[float]) -> ConfidenceLevel:
        """Determine confidence level based on retrieval scores."""
        if not scores:
            return ConfidenceLevel.NONE
        
        top_score = max(scores)
        avg_score = sum(scores) / len(scores)
        
        # Use the top score primarily, but also consider average
        if top_score >= self.config.high_confidence_threshold:
            return ConfidenceLevel.HIGH
        elif top_score >= self.config.medium_confidence_threshold:
            return ConfidenceLevel.MEDIUM
        elif top_score >= self.config.min_similarity_threshold:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.NONE
    
    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
    ) -> RetrievalResult:
        """
        Retrieve relevant documents using hybrid search.
        
        Args:
            query: User query
            top_k: Number of results to return (default from config)
            
        Returns:
            RetrievalResult with chunks, scores, and confidence
        """
        start_time = time.time()
        
        if not query or not query.strip():
            return RetrievalResult(
                query="",
                confidence=ConfidenceLevel.NONE,
                retrieval_time_ms=0,
            )
        
        query = query.strip()
        top_k = top_k or self.config.retrieval_top_k
        
        # Ensure initialized
        if not self._is_initialized:
            self.initialize()
        
        collection = self._get_collection()
        
        # Check if collection has documents
        if collection.count() == 0:
            logger.warning("Collection is empty")
            return RetrievalResult(
                query=query,
                confidence=ConfidenceLevel.NONE,
                retrieval_time_ms=(time.time() - start_time) * 1000,
            )
        
        # === DENSE RETRIEVAL ===
        embedder = self._get_embedder()
        query_embedding = embedder.encode(
            [query],
            normalize_embeddings=True,
            show_progress_bar=False,
        ).tolist()[0]
        
        dense_results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k * 2,  # Get more for fusion
            include=["documents", "metadatas", "distances"],
        )
        
        # Process dense results
        dense_ids = dense_results.get("ids", [[]])[0]
        dense_docs = dense_results.get("documents", [[]])[0]
        dense_metas = dense_results.get("metadatas", [[]])[0]
        dense_distances = dense_results.get("distances", [[]])[0]
        
        # Convert distances to similarities
        dense_similarities = [
            self._convert_distance_to_similarity(d) for d in dense_distances
        ]
        
        dense_ranked = list(zip(dense_ids, dense_similarities))
        
        # === SPARSE RETRIEVAL (BM25) ===
        sparse_ranked = []
        if self._bm25_index and self._bm25_index.is_built:
            sparse_results = self._bm25_index.search(query, top_k=top_k * 2)
            sparse_ranked = sparse_results
        
        # === HYBRID FUSION ===
        if sparse_ranked:
            fused_results = self._reciprocal_rank_fusion(dense_ranked, sparse_ranked)
        else:
            # Fall back to dense only
            fused_results = dense_ranked
        
        # Get top-k fused results
        final_doc_ids = [doc_id for doc_id, _score in fused_results[:top_k]]
        
        # Collect final chunks with original similarity scores
        chunks: list[DocumentChunk] = []
        scores: list[float] = []
        
        # Create lookup maps
        dense_map = {id_: (doc, meta, sim) for id_, doc, meta, sim in zip(
            dense_ids, dense_docs, dense_metas, dense_similarities
        )}
        
        for doc_id in final_doc_ids:
            if doc_id in dense_map:
                doc, meta, sim = dense_map[doc_id]
                
                # Filter out low-confidence results
                if sim < self.config.min_similarity_threshold:
                    continue
                
                # Create chunk
                chunk = DocumentChunk(
                    id=doc_id,
                    content=doc,
                    source=DocumentSource(
                        document_name=meta.get("source_document", "Unknown"),
                        section=meta.get("section", ""),
                        chunk_index=0,
                    ),
                    intent=meta.get("intent", ""),
                    section=meta.get("section", ""),
                    original_question=meta.get("original_question"),
                    original_answer=meta.get("original_answer"),
                )
                
                chunks.append(chunk)
                scores.append(sim)
        
        # Limit to max_context_docs
        chunks = chunks[:self.config.max_context_docs]
        scores = scores[:self.config.max_context_docs]
        
        # Determine confidence
        confidence = self._determine_confidence(scores)
        
        elapsed_ms = (time.time() - start_time) * 1000
        
        return RetrievalResult(
            query=query,
            chunks=chunks,
            scores=scores,
            confidence=confidence,
            dense_scores=dense_similarities[:len(chunks)] if chunks else None,
            retrieval_time_ms=elapsed_ms,
        )
    
    async def retrieve_async(
        self,
        query: str,
        top_k: Optional[int] = None,
    ) -> RetrievalResult:
        """Async wrapper for retrieve (runs in executor)."""
        import asyncio
        
        return await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self.retrieve(query, top_k)
        )
