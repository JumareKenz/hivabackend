"""
Chat Handler Service
Handles general conversation queries (non-data requests)
"""
from typing import Dict, Any
from app.services.llm_client import llm_client
from app.services.intent_router import intent_router


class ChatHandler:
    """
    Handles general conversation and non-data queries
    Uses standard LLM without MCP tools
    """
    
    async def handle_chat(
        self,
        user_query: str,
        session_id: str = None,
        conversation_history: list = None
    ) -> Dict[str, Any]:
        """
        Handle general conversation query
        
        Args:
            user_query: User's input
            session_id: Optional session ID
            conversation_history: Optional conversation history
        
        Returns:
            Response dictionary
        """
        try:
            # Build prompt with system message and conversation context
            system_prompt = intent_router.get_chat_prompt()
            
            # Build conversation context
            messages = []
            
            # Add system prompt
            messages.append({
                "role": "system",
                "content": system_prompt
            })
            
            # Add conversation history if available
            if conversation_history:
                for msg in conversation_history[-5:]:  # Last 5 messages
                    messages.append({
                        "role": msg.get("role", "user"),
                        "content": msg.get("content", "")
                    })
            
            # Add current user query
            messages.append({
                "role": "user",
                "content": user_query
            })
            
            # Format messages for LLM
            prompt_text = self._format_messages(messages)
            
            # Generate response
            response = await llm_client.generate(
                prompt=prompt_text,
                temperature=0.7,  # Slightly higher for natural conversation
                max_tokens=500
            )
            
            return {
                "success": True,
                "response": response.strip(),
                "intent": "CHAT",
                "mode": "chat"
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "intent": "CHAT",
                "mode": "chat",
                "response": "I apologize, but I'm having trouble processing your request. Please try again or ask me about data queries."
            }
    
    def _format_messages(self, messages: list) -> str:
        """Format messages for LLM prompt"""
        formatted = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                formatted.append(f"System: {content}")
            elif role == "user":
                formatted.append(f"User: {content}")
            elif role == "assistant":
                formatted.append(f"Assistant: {content}")
        
        return "\n\n".join(formatted)


# Global instance
chat_handler = ChatHandler()

