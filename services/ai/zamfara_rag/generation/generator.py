"""
Answer generation module for Zamfara RAG system.
Generates grounded, citation-backed answers using LLM with:
- Strict grounding in retrieved content
- Inline citations
- Formal administrative tone
- Safe fallback responses
"""
from __future__ import annotations
import logging
import json
import re
from zamfara_rag.utils.text_integrity import normalize_text
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
try:
    import httpx
except ImportError:
    httpx = None
logger = logging.getLogger(__name__)
class ResponseTone(Enum):
    """Response tone options."""
    FORMAL = "formal"
    NEUTRAL = "neutral"
    HELPFUL = "helpful"
@dataclass
class GeneratedAnswer:
    """Represents a generated answer with metadata."""
    # Core response
    answer: str
    # Citations
    citations: List[str]
    sources_used: List[str]
    # Metadata
    confidence: float  # 0.0 to 1.0
    grounded: bool  # Whether answer is grounded in sources
    is_fallback: bool  # Whether this is a fallback response
    # Generation metadata
    model: str = ""
    tokens_used: int = 0
    generation_time_ms: float = 0.0
    # Verification (populated by hallucination guard)
    verification_passed: bool = True
    verification_notes: str = ""
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "answer": self.answer,
            "citations": self.citations,
            "sources_used": self.sources_used,
            "confidence": self.confidence,
            "grounded": self.grounded,
            "is_fallback": self.is_fallback,
            "verification_passed": self.verification_passed,
        }
class AnswerGenerator:
    """
    Generates grounded answers for the Zamfara RAG system.
    Features:
    - Strict grounding in retrieved content
    - Inline citation generation
    - Formal administrative tone
    - Safe fallback responses
    - Multiple LLM backend support
    """
    # System prompt for grounded generation
    SYSTEM_PROMPT = """You are a friendly and helpful FAQ assistant for Zamfara State Government documents and policies.
CRITICAL RULES:
1. Answer using the provided context from official Zamfara State documents
2. If the context contains relevant information (even if not a direct definition), use it to answer the question
3. Be flexible with phrasing - if the context discusses the topic, provide that information even if it's not in the exact form asked
4. NEVER invent or assume information not in the context
5. Be friendly, polite, kind, and conversational - like a helpful government representative
6. DO NOT include citations, references, document names, or section numbers in your response
7. Write naturally as if you're directly helping the person
8. Be warm and welcoming while maintaining professionalism
RESPONSE STYLE:
- Friendly and conversational
- Polite and kind
- Clear and helpful
- Use "I" and "you" to make it personal
- Use proper spacing between words - always include spaces
- Write naturally with normal sentence structure
- Bullet points for lists when appropriate
- If information isn't available, be empathetic and suggest contacting ZAMCHEMA directly
- Write as if you're a knowledgeable friend helping them understand government policies"""
    # User prompt template
    USER_PROMPT_TEMPLATE = """Based on the following official Zamfara State documents, answer the question in a friendly, helpful, and conversational way.
CONTEXT FROM OFFICIAL DOCUMENTS:
{context}
QUESTION: {question}
Instructions:
- Use information from the provided context to answer the question in a friendly, conversational manner
- If the context contains relevant information (even if not a direct answer), use it to provide a helpful response
- Be flexible - if the question asks "what is X?" and the context discusses X in detail, provide that information
- Write as if you're a friendly government representative helping them
- DO NOT include citations, document names, section numbers, or references in your response
- Use "I" and "you" to make it personal and conversational
- Be warm, polite, and kind
- If information isn't available, say something like "I'm sorry, but I don't have that information. I'd recommend reaching out to ZAMCHEMA directly for assistance."
- If a direct definition isn't available but the context discusses the topic, explain what information is available in a friendly way"""
    # Fallback response when no relevant content found
    FALLBACK_RESPONSE = (
        "I'm sorry, but I don't have that information in the documents I have access to. "
        "For this specific question, I'd recommend reaching out directly to the Zamfara State Contributory Healthcare Management Agency (ZAMCHEMA) for assistance. "
        "They'll be able to provide you with the most accurate and up-to-date information."
    )
    def __init__(
        self,
        llm_api_url: str = "http://localhost:11434",
        llm_model: str = "llama3:latest",
        llm_api_key: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 1024,
        timeout: int = 120,
    ):
        """
        Initialize the answer generator.
        Args:
            llm_api_url: URL for LLM API (Ollama, OpenAI, Groq, etc.)
            llm_model: Model name to use
            llm_api_key: API key for authenticated services
            temperature: Generation temperature (low for factual)
            max_tokens: Maximum tokens in response
            timeout: Request timeout in seconds
        """
        if httpx is None:
            raise ImportError("httpx is required. Install with: pip install httpx")
        self.llm_api_url = llm_api_url.rstrip("/")
        self.llm_model = llm_model
        self.llm_api_key = llm_api_key
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        # Determine API type
        self._api_type = self._detect_api_type()
        logger.info(f"AnswerGenerator initialized: {llm_model} via {self._api_type}")
    def _detect_api_type(self) -> str:
        """Detect the type of LLM API being used."""
        url_lower = self.llm_api_url.lower()
        if "localhost:11434" in url_lower or "ollama" in url_lower:
            return "ollama"
        elif "openai" in url_lower:
            return "openai"
        elif "groq" in url_lower:
            return "groq"
        elif "anthropic" in url_lower:
            return "anthropic"
        else:
            # Default to OpenAI-compatible
            return "openai"
    async def generate(
        self,
        query: str,
        retrieval_response,  # RetrievalResponse
        min_context_results: int = 1,
        tone: ResponseTone = ResponseTone.FORMAL,
    ) -> GeneratedAnswer:
        """
        Generate a grounded answer for the query.
        Args:
            query: User query
            retrieval_response: RetrievalResponse from retriever
            min_context_results: Minimum results required to generate
            tone: Desired response tone
        Returns:
            GeneratedAnswer with response and metadata
        """
        import time
        start_time = time.time()
        # Check if we have enough context
        if len(retrieval_response.results) < min_context_results:
            logger.info("Insufficient context for generation, returning fallback")
            return GeneratedAnswer(
                answer=self.FALLBACK_RESPONSE,
                citations=[],
                sources_used=[],
                confidence=0.0,
                grounded=False,
                is_fallback=True,
            )
        # Build context from retrieval results
        context = retrieval_response.get_context(max_results=5)
        citations = retrieval_response.get_citations()
        sources = [r.document_title for r in retrieval_response.results[:5]]
        # Build prompt
        user_prompt = self.USER_PROMPT_TEMPLATE.format(
            context=context,
            question=query
        )
        # Generate response
        try:
            if self._api_type == "ollama":
                response_text = await self._generate_ollama(user_prompt)
            else:
                response_text = await self._generate_openai_compatible(user_prompt)
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            return GeneratedAnswer(
                answer=self.FALLBACK_RESPONSE,
                citations=[],
                sources_used=[],
                confidence=0.0,
                grounded=False,
                is_fallback=True,
            )
        elapsed = (time.time() - start_time) * 1000
        # Post-process response
        response_text = self._post_process(response_text)
        # Check if response indicates no information
        is_fallback = self._is_fallback_response(response_text)
        # Estimate confidence based on response characteristics
        confidence = self._estimate_confidence(response_text, citations)
        return GeneratedAnswer(
            answer=response_text,
            citations=citations,
            sources_used=list(set(sources)),
            confidence=confidence,
            grounded=not is_fallback,
            is_fallback=is_fallback,
            model=self.llm_model,
            generation_time_ms=elapsed,
        )
    async def _generate_ollama(self, prompt: str) -> str:
        """Generate using Ollama API."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.llm_api_url}/api/generate",
                json={
                    "model": self.llm_model,
                    "prompt": prompt,
                    "system": self.SYSTEM_PROMPT,
                    "stream": False,
                    "options": {
                        "temperature": self.temperature,
                        "num_predict": self.max_tokens,
                    }
                }
            )
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")
    async def _generate_openai_compatible(self, prompt: str) -> str:
        """Generate using OpenAI-compatible API."""
        headers = {"Content-Type": "application/json"}
        if self.llm_api_key:
            headers["Authorization"] = f"Bearer {self.llm_api_key}"
        # Handle URLs that already contain /v1
        base_url = self.llm_api_url.rstrip("/")
        if base_url.endswith("/v1"):
            endpoint = f"{base_url}/chat/completions"
        else:
            endpoint = f"{base_url}/v1/chat/completions"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                endpoint,
                headers=headers,
                json={
                    "model": self.llm_model,
                    "messages": [
                        {"role": "system", "content": self.SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens,
                }
            )
            response.raise_for_status()
            data = response.json()
            choices = data.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "")
            return ""
    def _post_process(self, text: str) -> str:
        """Post-process generated text using text integrity normalization."""
        if not text:
            return self.FALLBACK_RESPONSE
        
        # Use text integrity processor for normalization
        text = normalize_text(text)
        
        # Remove any preamble like "Based on the documents..."
        preamble_patterns = [
            r"^Based on the (?:provided |)(?:documents?|context)[,:]?\s*",
            r"^According to the (?:provided |)(?:documents?|context)[,:]?\s*",
            r"^From the (?:provided |)(?:documents?|context)[,:]?\s*",
        ]
        for pattern in preamble_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)
        
        # Remove citations and references (e.g., [Document Name], [Section X], etc.)
        citation_patterns = [
            r'\[[^\]]*Document[^\]]*\]',
            r'\[[^\]]*Section[^\]]*\]',
            r'\[[^\]]*,\s*Section[^\]]*\]',
            r'【[^】]*】',
            r'\([^)]*Citation[^)]*\)',
        ]
        for pattern in citation_patterns:
            text = re.sub(pattern, " ", text, flags=re.IGNORECASE | re.MULTILINE)
        
        # Final cleanup
        text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)  # Multiple newlines to double
        text = text.strip()
        
        return text

    def _is_fallback_response(self, text: str) -> bool:
        """Check if the response indicates no information was found."""
        fallback_indicators = [
            "not available",
            "not found",
            "no information",
            "cannot find",
            "does not contain",
            "not mentioned",
            "not specified",
            "not addressed",
            "beyond the scope",
            "outside the scope",
            "don't have that information",
            "don't have this information",
            "i don't have",
            "i'm sorry, but i don't",
            "i'm not in a position",
            "i don't know",
            "reach out to",
            "contact zamechema",
        ]
        text_lower = text.lower()
        return any(indicator in text_lower for indicator in fallback_indicators)
    def _estimate_confidence(
        self,
        response: str,
        citations: List[str]
    ) -> float:
        """
        Estimate confidence in the generated response.
        Higher confidence for:
        - Longer responses with substance
        - Responses with citations
        - Non-fallback responses
        """
        if not response or self._is_fallback_response(response):
            return 0.2
        confidence = 0.5  # Base confidence
        # Length bonus (more detailed = more confident)
        word_count = len(response.split())
        if word_count > 50:
            confidence += 0.1
        if word_count > 100:
            confidence += 0.1
        # Citation bonus
        citation_pattern = r"\[.+?\]"
        citation_count = len(re.findall(citation_pattern, response))
        if citation_count > 0:
            confidence += min(citation_count * 0.05, 0.2)
        # Structural bonus (lists, clear organization)
        if any(marker in response for marker in ["•", "-", "1.", "a)"]):
            confidence += 0.05
        return min(confidence, 1.0)
    def generate_sync(
        self,
        query: str,
        retrieval_response,
        **kwargs
    ) -> GeneratedAnswer:
        """Synchronous wrapper for generate()."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(
            self.generate(query, retrieval_response, **kwargs)
        )
