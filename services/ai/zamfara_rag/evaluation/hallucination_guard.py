"""
Hallucination guard and verification module for Zamfara RAG system.

Implements post-generation verification to ensure:
- All claims are grounded in retrieved content
- No invented facts or policies
- Citation accuracy
- Consistency with source documents
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


@dataclass
class VerificationResult:
    """Result of verification check."""
    
    passed: bool
    confidence: float  # 0.0 to 1.0
    
    # Detailed findings
    grounded_claims: List[str]
    ungrounded_claims: List[str]
    suspicious_claims: List[str]
    
    # Citation verification
    valid_citations: List[str]
    invalid_citations: List[str]
    
    # Recommendations
    needs_regeneration: bool
    fallback_recommended: bool
    notes: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "passed": self.passed,
            "confidence": self.confidence,
            "grounded_claims_count": len(self.grounded_claims),
            "ungrounded_claims_count": len(self.ungrounded_claims),
            "suspicious_claims_count": len(self.suspicious_claims),
            "needs_regeneration": self.needs_regeneration,
            "fallback_recommended": self.fallback_recommended,
            "notes": self.notes,
        }


class HallucinationGuard:
    """
    Verifies generated answers for hallucination and grounding.
    
    Strategy:
    1. Extract claims from generated answer
    2. Check each claim against retrieved sources
    3. Verify citations reference real sources
    4. Flag suspicious content (specific numbers, dates, names)
    5. Recommend regeneration or fallback if needed
    """
    
    # Patterns for extracting claims
    CLAIM_SEPARATORS = [
        r"(?<=[.!?])\s+",  # Sentence endings
        r"\n+",            # Line breaks
        r"[;]",            # Semicolons
    ]
    
    # Patterns for suspicious content (likely hallucinated if not in source)
    SUSPICIOUS_PATTERNS = [
        (r"\b\d{1,2}/\d{1,2}/\d{4}\b", "specific date"),
        (r"\b\d{4}\b(?!\s*(?:Naira|NGN|₦))", "specific year"),
        (r"₦[\d,]+(?:\.\d{2})?", "specific amount"),
        (r"NGN\s*[\d,]+(?:\.\d{2})?", "specific amount"),
        (r"\b\d+(?:,\d{3})*\s*(?:Naira)", "specific amount"),
        (r"\b\d+\s*%\b", "specific percentage"),
        (r"\b(?:Section|Article|Clause)\s+\d+(?:\.\d+)*", "specific section reference"),
        (r"(?:phone|tel|fax)[:\s]*[\d\-\+\(\)]+", "phone number"),
        (r"\b[A-Z][a-z]+\s+[A-Z][a-z]+\b", "proper name"),  # Names
    ]
    
    # High-risk phrases that suggest hallucination
    HALLUCINATION_INDICATORS = [
        "i believe",
        "i think",
        "probably",
        "might be",
        "could be",
        "usually",
        "typically",
        "generally",
        "in my experience",
        "as far as i know",
        "it is common",
        "it is possible",
    ]
    
    def __init__(
        self,
        confidence_threshold: float = 0.6,
        min_grounding_ratio: float = 0.7,
        strict_mode: bool = True,
    ):
        """
        Initialize the hallucination guard.
        
        Args:
            confidence_threshold: Minimum confidence to pass verification
            min_grounding_ratio: Minimum ratio of grounded claims
            strict_mode: If True, be more conservative
        """
        self.confidence_threshold = confidence_threshold
        self.min_grounding_ratio = min_grounding_ratio
        self.strict_mode = strict_mode
        
        # Compile patterns
        self._suspicious_patterns = [
            (re.compile(p, re.IGNORECASE), desc)
            for p, desc in self.SUSPICIOUS_PATTERNS
        ]
    
    def verify(
        self,
        answer: str,
        source_texts: List[str],
        citations: List[str],
    ) -> VerificationResult:
        """
        Verify a generated answer against source texts.
        
        Args:
            answer: Generated answer text
            source_texts: List of source document texts
            citations: List of claimed citations
            
        Returns:
            VerificationResult with detailed findings
        """
        if not answer or not answer.strip():
            return VerificationResult(
                passed=False,
                confidence=0.0,
                grounded_claims=[],
                ungrounded_claims=[],
                suspicious_claims=[],
                valid_citations=[],
                invalid_citations=[],
                needs_regeneration=False,
                fallback_recommended=True,
                notes="Empty answer",
            )
        
        # Check for hallucination indicator phrases
        hallucination_phrases = self._check_hallucination_phrases(answer)
        
        # Extract claims from answer
        claims = self._extract_claims(answer)
        
        # Verify each claim against sources
        grounded = []
        ungrounded = []
        suspicious = []
        
        combined_sources = " ".join(source_texts).lower()
        
        for claim in claims:
            grounding_score = self._check_claim_grounding(claim, combined_sources, source_texts)
            
            if grounding_score >= 0.6:
                grounded.append(claim)
            elif grounding_score >= 0.3:
                suspicious.append(claim)
            else:
                # Check if it contains suspicious specific content
                has_suspicious = self._has_suspicious_content(claim, combined_sources)
                if has_suspicious:
                    suspicious.append(claim)
                else:
                    ungrounded.append(claim)
        
        # Verify citations
        valid_citations, invalid_citations = self._verify_citations(
            answer, citations, source_texts
        )
        
        # Calculate overall confidence
        total_claims = len(grounded) + len(ungrounded) + len(suspicious)
        
        if total_claims == 0:
            grounding_ratio = 1.0  # No claims to verify
        else:
            grounding_ratio = len(grounded) / total_claims
        
        # Penalties
        confidence = grounding_ratio
        
        if hallucination_phrases:
            confidence *= 0.7  # Penalty for uncertain language
        
        if invalid_citations:
            confidence *= 0.8  # Penalty for bad citations
        
        if suspicious:
            confidence *= 0.9  # Small penalty for suspicious content
        
        # Determine if verification passed
        passed = (
            confidence >= self.confidence_threshold and
            grounding_ratio >= self.min_grounding_ratio and
            len(ungrounded) == 0  # No completely ungrounded claims in strict mode
        )
        
        if not self.strict_mode:
            # Relaxed mode: allow some ungrounded claims
            passed = confidence >= self.confidence_threshold
        
        # Determine recommendations
        needs_regeneration = not passed and confidence > 0.3
        fallback_recommended = confidence <= 0.3 or len(ungrounded) > len(grounded)
        
        # Build notes
        notes_parts = []
        if hallucination_phrases:
            notes_parts.append(f"Uncertain language detected: {hallucination_phrases}")
        if ungrounded:
            notes_parts.append(f"Ungrounded claims: {len(ungrounded)}")
        if suspicious:
            notes_parts.append(f"Suspicious claims: {len(suspicious)}")
        if invalid_citations:
            notes_parts.append(f"Invalid citations: {len(invalid_citations)}")
        
        return VerificationResult(
            passed=passed,
            confidence=confidence,
            grounded_claims=grounded,
            ungrounded_claims=ungrounded,
            suspicious_claims=suspicious,
            valid_citations=valid_citations,
            invalid_citations=invalid_citations,
            needs_regeneration=needs_regeneration,
            fallback_recommended=fallback_recommended,
            notes="; ".join(notes_parts) if notes_parts else "Verification passed",
        )
    
    def _check_hallucination_phrases(self, text: str) -> List[str]:
        """Check for phrases that indicate hallucination."""
        text_lower = text.lower()
        found = []
        
        for phrase in self.HALLUCINATION_INDICATORS:
            if phrase in text_lower:
                found.append(phrase)
        
        return found
    
    def _extract_claims(self, text: str) -> List[str]:
        """Extract individual claims from text."""
        # Split by sentence boundaries
        claims = []
        
        # First split by obvious boundaries
        parts = re.split(r"(?<=[.!?])\s+", text)
        
        for part in parts:
            part = part.strip()
            
            # Skip very short parts
            if len(part) < 20:
                continue
            
            # Skip questions
            if part.endswith("?"):
                continue
            
            # Skip citations-only parts
            if part.startswith("[") and part.endswith("]"):
                continue
            
            claims.append(part)
        
        return claims
    
    def _check_claim_grounding(
        self,
        claim: str,
        combined_sources: str,
        source_texts: List[str]
    ) -> float:
        """
        Check how well a claim is grounded in sources.
        
        Returns a score from 0.0 (not grounded) to 1.0 (fully grounded).
        """
        claim_lower = claim.lower()
        
        # Extract key terms from claim
        # Remove common words
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "must", "shall",
            "can", "need", "to", "of", "in", "for", "on", "with", "at",
            "by", "from", "as", "into", "through", "during", "before",
            "after", "above", "below", "between", "under", "again",
            "further", "then", "once", "here", "there", "when", "where",
            "why", "how", "all", "each", "few", "more", "most", "other",
            "some", "such", "no", "nor", "not", "only", "own", "same",
            "so", "than", "too", "very", "just", "and", "but", "if", "or",
            "because", "until", "while", "this", "that", "these", "those",
        }
        
        words = set(re.findall(r"\b\w{3,}\b", claim_lower))
        key_words = words - stop_words
        
        if not key_words:
            return 0.5  # Neutral if no key words
        
        # Check word overlap
        found_words = sum(1 for w in key_words if w in combined_sources)
        word_overlap = found_words / len(key_words)
        
        # Check for phrase matches
        phrase_score = 0.0
        for length in [5, 4, 3]:  # Try different n-gram lengths
            words_list = claim_lower.split()
            for i in range(len(words_list) - length + 1):
                phrase = " ".join(words_list[i:i+length])
                if phrase in combined_sources:
                    phrase_score = max(phrase_score, 0.3 * length / 5)
        
        # Check semantic similarity with sources
        best_source_match = 0.0
        for source in source_texts:
            similarity = self._text_similarity(claim_lower, source.lower())
            best_source_match = max(best_source_match, similarity)
        
        # Combine scores
        final_score = (
            word_overlap * 0.4 +
            phrase_score * 0.3 +
            best_source_match * 0.3
        )
        
        return min(final_score, 1.0)
    
    def _has_suspicious_content(self, claim: str, combined_sources: str) -> bool:
        """Check if claim contains suspicious specific content not in sources."""
        for pattern, desc in self._suspicious_patterns:
            matches = pattern.findall(claim)
            for match in matches:
                # Check if this specific value appears in sources
                if match.lower() not in combined_sources:
                    logger.debug(f"Suspicious {desc} not in sources: {match}")
                    return True
        
        return False
    
    def _verify_citations(
        self,
        answer: str,
        claimed_citations: List[str],
        source_texts: List[str]
    ) -> Tuple[List[str], List[str]]:
        """
        Verify citations in the answer.
        
        Returns:
            Tuple of (valid_citations, invalid_citations)
        """
        # Extract citations from answer text
        citation_pattern = r"\[([^\]]+)\]"
        inline_citations = re.findall(citation_pattern, answer)
        
        valid = []
        invalid = []
        
        for citation in inline_citations:
            citation_lower = citation.lower()
            
            # Check if citation matches any claimed citation
            is_valid = any(
                self._citation_matches(citation_lower, claimed.lower())
                for claimed in claimed_citations
            )
            
            if is_valid:
                valid.append(citation)
            else:
                invalid.append(citation)
        
        return valid, invalid
    
    def _citation_matches(self, citation1: str, citation2: str) -> bool:
        """Check if two citations refer to the same source."""
        # Simple word overlap check
        words1 = set(citation1.split())
        words2 = set(citation2.split())
        
        if not words1 or not words2:
            return False
        
        overlap = len(words1 & words2)
        min_len = min(len(words1), len(words2))
        
        return overlap / min_len >= 0.5
    
    def _text_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity using sequence matching."""
        # Use SequenceMatcher for similarity
        # For efficiency, compare only first 500 chars
        t1 = text1[:500]
        t2 = text2[:500]
        
        matcher = SequenceMatcher(None, t1, t2)
        return matcher.ratio()
    
    def quick_check(self, answer: str) -> Tuple[bool, str]:
        """
        Perform a quick sanity check on the answer.
        
        Returns:
            Tuple of (passed, reason)
        """
        if not answer or len(answer.strip()) < 10:
            return False, "Answer too short"
        
        # Check for hallucination phrases
        phrases = self._check_hallucination_phrases(answer)
        if phrases:
            return False, f"Contains uncertain language: {phrases[0]}"
        
        # Check for obviously fabricated content
        if "as an AI" in answer.lower() or "i cannot" in answer.lower():
            return False, "Contains AI self-reference"
        
        return True, "Quick check passed"




