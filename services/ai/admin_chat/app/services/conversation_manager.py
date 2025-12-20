"""
Conversation history and context management
"""
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import json
from collections import defaultdict


class ConversationManager:
    """Manages conversation history and context for intelligent responses"""
    
    def __init__(self, max_history: int = 10, ttl_hours: int = 24):
        """
        Args:
            max_history: Maximum number of messages to keep in history
            ttl_hours: Time to live for conversations in hours
        """
        self.max_history = max_history
        self.ttl = timedelta(hours=ttl_hours)
        self._conversations: Dict[str, List[Dict]] = defaultdict(list)
        self._timestamps: Dict[str, datetime] = {}
        self._branch_context: Dict[str, Dict] = {}  # branch_id -> context info
    
    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        branch_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ):
        """Add a message to conversation history"""
        # Clean old conversations
        self._cleanup_old_conversations()
        
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        
        if branch_id:
            message["metadata"]["branch_id"] = branch_id
        
        self._conversations[session_id].append(message)
        self._timestamps[session_id] = datetime.now()
        
        # Limit history size
        if len(self._conversations[session_id]) > self.max_history * 2:
            # Keep system messages and recent messages
            recent = self._conversations[session_id][-self.max_history:]
            self._conversations[session_id] = recent
    
    def get_messages(
        self,
        session_id: str,
        include_system: bool = True,
        max_messages: Optional[int] = None
    ) -> List[Dict[str, str]]:
        """Get conversation messages formatted for LLM"""
        if session_id not in self._conversations:
            return []
        
        messages = self._conversations[session_id].copy()
        
        # Filter by max_messages if specified
        if max_messages:
            messages = messages[-max_messages:]
        
        # Format for LLM
        formatted = []
        for msg in messages:
            formatted.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        return formatted
    
    def get_branch_context(self, branch_id: str) -> Dict:
        """Get branch-specific context"""
        return self._branch_context.get(branch_id, {})
    
    def set_branch_context(self, branch_id: str, context: Dict):
        """Set branch-specific context (modes of operation, policies, etc.)"""
        self._branch_context[branch_id] = context
    
    def get_conversation_summary(self, session_id: str) -> str:
        """Generate a comprehensive summary of the conversation for context awareness"""
        if session_id not in self._conversations:
            return ""
        
        messages = self._conversations[session_id]
        if len(messages) < 2:
            return ""
        
        # Get recent conversation (last 6 messages for better context)
        recent_messages = messages[-6:]
        
        # Extract key information
        user_queries = [msg["content"] for msg in recent_messages if msg["role"] == "user"]
        assistant_responses = [msg["content"] for msg in recent_messages if msg["role"] == "assistant"]
        
        # Detect branch from conversation history
        branch_mentioned = None
        for msg in recent_messages:
            branch = msg.get("metadata", {}).get("branch_id")
            if branch:
                branch_mentioned = branch
                break
        
        # Build comprehensive summary
        summary_parts = []
        
        if branch_mentioned:
            summary_parts.append(f"Current conversation is about the {branch_mentioned.upper()} branch.")
        
        if len(user_queries) > 1:
            summary_parts.append(f"Previous questions: {'; '.join(user_queries[:-1][-2:])}")
            summary_parts.append(f"Current question: {user_queries[-1]}")
        elif user_queries:
            summary_parts.append(f"User is asking: {user_queries[0]}")
        
        # Detect if this is a follow-up question
        if len(user_queries) > 1:
            current_query = user_queries[-1].lower()
            follow_up_indicators = ["continue", "more", "also", "and", "what about", "how about", "tell me more", "what else"]
            if any(indicator in current_query for indicator in follow_up_indicators) or len(current_query.split()) < 5:
                summary_parts.append("This appears to be a follow-up question. Use the previous conversation context to provide a complete answer.")
        
        return " ".join(summary_parts) if summary_parts else ""
    
    def clear_conversation(self, session_id: str):
        """Clear conversation history for a session"""
        if session_id in self._conversations:
            del self._conversations[session_id]
        if session_id in self._timestamps:
            del self._timestamps[session_id]
    
    def _cleanup_old_conversations(self):
        """Remove conversations older than TTL"""
        now = datetime.now()
        expired = [
            session_id for session_id, timestamp in self._timestamps.items()
            if now - timestamp > self.ttl
        ]
        for session_id in expired:
            self.clear_conversation(session_id)
    
    def get_context_for_llm(
        self,
        session_id: str,
        branch_id: Optional[str] = None,
        rag_context: Optional[str] = None,
        current_query: Optional[str] = None
    ) -> str:
        """Build comprehensive context string for LLM with strict branch filtering and conversation awareness"""
        context_parts = []
        
        # Add branch-specific context FIRST and prominently
        if branch_id:
            branch_ctx = self.get_branch_context(branch_id)
            if branch_ctx:
                context_parts.append(f"=== BRANCH: {branch_id.upper()} ===\nBranch Information: {json.dumps(branch_ctx, indent=2)}\n")
        
        # Add RAG context with branch label
        if rag_context:
            if branch_id:
                context_parts.append(f"=== KNOWLEDGE BASE FOR {branch_id.upper()} BRANCH ===\n{rag_context}\n=== END OF {branch_id.upper()} KNOWLEDGE BASE ===")
            else:
                context_parts.append(f"=== KNOWLEDGE BASE ===\n{rag_context}\n=== END OF KNOWLEDGE BASE ===")
        
        # Add enhanced conversation summary for context awareness
        summary = self.get_conversation_summary(session_id)
        if summary:
            context_parts.append(f"=== CONVERSATION CONTEXT ===\n{summary}\n=== END OF CONVERSATION CONTEXT ===")
        
        # Add recent conversation history for better context understanding (last 2 exchanges)
        if session_id in self._conversations and len(self._conversations[session_id]) > 2:
            recent = self._conversations[session_id][-4:]  # Last 2 user-assistant exchanges
            if recent:
                context_parts.append("=== RECENT CONVERSATION HISTORY ===\n")
                for msg in recent:
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")[:200]  # Limit length
                    if role == "user":
                        context_parts.append(f"User: {content}")
                    elif role == "assistant":
                        context_parts.append(f"Assistant: {content}")
                context_parts.append("=== END OF CONVERSATION HISTORY ===\n")
        
        return "\n\n".join(context_parts) if context_parts else None


# Global conversation manager instance
conversation_manager = ConversationManager()

