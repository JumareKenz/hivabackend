"""
Safety and Governance Module for Provider RAG.

Implements:
- Hard refusal logic when information is unavailable
- Confidence gating
- Hallucination detection heuristics
- Response validation

This module is the last line of defense against hallucination.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from app.providers_rag.config import provider_rag_config
from app.providers_rag.schemas import (
    ConfidenceLevel,
    QueryResult,
    RetrievalResult,
)

logger = logging.getLogger(__name__)


class SafetyGate:
    """
    Safety gate for validating and filtering RAG responses.
    
    Responsibilities:
    1. Validate retrieval confidence meets thresholds
    2. Detect potential hallucination patterns
    3. Apply content filters
    4. Generate safe refusal responses
    """
    
    def __init__(self, config: Optional[object] = None):
        self.config = config or provider_rag_config
        
        # Known hallucination patterns - responses that indicate the model
        # may be generating content not in the source material
        self._hallucination_patterns = [
            r"as an ai",
            r"i think",
            r"i believe",
            r"in my opinion",
            r"probably",
            r"might be",
            r"could be",
            r"i would guess",
            r"generally speaking",
            r"typically",
            r"usually",
            r"it's common to",
            r"most people",
            r"from my training",
            r"based on my knowledge",
            r"i was trained",
        ]
        
        # Patterns that indicate grounded responses
        self._grounded_patterns = [
            r"according to",
            r"the (portal|system|code|claim)",
            r"you (should|need to|must|can)",
            r"contact ict",
            r"authorization code",
            r"enrollee",
            r"provider",
            r"claims",
        ]
    
    def _detect_potential_hallucination(self, response: str) -> tuple[bool, list[str]]:
        """
        Detect patterns that may indicate hallucination.
        
        Returns:
            Tuple of (is_suspicious, list of matched patterns)
        """
        response_lower = response.lower()
        matched_patterns = []
        
        for pattern in self._hallucination_patterns:
            if re.search(pattern, response_lower):
                matched_patterns.append(pattern)
        
        # High suspicion if multiple patterns match
        is_suspicious = len(matched_patterns) >= 2
        
        return is_suspicious, matched_patterns
    
    def _check_grounding(self, response: str, context_chunks: list) -> float:
        """
        Check how well the response is grounded in the context.
        
        Returns a grounding score between 0 and 1.
        Higher scores indicate better grounding.
        """
        if not context_chunks:
            return 0.0
        
        response_lower = response.lower()
        
        # Check for domain-specific terms from context
        grounded_term_count = 0
        total_checks = 0
        
        for pattern in self._grounded_patterns:
            total_checks += 1
            if re.search(pattern, response_lower):
                grounded_term_count += 1
        
        # Also check if key terms from chunks appear in response
        for chunk in context_chunks[:3]:  # Check top 3 chunks
            content_lower = chunk.content.lower() if hasattr(chunk, 'content') else str(chunk).lower()
            
            # Extract key terms (nouns, important words)
            key_terms = re.findall(r'\b[a-z]{4,}\b', content_lower)
            key_terms = [t for t in key_terms if t not in {
                "that", "this", "with", "from", "have", "will", "your", "what",
                "when", "where", "which", "their", "about", "would", "there"
            }]
            
            for term in key_terms[:10]:  # Check top 10 key terms
                total_checks += 1
                if term in response_lower:
                    grounded_term_count += 1
        
        return grounded_term_count / total_checks if total_checks > 0 else 0.0
    
    def validate_retrieval(self, retrieval_result: RetrievalResult) -> tuple[bool, str]:
        """
        Validate retrieval results meet safety criteria.
        
        Returns:
            Tuple of (is_valid, reason_if_invalid)
        """
        # Check if we have any results
        if not retrieval_result.chunks:
            return False, "No documents retrieved"
        
        # Check minimum document count
        if len(retrieval_result.chunks) < self.config.min_relevant_docs:
            return False, f"Insufficient documents: {len(retrieval_result.chunks)} < {self.config.min_relevant_docs}"
        
        # Check confidence level
        if retrieval_result.confidence == ConfidenceLevel.NONE:
            return False, "Confidence level is NONE"
        
        # Check if top score meets threshold
        if retrieval_result.top_score < self.config.min_similarity_threshold:
            return False, f"Top score {retrieval_result.top_score:.3f} below threshold {self.config.min_similarity_threshold}"
        
        return True, ""
    
    def validate_response(
        self,
        response: str,
        retrieval_result: RetrievalResult
    ) -> tuple[bool, str, Optional[str]]:
        """
        Validate a generated response for safety.
        
        Returns:
            Tuple of (is_safe, reason, suggested_replacement)
        """
        if not response:
            return False, "Empty response", self.config.refusal_message
        
        # Check for hallucination patterns
        is_suspicious, patterns = self._detect_potential_hallucination(response)
        
        if is_suspicious:
            logger.warning(
                f"Potential hallucination detected. Patterns: {patterns}"
            )
            # Don't immediately reject, but flag for review
            # In strict mode, we might want to reject
        
        # Check grounding score
        grounding_score = self._check_grounding(response, retrieval_result.chunks)
        
        if grounding_score < 0.2:  # Very low grounding
            logger.warning(
                f"Low grounding score: {grounding_score:.3f}"
            )
            # In strict mode, might want to reject
        
        # Check response length - very short responses might be incomplete
        if len(response) < 20 and not any(
            phrase in response.lower() for phrase in ["yes", "no", "correct", "incorrect"]
        ):
            return False, "Response too short", None
        
        # Check for obvious error patterns
        error_patterns = [
            r"error",
            r"exception",
            r"traceback",
            r"undefined",
            r"null",
            r"\{\{",  # Template markers
            r"\[\[",  # Wiki-style markers
        ]
        
        for pattern in error_patterns:
            if re.search(pattern, response.lower()):
                logger.warning(f"Error pattern detected in response: {pattern}")
        
        return True, "", None
    
    def apply_safety_gate(self, query_result: QueryResult) -> QueryResult:
        """
        Apply final safety checks to a query result.
        
        May modify the result if safety concerns are detected.
        """
        # Already a refusal - pass through
        if query_result.is_refusal:
            return query_result
        
        # Validate the response
        is_safe, reason, replacement = self.validate_response(
            query_result.answer,
            query_result.retrieval_result if query_result.retrieval_result else RetrievalResult(query=""),
        )
        
        if not is_safe and replacement:
            logger.warning(f"Safety gate triggered: {reason}. Replacing response.")
            query_result.answer = replacement
            query_result.is_refusal = True
            query_result.confidence = ConfidenceLevel.NONE
            query_result.confidence_score = 0.0
        
        # Additional check: if confidence is LOW and response is long,
        # add a disclaimer
        if (
            query_result.confidence == ConfidenceLevel.LOW 
            and len(query_result.answer) > 200
            and not query_result.is_refusal
        ):
            disclaimer = (
                "\n\n⚠️ Note: This information is based on limited context. "
                "Please verify with ICT support if needed."
            )
            if disclaimer not in query_result.answer:
                query_result.answer += disclaimer
        
        return query_result
    
    def create_safe_refusal(
        self,
        query: str,
        reason: str = ""
    ) -> QueryResult:
        """
        Create a safe refusal response.
        
        Used when the system cannot provide a confident answer.
        """
        refusal_message = self.config.refusal_message
        
        if reason:
            logger.info(f"Creating refusal for query '{query[:50]}...': {reason}")
        
        return QueryResult(
            query=query,
            answer=refusal_message,
            confidence=ConfidenceLevel.NONE,
            confidence_score=0.0,
            citations=[],
            is_grounded=True,
            is_refusal=True,
            needs_clarification=False,
        )


class QueryClassifier:
    """
    Classifies incoming queries to detect edge cases.
    
    Identifies:
    - Greetings
    - Off-topic questions
    - Ambiguous queries
    - Follow-up questions
    """
    
    def __init__(self):
        # Greeting patterns
        self._greeting_patterns = [
            r"^(hi|hello|hey|yo|greetings|good\s+(morning|afternoon|evening))[!.,\s]*$",
        ]
        
        # Thank you patterns
        self._thanks_patterns = [
            r"\b(thank|thanks|thank\s+you|appreciate|grateful)\b",
        ]
        
        # Off-topic indicators - expanded list
        self._offtopic_patterns = [
            r"\b(weather|sports|news|politics|movie|music|game|recipe)\b",
            r"\b(who is|what is the capital|how tall|how old)\b",
            r"\b(joke|funny|laugh|entertain)\b",
            r"\b(ai[- ]?powered|machine learning|blockchain|crypto)\b",
            r"\b(salary|wage|compensation|pay scale)\b",
            r"\b(aws|azure|google cloud|kubernetes)\b",
        ]
        
        # Ambiguous query indicators
        self._ambiguous_patterns = [
            r"^(it|this|that|they|them|those|these)[\s\?]*$",
            r"^(what|how|why|when|where)[\s\?]*$",
        ]
        
        # Domain-relevant keywords - if query lacks these, more likely off-topic
        self._domain_keywords = {
            "portal", "login", "password", "claim", "claims", "submit", "authorization",
            "auth", "code", "enrollee", "enrolment", "enrollment", "provider", "facility",
            "dependant", "dependent", "principal", "benefit", "service", "drug", "drugs",
            "ict", "system", "error", "access", "account", "referral", "encounter",
            "emr", "m&e", "offline", "online", "batch", "sector", "health", "insurance",
            "ohis", "kgshia", "claimify", "browser", "chrome", "firefox"
        }
    
    def is_greeting(self, query: str) -> bool:
        """Check if query is a greeting."""
        query_lower = query.lower().strip()
        return any(
            re.match(pattern, query_lower)
            for pattern in self._greeting_patterns
        )
    
    def is_thanks(self, query: str) -> bool:
        """Check if query is expressing gratitude."""
        query_lower = query.lower()
        return any(
            re.search(pattern, query_lower)
            for pattern in self._thanks_patterns
        )
    
    def is_offtopic(self, query: str) -> bool:
        """Check if query appears to be off-topic."""
        query_lower = query.lower()
        return any(
            re.search(pattern, query_lower)
            for pattern in self._offtopic_patterns
        )
    
    def is_ambiguous(self, query: str) -> bool:
        """Check if query is too ambiguous to answer."""
        query_lower = query.lower().strip()
        
        # Very short queries are often ambiguous
        if len(query.split()) <= 2:
            return any(
                re.match(pattern, query_lower)
                for pattern in self._ambiguous_patterns
            )
        
        return False
    
    def has_domain_relevance(self, query: str) -> bool:
        """
        Check if query has keywords related to the provider domain.
        
        Returns True if query contains domain-relevant keywords,
        False if it appears to be completely off-topic.
        """
        query_lower = query.lower()
        
        # Check for domain keywords
        for keyword in self._domain_keywords:
            if keyword in query_lower:
                return True
        
        # Also check for question patterns about the domain
        domain_patterns = [
            r"how (do|can|to) i",  # How do I... questions
            r"what (should|do|can) i",  # What should I... questions
            r"why (is|does|can't|won't)",  # Why... questions
            r"where (can|do|is)",  # Where... questions
            r"(i can't|i cannot|unable to)",  # Problem statements
            r"(not working|not showing|not loading)",  # Error descriptions
            r"(error|issue|problem|trouble)",  # Problem keywords
        ]
        
        for pattern in domain_patterns:
            if re.search(pattern, query_lower):
                return True
        
        return False
    
    def classify(self, query: str) -> dict:
        """
        Classify a query and return classification results.
        
        Returns dict with classification flags.
        """
        is_greeting = self.is_greeting(query)
        is_thanks = self.is_thanks(query)
        is_offtopic = self.is_offtopic(query)
        is_ambiguous = self.is_ambiguous(query)
        has_domain_relevance = self.has_domain_relevance(query)
        
        # Query needs retrieval if it's not a special case AND has domain relevance
        needs_retrieval = (
            not is_greeting and 
            not is_thanks and 
            not is_ambiguous and
            not is_offtopic and
            (has_domain_relevance or len(query.split()) > 5)  # Long queries get a chance
        )
        
        return {
            "is_greeting": is_greeting,
            "is_thanks": is_thanks,
            "is_offtopic": is_offtopic,
            "is_ambiguous": is_ambiguous,
            "has_domain_relevance": has_domain_relevance,
            "needs_retrieval": needs_retrieval,
        }
