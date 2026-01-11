"""
Branch detection service.

Detects which branch/state a query is related to based on context.
"""

from __future__ import annotations

from typing import Optional
from app.services.conversation_manager import ConversationManager


class BranchDetector:
    """Detects branch/state from queries and conversation history."""
    
    @staticmethod
    def smart_detect(
        query: str,
        session_id: str,
        explicit_branch_id: Optional[str] = None,
        conversation_manager: Optional[ConversationManager] = None
    ) -> Optional[str]:
        """
        Detect branch ID from query or conversation history.
        
        Args:
            query: User query
            session_id: Session identifier
            explicit_branch_id: Explicitly provided branch ID (takes precedence)
            conversation_manager: Conversation manager instance
            
        Returns:
            Detected branch ID or None
        """
        # If explicitly provided, use it
        if explicit_branch_id:
            return explicit_branch_id
        
        # Check conversation history for branch context
        if conversation_manager:
            messages = conversation_manager.get_messages(session_id, max_messages=10)
            for msg in reversed(messages):
                branch_id = msg.get("metadata", {}).get("branch_id")
                if branch_id:
                    return branch_id
        
        # Simple keyword-based detection (can be enhanced with LLM)
        query_lower = query.lower()
        
        # State names
        state_keywords = {
            "adamawa": ["adamawa", "aschema"],
            "fct": ["fct", "abuja", "fhis"],
            "kano": ["kano", "kschema"],
            "zamfara": ["zamfara", "zamchema"],
            "kogi": ["kogi", "kgshia"],
            "osun": ["osun", "oshia"],
            "rivers": ["rivers", "rivchpp"],
            "sokoto": ["sokoto", "sohema"],
            "kaduna": ["kaduna", "kadchma"],
        }
        
        for state_id, keywords in state_keywords.items():
            if any(keyword in query_lower for keyword in keywords):
                return state_id
        
        # No branch detected
        return None


