"""
Async LLM client supporting both Ollama and OpenAI-compatible APIs (Groq, OpenAI, etc.).

The rest of the service expects:
- `get_ollama_client()` returning a singleton
- `.chat(messages, context=..., branch_id=...)` for non-streaming responses

This implementation supports:
- Ollama API (`/api/chat`)
- OpenAI-compatible APIs (Groq, OpenAI) (`/v1/chat/completions`)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import httpx

from app.core.config import settings


@dataclass
class OllamaClient:
    base_url: str
    model: str
    api_key: Optional[str] = None
    timeout_seconds: int = 120
    temperature: float = 0.2

    def _is_openai_compatible(self) -> bool:
        """Check if this is an OpenAI-compatible API (Groq, OpenAI, etc.)"""
        return self.api_key is not None or "openai" in self.base_url.lower() or "groq" in self.base_url.lower()

    async def chat(
        self,
        *,
        messages: list[dict[str, str]],
        context: Optional[str] = None,
        branch_id: Optional[str] = None,
        kb_id: Optional[str] = None,
        options: Optional[dict[str, Any]] = None,
    ) -> str:
        """
        Generate an assistant response.

        Args:
            messages: Chat message list. Each: {"role": "user|assistant|system", "content": "..."}
            context: Optional extra context injected as a system message.
            branch_id/kb_id: Optional scope tags (useful for debugging/telemetry).
            options: Options override (temperature, etc.).
        """
        final_messages = []
        if context:
            scope = ""
            if kb_id:
                scope = f" KB={kb_id}"
            elif branch_id:
                scope = f" BRANCH={branch_id}"
            
            # Enhanced system prompt with balanced instructions
            system_prompt = f"""{context}

RESPONSE GUIDELINES:

1. ANSWER CONFIDENTLY using the information provided in the knowledge base above. The knowledge base contains comprehensive clinical information - use it directly and naturally.

2. DO NOT include in your response:
   - Source citations, references, or attributions
   - Document names, file paths, or page numbers
   - Phrases like "according to the knowledge base" or "the document states"
   - Technical metadata or formatting markers

3. WRITE AS A KNOWLEDGEABLE CLINICAL EXPERT providing direct, helpful answers. Be confident when information is available.

4. ONLY say you don't have information if the knowledge base truly lacks relevant content about the question.

5. For clinical questions, provide clear, actionable answers. Be helpful and direct.

6. DO NOT make up information, but DO confidently use the information that IS available.

Remember: You have access to comprehensive clinical information. Use it confidently to help the user.

(Internal scope:{scope.strip() or 'none'})"""
            
            final_messages.append(
                {
                    "role": "system",
                    "content": system_prompt,
                }
            )
        final_messages.extend(messages)

        # Determine API format
        is_openai = self._is_openai_compatible()
        
        if is_openai:
            # OpenAI/Groq format
            payload: dict[str, Any] = {
                "model": self.model,
                "messages": final_messages,
                "temperature": options.get("temperature", self.temperature) if options else self.temperature,
                "stream": False,
            }
            # Handle base URL - if it already ends with /v1, don't add it again
            base = self.base_url.rstrip('/')
            if base.endswith('/v1'):
                endpoint = f"{base}/chat/completions"
            else:
                endpoint = f"{base}/v1/chat/completions"
            headers = {
                "Content-Type": "application/json",
            }
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
        else:
            # Ollama format
            payload: dict[str, Any] = {
                "model": self.model,
                "messages": final_messages,
                "stream": False,
                "options": {
                    "temperature": options.get("temperature", self.temperature) if options else self.temperature,
                    **(options or {}),
                },
            }
            endpoint = f"{self.base_url.rstrip('/')}/api/chat"
            headers = {"Content-Type": "application/json"}

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.post(endpoint, json=payload, headers=headers)
            if resp.status_code != 200:
                # Try to get error details from Groq
                try:
                    error_data = resp.json()
                    error_msg = error_data.get("error", {}).get("message", resp.text[:500])
                    error_type = error_data.get("error", {}).get("type", "unknown")
                except:
                    error_msg = resp.text[:500]
                    error_type = "unknown"
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Groq API error {resp.status_code}: {error_type} - {error_msg}")
                logger.error(f"Payload size: {len(str(payload))} chars, Messages: {len(final_messages)}")
                raise Exception(f"Client error '{resp.status_code} {resp.reason_phrase}' for url '{endpoint}'\nError type: {error_type}\nError details: {error_msg}")
            resp.raise_for_status()
            data = resp.json()

        # Parse response based on API type
        if is_openai:
            # OpenAI/Groq returns: {"choices": [{"message": {"content": "..."}}]}
            choices = data.get("choices", [])
            if choices:
                return (choices[0].get("message", {}).get("content") or "").strip()
            return ""
        else:
            # Ollama returns: {"message": {"role":"assistant","content":"..."}, ...}
            msg = (data or {}).get("message") or {}
            return (msg.get("content") or "").strip()


_singleton: Optional[OllamaClient] = None


async def get_ollama_client() -> OllamaClient:
    """Return a process-wide singleton client (async for compatibility with callers)."""
    global _singleton
    if _singleton is None:
        _singleton = OllamaClient(
            base_url=settings.LLM_API_URL,
            model=settings.LLM_MODEL,
            api_key=getattr(settings, "LLM_API_KEY", None),
            timeout_seconds=settings.LLM_TIMEOUT_SECONDS,
            temperature=settings.TEMPERATURE,
        )
    return _singleton


