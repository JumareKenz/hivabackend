"""
Retrieval module for Zamfara RAG system.

Implements intelligent document retrieval with:
- Query embedding
- Similarity search
- Metadata filtering
- Re-ranking for precision
- Context deduplication
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """Represents a single retrieval result with full context."""
    
    # Content
    text: str
    
    # Source information
    document_title: str
    document_type: str
    section_heading: str
    file_path: str
    
    # Relevance scores
    similarity_score: float
    rerank_score: Optional[float] = None
    final_score: float = 0.0
    
    # Ranking
    rank: int = 0
    
    # Metadata
    department: str = "unknown"
    chunk_id: str = ""
    
    def __post_init__(self):
        if self.final_score == 0.0:
            self.final_score = self.rerank_score or self.similarity_score
    
    def to_citation(self) -> str:
        """Generate a citation string for this result."""
        parts = [self.document_title]
        if self.section_heading and self.section_heading != self.document_title:
            parts.append(f"Section: {self.section_heading}")
        return " - ".join(parts)


@dataclass
class RetrievalResponse:
    """Complete retrieval response with results and metadata."""
    
    query: str
    results: List[RetrievalResult]
    total_results: int
    
    # Performance metadata
    retrieval_time_ms: float = 0.0
    reranking_applied: bool = False
    filters_applied: List[str] = field(default_factory=list)
    
    def get_context(self, max_results: int = 5) -> str:
        """Get formatted context string for LLM."""
        context_parts = []
        
        for result in self.results[:max_results]:
            # Format each chunk with source info
            chunk_context = f"[Source: {result.document_title}"
            if result.section_heading:
                chunk_context += f" | Section: {result.section_heading}"
            chunk_context += "]\n"
            chunk_context += result.text
            context_parts.append(chunk_context)
        
        return "\n\n---\n\n".join(context_parts)
    
    def get_citations(self) -> List[str]:
        """Get list of unique citations."""
        seen = set()
        citations = []
        for result in self.results:
            citation = result.to_citation()
            if citation not in seen:
                seen.add(citation)
                citations.append(citation)
        return citations


class Retriever:
    """
    Intelligent document retriever for the Zamfara RAG system.
    
    Features:
    - Embedding-based similarity search
    - Metadata filtering
    - Keyword-based re-ranking
    - Context deduplication
    - Query analysis
    """
    
    def __init__(
        self,
        vector_store,
        embedding_generator,
        default_k: int = 5,
        enable_reranking: bool = True,
        min_similarity: float = 0.3,
    ):
        """
        Initialize the retriever.
        
        Args:
            vector_store: VectorStore instance
            embedding_generator: EmbeddingGenerator instance
            default_k: Default number of results to retrieve
            enable_reranking: Whether to apply re-ranking
            min_similarity: Minimum similarity threshold
        """
        self.vector_store = vector_store
        self.embedding_generator = embedding_generator
        self.default_k = default_k
        self.enable_reranking = enable_reranking
        self.min_similarity = min_similarity
    
    def retrieve(
        self,
        query: str,
        k: Optional[int] = None,
        document_type: Optional[str] = None,
        department: Optional[str] = None,
        min_similarity: Optional[float] = None,
    ) -> RetrievalResponse:
        """
        Retrieve relevant documents for a query.
        
        Args:
            query: User query string
            k: Number of results to return (default: self.default_k)
            document_type: Filter by document type
            department: Filter by department
            min_similarity: Minimum similarity threshold
            
        Returns:
            RetrievalResponse with results and metadata
        """
        import time
        start_time = time.time()
        
        k = k or self.default_k
        min_sim = min_similarity or self.min_similarity
        
        # Normalize query
        query = self._normalize_query(query)
        
        if not query:
            return RetrievalResponse(
                query=query,
                results=[],
                total_results=0,
            )
        
        logger.info(f"Retrieving for query: '{query[:50]}...' (k={k})")
        
        # Generate query embedding
        query_embedding = self.embedding_generator.embed_query(query)
        
        # Search with extra results for filtering/reranking
        search_k = min(k * 3, 20)  # Get extra for filtering
        
        # Build metadata filter
        filter_dict = self._build_filter(document_type, department)
        
        # Perform search
        raw_results = self.vector_store.search(
            query_embedding=query_embedding,
            k=search_k,
            filter_dict=filter_dict,
        )
        
        # Convert to RetrievalResult objects
        results = []
        for raw in raw_results:
            meta = raw.get("metadata", {})
            
            # Skip low similarity results
            if raw.get("similarity", 0) < min_sim:
                continue
            
            result = RetrievalResult(
                text=raw.get("document", ""),
                document_title=meta.get("document_title", "Unknown"),
                document_type=meta.get("document_type", "unknown"),
                section_heading=meta.get("section_heading", ""),
                file_path=meta.get("file_path", ""),
                similarity_score=raw.get("similarity", 0),
                department=meta.get("department", "unknown"),
                chunk_id=raw.get("id", ""),
            )
            results.append(result)
        
        # Apply re-ranking
        reranking_applied = False
        if self.enable_reranking and results:
            results = self._rerank(query, results)
            reranking_applied = True
        
        # Deduplicate similar content
        results = self._deduplicate(results)
        
        # Limit to k results
        results = results[:k]
        
        # Assign final ranks
        for i, result in enumerate(results):
            result.rank = i + 1
        
        # Build filters list
        filters_applied = []
        if document_type:
            filters_applied.append(f"document_type={document_type}")
        if department:
            filters_applied.append(f"department={department}")
        
        elapsed = (time.time() - start_time) * 1000
        
        response = RetrievalResponse(
            query=query,
            results=results,
            total_results=len(results),
            retrieval_time_ms=elapsed,
            reranking_applied=reranking_applied,
            filters_applied=filters_applied,
        )
        
        logger.info(
            f"Retrieved {len(results)} results in {elapsed:.1f}ms "
            f"(reranking={'yes' if reranking_applied else 'no'})"
        )
        
        return response
    
    def _normalize_query(self, query: str) -> str:
        """Normalize the query for better matching."""
        if not query:
            return ""
        
        # Basic cleaning
        query = query.strip()
        
        # Remove excessive punctuation
        query = re.sub(r"[?!.]+$", "", query)
        
        # Normalize whitespace
        query = re.sub(r"\s+", " ", query)
        
        return query
    
    def _build_filter(
        self,
        document_type: Optional[str],
        department: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        """Build ChromaDB filter dictionary."""
        conditions = []
        
        if document_type:
            conditions.append({"document_type": document_type})
        
        if department:
            conditions.append({"department": department})
        
        if not conditions:
            return None
        
        if len(conditions) == 1:
            return conditions[0]
        
        return {"$and": conditions}
    
    def _rerank(
        self,
        query: str,
        results: List[RetrievalResult]
    ) -> List[RetrievalResult]:
        """
        Re-rank results based on keyword overlap and other signals.
        
        This is a lightweight re-ranker that doesn't require a separate model.
        For better precision, a cross-encoder could be used.
        """
        query_lower = query.lower()
        query_terms = set(query_lower.split())
        
        # Extract key terms (longer words, likely meaningful)
        key_terms = [t for t in query_terms if len(t) > 3]
        
        for result in results:
            text_lower = result.text.lower()
            
            # Calculate term overlap score
            term_overlap = sum(1 for term in key_terms if term in text_lower)
            overlap_score = term_overlap / max(len(key_terms), 1)
            
            # Check for exact phrase matches
            phrase_bonus = 0.0
            if len(query) > 10:
                # Check for significant substrings
                for i in range(0, len(query) - 10, 5):
                    substring = query_lower[i:i+15]
                    if substring in text_lower:
                        phrase_bonus += 0.1
            
            phrase_bonus = min(phrase_bonus, 0.3)  # Cap bonus
            
            # Check section heading relevance
            heading_bonus = 0.0
            if result.section_heading:
                heading_lower = result.section_heading.lower()
                heading_overlap = sum(1 for term in key_terms if term in heading_lower)
                heading_bonus = 0.1 * heading_overlap
            
            # Calculate final rerank score
            result.rerank_score = (
                result.similarity_score * 0.5 +  # Base similarity
                overlap_score * 0.3 +             # Term overlap
                phrase_bonus +                     # Phrase matches
                heading_bonus                      # Heading relevance
            )
            
            result.final_score = result.rerank_score
        
        # Sort by final score
        results.sort(key=lambda x: x.final_score, reverse=True)
        
        return results
    
    def _deduplicate(
        self,
        results: List[RetrievalResult],
        similarity_threshold: float = 0.85
    ) -> List[RetrievalResult]:
        """
        Remove near-duplicate results.
        
        Uses simple text similarity to detect duplicates.
        """
        if len(results) <= 1:
            return results
        
        unique_results = []
        seen_texts = []
        
        for result in results:
            # Check similarity with already accepted results
            is_duplicate = False
            
            for seen in seen_texts:
                similarity = self._text_similarity(result.text, seen)
                if similarity > similarity_threshold:
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique_results.append(result)
                seen_texts.append(result.text)
        
        return unique_results
    
    def _text_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate simple text similarity using word overlap.
        
        Returns value between 0 and 1.
        """
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0
    
    def analyze_query(self, query: str) -> Dict[str, Any]:
        """
        Analyze query for intent and filtering hints.
        
        Returns:
            Dictionary with analysis results
        """
        query_lower = query.lower()
        
        analysis = {
            "original_query": query,
            "normalized_query": self._normalize_query(query),
            "suggested_document_type": None,
            "suggested_department": None,
            "query_type": "general",
        }
        
        # Detect document type hints
        if any(word in query_lower for word in ["policy", "rule", "regulation"]):
            analysis["suggested_document_type"] = "policy"
        elif any(word in query_lower for word in ["guideline", "guide", "how to"]):
            analysis["suggested_document_type"] = "guideline"
        elif any(word in query_lower for word in ["procedure", "process", "steps"]):
            analysis["suggested_document_type"] = "sop"
        
        # Detect department hints
        department_keywords = {
            "health": ["health", "medical", "hospital", "clinic"],
            "finance": ["finance", "budget", "payment", "tax"],
            "education": ["education", "school", "student", "teacher"],
            "agriculture": ["agriculture", "farming", "crop", "livestock"],
        }
        
        for dept, keywords in department_keywords.items():
            if any(kw in query_lower for kw in keywords):
                analysis["suggested_department"] = dept
                break
        
        # Detect query type
        if query_lower.startswith(("what", "who", "when", "where", "which")):
            analysis["query_type"] = "factual"
        elif query_lower.startswith(("how", "explain")):
            analysis["query_type"] = "procedural"
        elif query_lower.startswith(("why", "what if")):
            analysis["query_type"] = "explanatory"
        
        return analysis




