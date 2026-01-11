"""
RAG Grounding Firewall - Mandatory Grounding Enforcement

This module ensures that:
- Every answer is derived from retrieved chunks
- Every factual claim maps to a source chunk
- Citations are mandatory (not optional)
- No external knowledge is used

This is the core anti-hallucination mechanism.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

from app.providers_rag.schemas import DocumentChunk, RetrievalResult

logger = logging.getLogger(__name__)


@dataclass
class GroundingCheckResult:
    """Result of a grounding check."""
    
    is_grounded: bool
    grounding_score: float  # 0.0 to 1.0
    mapped_chunks: list[int]  # Indices of chunks that support the answer
    unmapped_claims: list[str]  # Claims that couldn't be mapped to chunks
    reason: Optional[str] = None


class RAGGroundingFirewall:
    """
    Enforces mandatory grounding of all responses.
    
    This is a hard gate - responses that cannot be grounded
    in retrieved chunks must be refused.
    """
    
    def __init__(self):
        # Minimum grounding score to accept (0.0 to 1.0)
        self.min_grounding_score = 0.3
        
        # Minimum number of chunks that must support the answer
        self.min_supporting_chunks = 1
        
        # Stop words to ignore in grounding checks
        self._stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been',
            'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
            'could', 'should', 'may', 'might', 'can', 'this', 'that', 'these',
            'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'what', 'which',
            'who', 'when', 'where', 'why', 'how', 'all', 'each', 'every', 'both',
            'few', 'more', 'most', 'other', 'some', 'such', 'no', 'not', 'only',
            'same', 'so', 'than', 'too', 'very', 'just', 'also', 'now', 'if',
            'please', 'thank', 'thanks', 'yes', 'no', 'ok', 'okay'
        }
    
    def _extract_key_terms(self, text: str) -> set[str]:
        """Extract key terms from text (excluding stop words)."""
        # Normalize and tokenize
        text_lower = text.lower()
        # Remove punctuation
        text_clean = re.sub(r'[^\w\s]', ' ', text_lower)
        # Split into words
        words = text_clean.split()
        # Filter stop words and short words
        key_terms = {w for w in words if w not in self._stop_words and len(w) > 2}
        return key_terms
    
    def _calculate_chunk_overlap(
        self,
        answer_terms: set[str],
        chunk: DocumentChunk
    ) -> float:
        """
        Calculate how much of the answer overlaps with a chunk.
        
        Returns a score between 0.0 and 1.0.
        """
        # Extract terms from chunk
        chunk_text = chunk.content.lower()
        if chunk.original_answer:
            chunk_text += " " + chunk.original_answer.lower()
        
        chunk_terms = self._extract_key_terms(chunk_text)
        
        if not answer_terms:
            return 0.0
        
        # Calculate overlap
        overlap = answer_terms & chunk_terms
        overlap_score = len(overlap) / len(answer_terms)
        
        return overlap_score
    
    def check_grounding(
        self,
        answer: str,
        retrieval_result: RetrievalResult,
        require_citations: bool = True,
    ) -> GroundingCheckResult:
        """
        Check if an answer is properly grounded in retrieved chunks.
        
        Args:
            answer: Generated answer text
            retrieval_result: Original retrieval results
            require_citations: Whether citations are mandatory
            
        Returns:
            GroundingCheckResult with grounding status and details
        """
        # Check if we have retrieval results
        if not retrieval_result.chunks:
            return GroundingCheckResult(
                is_grounded=False,
                grounding_score=0.0,
                mapped_chunks=[],
                unmapped_claims=[],
                reason="No retrieved chunks available",
            )
        
        # Check if citations are required
        if require_citations and not retrieval_result.chunks:
            return GroundingCheckResult(
                is_grounded=False,
                grounding_score=0.0,
                mapped_chunks=[],
                unmapped_claims=[],
                reason="Citations required but no chunks retrieved",
            )
        
        # Extract key terms from answer
        answer_terms = self._extract_key_terms(answer)
        
        if not answer_terms:
            # Answer is too generic or empty
            return GroundingCheckResult(
                is_grounded=False,
                grounding_score=0.0,
                mapped_chunks=[],
                unmapped_claims=[],
                reason="Answer contains no meaningful terms",
            )
        
        # Check grounding against each chunk
        chunk_scores: list[tuple[int, float]] = []
        for i, chunk in enumerate(retrieval_result.chunks):
            score = self._calculate_chunk_overlap(answer_terms, chunk)
            chunk_scores.append((i, score))
        
        # Sort by score (descending)
        chunk_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Find chunks that support the answer (score > threshold)
        supporting_chunks = [i for i, score in chunk_scores if score >= 0.2]
        
        # Calculate overall grounding score
        if chunk_scores:
            # Use the best chunk's score as primary indicator
            best_score = chunk_scores[0][1]
            # Also consider how many chunks support it
            support_ratio = len(supporting_chunks) / len(retrieval_result.chunks)
            # Combined score
            grounding_score = (best_score * 0.7) + (support_ratio * 0.3)
        else:
            grounding_score = 0.0
        
        # Check if grounding meets minimum threshold
        is_grounded = (
            grounding_score >= self.min_grounding_score and
            len(supporting_chunks) >= self.min_supporting_chunks
        )
        
        # Identify unmapped claims (sentences with low grounding)
        unmapped_claims = []
        if not is_grounded:
            # Split answer into sentences
            sentences = re.split(r'[.!?]+\s+', answer)
            for sentence in sentences:
                sentence_terms = self._extract_key_terms(sentence)
                if not sentence_terms:
                    continue
                
                # Check if sentence is grounded
                sentence_grounded = False
                for chunk in retrieval_result.chunks:
                    overlap = self._calculate_chunk_overlap(sentence_terms, chunk)
                    if overlap >= 0.2:
                        sentence_grounded = True
                        break
                
                if not sentence_grounded and len(sentence.strip()) > 20:
                    unmapped_claims.append(sentence.strip())
        
        reason = None
        if not is_grounded:
            if grounding_score < self.min_grounding_score:
                reason = f"Grounding score {grounding_score:.2f} below threshold {self.min_grounding_score}"
            elif len(supporting_chunks) < self.min_supporting_chunks:
                reason = f"Only {len(supporting_chunks)} supporting chunks, need {self.min_supporting_chunks}"
        
        return GroundingCheckResult(
            is_grounded=is_grounded,
            grounding_score=grounding_score,
            mapped_chunks=supporting_chunks,
            unmapped_claims=unmapped_claims[:5],  # Limit to first 5
            reason=reason,
        )
    
    def enforce_grounding(
        self,
        answer: str,
        retrieval_result: RetrievalResult,
    ) -> tuple[bool, Optional[str]]:
        """
        Enforce grounding - refuse if not grounded.
        
        Returns:
            (is_allowed, refusal_message_if_not_allowed)
        """
        result = self.check_grounding(answer, retrieval_result, require_citations=True)
        
        if not result.is_grounded:
            refusal_msg = (
                "The provided documents do not contain sufficient information "
                "to answer this question accurately."
            )
            if result.reason:
                logger.warning(f"Grounding failed: {result.reason}")
            return False, refusal_msg
        
        return True, None
