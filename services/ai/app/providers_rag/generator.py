"""
Grounded Answer Generator for Provider RAG.

This module generates answers STRICTLY from retrieved documents.
It implements hard constraints to prevent hallucination.

Features:
- Strict grounding to retrieved content
- Inline citations
- Deterministic response generation
- Refusal when information is unavailable

Usage:
    from app.providers_rag.generator import GroundedGenerator
    
    generator = GroundedGenerator()
    result = await generator.generate(query, retrieval_result)
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

import httpx

from app.core.config import settings
from app.providers_rag.config import provider_rag_config
from app.providers_rag.grounding import RAGGroundingFirewall
from app.providers_rag.integrity import ResponseIntegrityValidator
from app.providers_rag.schemas import (
    Citation,
    ConfidenceLevel,
    DocumentChunk,
    QueryResult,
    RetrievalResult,
)
from app.providers_rag.security import SecurityFilter

logger = logging.getLogger(__name__)


# System prompt for grounded generation - CRITICAL for preventing hallucination
GROUNDED_SYSTEM_PROMPT = """You are a helpful assistant that answers questions ONLY using the provided context.

STRICT RULES (MUST FOLLOW):

1. ANSWER ONLY FROM CONTEXT: Your answer must be derived ENTIRELY from the "RETRIEVED CONTEXT" section below. 
   - If the information is in the context, provide it clearly and helpfully
   - If the information is NOT in the context, you MUST say so

2. NEVER HALLUCINATE: Do NOT make up information, even if you think you know the answer.
   - Do not add details not present in the context
   - Do not extrapolate beyond what the context explicitly states
   - Do not use external knowledge

3. VERBATIM WHEN PRECISE: For specific procedures, steps, or policies, quote or closely paraphrase the source.

4. NO CITATIONS IN RESPONSE: Do NOT include source references, document names, or citations in your answer.
   - Just provide the information naturally
   - The citations are tracked separately

5. ADMIT UNCERTAINTY: If the context is ambiguous or incomplete:
   - Say what IS available
   - Clearly state what additional information might be needed

6. BE PROFESSIONAL AND HELPFUL:
   - Use clear, professional language
   - Structure answers logically
   - Be concise but complete

RESPONSE FORMAT:
- Answer the question directly and naturally
- Use bullet points or numbered lists for steps/procedures
- Keep responses focused and relevant
"""


class GroundedGenerator:
    """
    Generates strictly grounded responses from retrieved documents.
    
    This class ensures that:
    1. All responses are derived from retrieved content
    2. Low-confidence retrievals trigger appropriate handling
    3. Citations are extracted for audit trails
    """
    
    def __init__(self, config: Optional[Any] = None):
        self.config = config or provider_rag_config
        
        # Initialize safety validators
        self._integrity_validator = ResponseIntegrityValidator()
        self._security_filter = SecurityFilter()
        self._grounding_firewall = RAGGroundingFirewall()
        
        # Retry configuration
        self.max_retries = 2
    
    def _build_context(self, chunks: list[DocumentChunk], scores: list[float]) -> str:
        """
        Build the context string from retrieved chunks.
        
        Formats chunks for optimal LLM comprehension while
        preserving source information for citation.
        """
        if not chunks:
            return ""
        
        context_parts = []
        
        for i, (chunk, score) in enumerate(zip(chunks, scores), 1):
            # Format section header if available
            section_info = ""
            if chunk.section:
                section_info = f" (Section: {chunk.section.replace('_', ' ').title()})"
            
            # Use original Q&A format if available, otherwise use content
            if chunk.original_question and chunk.original_answer:
                content = f"Q: {chunk.original_question}\nA: {chunk.original_answer}"
            else:
                content = chunk.content
            
            context_parts.append(
                f"--- Retrieved Document {i}{section_info} ---\n{content}\n"
            )
        
        return "\n".join(context_parts)
    
    def _extract_citations(
        self,
        chunks: list[DocumentChunk],
        scores: list[float]
    ) -> list[Citation]:
        """Extract citation information from chunks."""
        citations = []
        
        for chunk, score in zip(chunks, scores):
            # Use original question as citation text if available
            if chunk.original_question:
                text = chunk.original_question
            else:
                # Extract first sentence as citation
                text = chunk.content.split(".")[0] + "."
                if len(text) > 100:
                    text = text[:100] + "..."
            
            source = chunk.source.document_name
            if chunk.section:
                source = f"{source} - {chunk.section.replace('_', ' ').title()}"
            
            citations.append(Citation(
                text=text,
                source=source,
                relevance_score=score,
            ))
        
        return citations
    
    def _create_refusal_response(
        self,
        query: str,
        confidence: ConfidenceLevel,
    ) -> QueryResult:
        """Create a refusal response when information is not found."""
        return QueryResult(
            query=query,
            answer=self.config.refusal_message,
            confidence=confidence,
            confidence_score=0.0,
            citations=[],
            is_grounded=True,  # Refusal is a grounded response
            is_refusal=True,
            needs_clarification=False,
        )
    
    def _create_clarification_response(
        self,
        query: str,
    ) -> QueryResult:
        """Create a response requesting clarification."""
        return QueryResult(
            query=query,
            answer=self.config.clarification_message,
            confidence=ConfidenceLevel.NONE,
            confidence_score=0.0,
            citations=[],
            is_grounded=True,
            is_refusal=False,
            needs_clarification=True,
        )
    
    async def _call_llm(
        self,
        context: str,
        query: str,
    ) -> str:
        """
        Call the LLM to generate a grounded response.
        
        Uses the configured LLM API with strict temperature settings.
        """
        # Build the prompt
        user_prompt = f"""RETRIEVED CONTEXT:
{context}

USER QUESTION: {query}

Based ONLY on the context above, provide a helpful answer. If the context doesn't contain the needed information, say so clearly."""
        
        messages = [
            {"role": "system", "content": GROUNDED_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        
        # Prepare API call
        api_url = settings.LLM_API_URL
        api_key = getattr(settings, "LLM_API_KEY", None)
        model = settings.LLM_MODEL
        
        # Determine API format
        is_openai_compatible = api_key is not None or "groq" in api_url.lower() or "openai" in api_url.lower()
        
        if is_openai_compatible:
            # OpenAI/Groq format
            payload = {
                "model": model,
                "messages": messages,
                "temperature": self.config.temperature,  # Low for determinism
                "max_tokens": self.config.max_response_tokens,
                "stream": False,
            }
            base = api_url.rstrip("/")
            if base.endswith("/v1"):
                endpoint = f"{base}/chat/completions"
            else:
                endpoint = f"{base}/v1/chat/completions"
            
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
        else:
            # Ollama format
            payload = {
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": self.config.temperature,
                },
            }
            endpoint = f"{api_url.rstrip('/')}/api/chat"
            headers = {"Content-Type": "application/json"}
        
        # Make API call
        async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
            response = await client.post(endpoint, json=payload, headers=headers)
            
            if response.status_code != 200:
                logger.error(f"LLM API error {response.status_code}: {response.text[:500]}")
                raise Exception(f"LLM API error: {response.status_code}")
            
            data = response.json()
        
        # Parse response
        if is_openai_compatible:
            choices = data.get("choices", [])
            if choices:
                return (choices[0].get("message", {}).get("content") or "").strip()
            return ""
        else:
            msg = data.get("message", {})
            return (msg.get("content") or "").strip()
    
    def _handle_token_truncation(self, response: str) -> str:
        """
        Handle token truncation by ensuring complete sentences.
        
        If response appears truncated, remove incomplete last sentence.
        """
        if not response:
            return response
        
        # Check if response ends mid-sentence
        # Look for sentence endings in last 100 chars
        last_100 = response[-100:]
        
        # If ends with sentence punctuation, likely complete
        if re.search(r'[.!?]\s*$', response.rstrip()):
            return response
        
        # If ends with list item or colon, might be intentional
        if re.search(r'[:\-•]\s*$', response.rstrip()):
            return response
        
        # Find last complete sentence
        sentences = re.split(r'([.!?]+\s+)', response)
        if len(sentences) > 1:
            # Reconstruct up to last complete sentence
            complete = ""
            for i in range(0, len(sentences) - 1, 2):
                if i + 1 < len(sentences):
                    complete += sentences[i] + sentences[i + 1]
                else:
                    complete += sentences[i]
            
            if complete.strip():
                return complete.strip()
        
        return response
    
    def _clean_response(self, response: str) -> str:
        """
        Clean the LLM response to remove any unwanted artifacts.
        
        Removes:
        - Source citations that might have been generated
        - Technical markers
        - Excessive whitespace
        """
        # Remove various citation patterns
        patterns_to_remove = [
            r'【[^】]*】',  # Chinese brackets
            r'\[[^\]]*source[^\]]*\]',  # [source: ...]
            r'\([^)]*source[^)]*\)',  # (source: ...)
            r'According to the (context|document|source)[^.]*[,.]',
            r'Based on the (context|document|source)[^.]*[,.]',
            r'From the (context|document|source)[^.]*[,.]',
            r'The (context|document|source) (states|mentions|indicates)[^.]*[,.]',
            r'\(Document \d+\)',  # (Document 1)
            r'Document \d+:?',  # Document 1:
            r'Source:?\s*[A-Za-z\s]+FAQ',  # Source: Providers FAQ
        ]
        
        for pattern in patterns_to_remove:
            response = re.sub(pattern, '', response, flags=re.IGNORECASE)
        
        # Clean up whitespace
        response = re.sub(r'\s+', ' ', response)
        response = re.sub(r'\n\s*\n', '\n\n', response)
        response = response.strip()
        
        return response
    
    async def generate(
        self,
        query: str,
        retrieval_result: RetrievalResult,
    ) -> QueryResult:
        """
        Generate a grounded answer from retrieval results.
        
        Args:
            query: Original user query
            retrieval_result: Results from the retrieval engine
            
        Returns:
            QueryResult with grounded answer and citations
        """
        import time
        start_time = time.time()
        
        # Handle empty query
        if not query or not query.strip():
            return self._create_clarification_response("")
        
        query = query.strip()
        
        # Check if we have relevant results
        if not retrieval_result.has_relevant_results:
            logger.info(f"No relevant results for query: {query[:50]}...")
            return self._create_refusal_response(query, ConfidenceLevel.NONE)
        
        # Check confidence level for strict refusal mode
        if self.config.strict_refusal_mode:
            if retrieval_result.confidence == ConfidenceLevel.NONE:
                return self._create_refusal_response(query, ConfidenceLevel.NONE)
        
        # Build context from retrieved chunks
        context = self._build_context(
            retrieval_result.chunks,
            retrieval_result.scores
        )
        
        # Extract citations (MANDATORY for production)
        citations = self._extract_citations(
            retrieval_result.chunks,
            retrieval_result.scores
        )
        
        # Enforce mandatory citations
        if self.config.require_citations and not citations:
            logger.warning("No citations extracted but citations are required")
            return self._create_refusal_response(
                query,
                ConfidenceLevel.NONE
            )
        
        # Generate response with LLM (with retry logic)
        answer = None
        final_confidence = retrieval_result.confidence
        retry_count = 0
        
        while retry_count <= self.max_retries:
            try:
                # Generate response
                raw_answer = await self._call_llm(context, query)
                
                # Handle token truncation
                raw_answer = self._handle_token_truncation(raw_answer)
                
                # Clean response
                answer = self._clean_response(raw_answer)
                
                # === SECURITY FILTER ===
                security_check = self._security_filter.check(answer)
                if not security_check.is_safe:
                    logger.error(f"Security filter blocked response: {security_check.alert_message}")
                    if security_check.redacted_text:
                        answer = security_check.redacted_text
                    else:
                        # If too dangerous, refuse
                        return self._create_refusal_response(
                            query,
                            ConfidenceLevel.NONE
                        )
                
                # === INTEGRITY VALIDATION ===
                integrity_check = self._integrity_validator.validate(
                    answer,
                    require_citations=self.config.require_citations,
                    citations=citations,
                )
                
                if not integrity_check.is_valid:
                    logger.warning(
                        f"Integrity check failed (attempt {retry_count + 1}): "
                        f"{integrity_check.issues}"
                    )
                    
                    # Use normalized text if available
                    if integrity_check.normalized_text:
                        answer = integrity_check.normalized_text
                    
                    # If critical issues, retry
                    critical_issues = {
                        'truncated_sentence', 'truncated_paragraph',
                        'merged_words', 'broken_spacing'
                    }
                    if any(issue.value in critical_issues for issue in integrity_check.issues):
                        if retry_count < self.max_retries:
                            retry_count += 1
                            logger.info(f"Retrying generation (attempt {retry_count + 1})...")
                            continue
                        else:
                            # Max retries reached, use fallback
                            logger.error("Max retries reached, using fallback")
                            break
                
                # === GROUNDING FIREWALL ===
                is_allowed, refusal_msg = self._grounding_firewall.enforce_grounding(
                    answer,
                    retrieval_result,
                )
                
                if not is_allowed:
                    logger.warning(f"Grounding check failed: {refusal_msg}")
                    if retry_count < self.max_retries:
                        retry_count += 1
                        logger.info(f"Retrying generation (attempt {retry_count + 1})...")
                        continue
                    else:
                        # Return refusal
                        return QueryResult(
                            query=query,
                            answer=refusal_msg or self.config.refusal_message,
                            confidence=ConfidenceLevel.NONE,
                            confidence_score=0.0,
                            citations=[],
                            is_grounded=True,
                            is_refusal=True,
                            needs_clarification=False,
                            retrieval_result=retrieval_result,
                            processing_time_ms=(time.time() - start_time) * 1000,
                        )
                
                # All checks passed
                break
                
            except Exception as e:
                logger.error(f"LLM generation failed (attempt {retry_count + 1}): {e}")
                if retry_count < self.max_retries:
                    retry_count += 1
                    continue
                else:
                    # Fall back to showing retrieved content directly
                    if retrieval_result.chunks:
                        chunk = retrieval_result.chunks[0]
                        if chunk.original_answer:
                            answer = chunk.original_answer
                        else:
                            answer = chunk.content
                        final_confidence = retrieval_result.confidence
                    else:
                        return self._create_refusal_response(query, ConfidenceLevel.NONE)
                    break
        
        # If we still don't have an answer, refuse
        if not answer:
            return self._create_refusal_response(query, ConfidenceLevel.NONE)
        
        # Final integrity check on the answer
        final_integrity = self._integrity_validator.validate(
            answer,
            require_citations=self.config.require_citations,
            citations=citations,
        )
        
        # Use normalized text if available
        if final_integrity.normalized_text:
            answer = final_integrity.normalized_text
        
        # Check if the LLM admitted it doesn't have information
        refusal_indicators = [
            "i don't have",
            "not found in",
            "no information",
            "not mentioned",
            "not available",
            "cannot find",
            "the context doesn't",
            "not in the context",
        ]
        
        is_implicit_refusal = any(
            indicator in answer.lower() for indicator in refusal_indicators
        )
        
        # Adjust confidence if LLM couldn't answer
        if is_implicit_refusal and final_confidence == ConfidenceLevel.HIGH:
            final_confidence = ConfidenceLevel.MEDIUM
        
        # Calculate confidence score
        confidence_score = retrieval_result.top_score
        
        elapsed_ms = (time.time() - start_time) * 1000
        
        return QueryResult(
            query=query,
            answer=answer,
            confidence=final_confidence,
            confidence_score=confidence_score,
            citations=citations if (self.config.enable_citations and citations) else [],
            is_grounded=True,
            is_refusal=False,
            needs_clarification=False,
            retrieval_result=retrieval_result,
            processing_time_ms=elapsed_ms + retrieval_result.retrieval_time_ms,
        )
