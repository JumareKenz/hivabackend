"""
Optimized async Ollama client with streaming support
"""
import httpx
import json
from typing import AsyncIterator, Optional, List, Dict, Any
from app.core.config import settings


class AsyncOllamaClient:
    """High-performance async Ollama client with connection pooling"""
    
    def __init__(
        self,
        base_url: str = None,
        timeout: float = 300.0,
        max_connections: int = 100,
        max_keepalive_connections: int = 20
    ):
        self.base_url = base_url or str(settings.LLM_API_URL)
        self.timeout = httpx.Timeout(timeout, connect=10.0)
        self.limits = httpx.Limits(
            max_connections=max_connections,
            max_keepalive_connections=max_keepalive_connections
        )
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _ensure_client(self):
        """Ensure client is initialized"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                limits=self.limits,
                http2=True  # Enable HTTP/2 for better performance
            )
    
    async def close(self):
        """Close the HTTP client"""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("Client not initialized. Call _ensure_client() first.")
        return self._client
    
    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        model: str = None,
        options: Dict[str, Any] = None,
        context: Optional[str] = None,
        branch_id: Optional[str] = None
    ) -> AsyncIterator[str]:
        """
        Stream chat completions from Ollama
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model name (defaults to config)
            options: Generation options
            context: Additional context to prepend to system message
        """
        model = model or settings.LLM_MODEL
        
        # Prepare system message with context and branch info
        system_content = self._build_system_message(context, branch_id)
        if system_content and (not messages or messages[0].get("role") != "system"):
            messages = [{"role": "system", "content": system_content}] + messages
        
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {
                "num_predict": settings.DEFAULT_NUM_PREDICT,
                "temperature": 0.7,
                "top_p": 0.9,
                "repeat_penalty": 1.1,
                "num_thread": 4,  # Use 4 threads for faster inference
                "num_ctx": 2048,  # Smaller context = faster
                **(options or {})
            }
        }
        
        await self._ensure_client()
        async with self.client.stream(
            "POST",
            "/api/chat",
            json=payload,
            timeout=self.timeout
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if "message" in data:
                        content = data["message"].get("content", "")
                        if content:
                            yield content
                    elif "response" in data:
                        content = data.get("response", "")
                        if content:
                            yield content
                    elif "done" in data and data.get("done"):
                        break
                except json.JSONDecodeError:
                    continue
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: str = None,
        options: Dict[str, Any] = None,
        context: Optional[str] = None,
        branch_id: Optional[str] = None
    ) -> str:
        """Non-streaming chat completion"""
        full_response = ""
        async for chunk in self.stream_chat(messages, model, options, context, branch_id):
            full_response += chunk
        return full_response
    
    def _build_system_message(self, context: Optional[str] = None, branch_id: Optional[str] = None) -> str:
        """Build intelligent system message with friendly, helpful tone"""
        base_system = """You are HIVA (Hayok Intelligent Virtual Assistant), a friendly and helpful AI assistant for an insurance company.

YOUR PERSONALITY:
- Warm, polite, and genuinely helpful
- Professional yet conversational
- Empathetic and understanding
- Focused on solving user problems

CRITICAL RULES:
1. ONLY use information from the provided context below - never make up information
2. DO NOT mention sources, documents, FAQs, or where information comes from
3. DO NOT mix information from different branches
4. Answer naturally as if you know the information personally
5. If you don't have information, politely say: "I don't have that specific information, but I'd be happy to help you contact our support team who can assist you further."

YOUR APPROACH:
- Provide clear, helpful answers based on the context
- Be conversational and friendly - like talking to a helpful colleague
- For greetings (hello, hi, hey), respond warmly: "Hello! I'm HIVA, your helpful assistant. I'm here to help you with information about our health insurance schemes. What would you like to know?"
- For simple queries without context, be helpful and guide users: "I'd be happy to help! Could you tell me more about what you're looking for? For example, you might want to know about enrollment, coverage, contributions, or specific policies."
- After providing an answer, naturally ask: "Does this help? Is there anything else you'd like to know?" or "I hope that answers your question. Would you like more information on this?"
- Focus on being genuinely helpful and solving the user's needs
- Use simple, clear language that anyone can understand
- Show empathy, especially for claims or concerns

TONE EXAMPLES:
❌ BAD: "According to the Zamfara FAQs, enrollment is..."
✅ GOOD: "Enrollment is open to all residents. Here's how you can get started..."

❌ BAD: "Based on the knowledge base, the contribution rate is..."
✅ GOOD: "The contribution rate is typically 5% of your basic salary. This helps ensure affordable healthcare coverage for everyone."

❌ BAD: "The document states that..."
✅ GOOD: "Yes, enrollment is mandatory for all residents. This ensures everyone has access to quality healthcare."

REMEMBER:
- Never mention "FAQs", "documents", "knowledge base", "sources", or similar terms
- Answer as if you naturally know this information
- Be warm, friendly, and helpful
- Ask if the user needs more help after answering
"""
        if branch_id:
            base_system += f"\n\nYou are helping a customer from the {branch_id.upper()} branch. Use only information relevant to this branch.\n"
        
        if context:
            base_system += f"\n\n--- INFORMATION AVAILABLE TO YOU ---\n{context}\n--- END OF INFORMATION ---\n"
            base_system += "\n\nUse the information above to answer questions naturally and helpfully. Never mention where the information comes from - just provide it in a friendly, conversational way."
        else:
            base_system += "\n\nYou have general information available. For specific details, you can help connect users with support."
        
        return base_system


# Global client instance (will be initialized on startup)
_global_client: Optional[AsyncOllamaClient] = None


async def get_ollama_client() -> AsyncOllamaClient:
    """Get or create global Ollama client instance"""
    global _global_client
    if _global_client is None:
        _global_client = AsyncOllamaClient()
        await _global_client._ensure_client()
    return _global_client


async def close_ollama_client():
    """Close global Ollama client"""
    global _global_client
    if _global_client:
        await _global_client.close()
        _global_client = None

