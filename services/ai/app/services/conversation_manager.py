"""
Conversation history and context management
"""
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
import json
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


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
        self._kb_context: Dict[str, Dict] = {}  # kb_id -> context info (states/providers KBs)
    
    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        branch_id: Optional[str] = None,
        kb_id: Optional[str] = None,
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
        if kb_id:
            message["metadata"]["kb_id"] = kb_id
        
        self._conversations[session_id].append(message)
        self._timestamps[session_id] = datetime.now()
        
        # Limit history size
        if len(self._conversations[session_id]) > self.max_history * 2:
            # Keep system messages and recent messages
            recent = self._conversations[session_id][-self.max_history:]
            self._conversations[session_id] = recent
    
    def get_last_query_results(
        self,
        session_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get the last query's SQL and results from conversation history.
        Used for narrative analysis of follow-up questions.
        
        Returns:
            Dict with:
                - sql: str
                - results: List[Dict]
                - query: str (original user query)
                - analytical_summary: str
                - row_count: int
            or None if no previous query found
        """
        if session_id not in self._conversations:
            logger.debug(f"No conversation history for session: {session_id}")
            return None
        
        # Find last assistant message with query results
        # Look through messages in reverse order
        for msg in reversed(self._conversations[session_id]):
            if msg.get("role") == "assistant":
                metadata = msg.get("metadata", {})
                
                # Check if this message has SQL and results
                sql = metadata.get("sql")
                results = metadata.get("results")
                
                # Also check if results might be in data field (backward compatibility)
                if not results and metadata.get("data"):
                    results = metadata.get("data")
                
                if sql and results:
                    query = metadata.get("query", "")
                    analytical_summary = metadata.get("analytical_summary", "")
                    row_count = metadata.get("row_count", len(results) if isinstance(results, list) else 0)
                    
                    logger.debug(f"Found previous query results for session {session_id}: {len(results) if isinstance(results, list) else 0} rows")
                    
                    return {
                        "sql": sql,
                        "results": results if isinstance(results, list) else [],
                        "query": query,
                        "analytical_summary": analytical_summary,
                        "row_count": row_count
                    }
        
        logger.debug(f"No previous query results found for session: {session_id}")
        return None
    
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
        
        # Format for LLM - include metadata for follow-up handling
        formatted = []
        for msg in messages:
            formatted_msg = {
                "role": msg["role"],
                "content": msg["content"]
            }
            # Include metadata if available (for follow-up queries)
            if msg.get("metadata"):
                formatted_msg["metadata"] = msg["metadata"]
            formatted.append(formatted_msg)
        
        return formatted
    
    def get_branch_context(self, branch_id: str) -> Dict:
        """Get branch-specific context"""
        return self._branch_context.get(branch_id, {})
    
    def set_branch_context(self, branch_id: str, context: Dict):
        """Set branch-specific context (modes of operation, policies, etc.)"""
        self._branch_context[branch_id] = context

    def get_kb_context(self, kb_id: str) -> Dict:
        """Get KB-specific context (states/providers RAG)."""
        return self._kb_context.get(kb_id, {})

    def set_kb_context(self, kb_id: str, context: Dict):
        """Set KB-specific context (states/providers KB metadata, policies, etc.)."""
        self._kb_context[kb_id] = context
    
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
        kb_mentioned = None
        for msg in recent_messages:
            branch = msg.get("metadata", {}).get("branch_id")
            if branch:
                branch_mentioned = branch
                break
            kb = msg.get("metadata", {}).get("kb_id")
            if kb:
                kb_mentioned = kb
                break
        
        # Build comprehensive summary
        summary_parts = []
        
        if branch_mentioned:
            summary_parts.append(f"Current conversation is about the {branch_mentioned.upper()} branch.")
        if kb_mentioned:
            summary_parts.append(f"Current conversation is using the {kb_mentioned.upper()} knowledge base.")
        
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
    
    def reformulate_query(self, session_id: str, current_query: str) -> str:
        """
        Reformulate a query using conversation context for better retrieval.
        
        This is particularly useful for follow-up questions that reference
        previous conversation (e.g., "What about that?", "Tell me more").
        
        Args:
            session_id: Session identifier
            current_query: Current user query
            
        Returns:
            Reformulated query with context, or original query if no context
        """
        if session_id not in self._conversations or len(self._conversations[session_id]) < 2:
            return current_query
        
        # Check if this looks like a follow-up question
        follow_up_indicators = [
            "what about", "how about", "tell me more", "what else",
            "also", "and", "continue", "more", "that", "this", "it"
        ]
        
        query_lower = current_query.lower()
        is_follow_up = any(indicator in query_lower for indicator in follow_up_indicators) or len(current_query.split()) < 5
        
        if not is_follow_up:
            return current_query
        
        # Get recent conversation to add context
        recent_messages = self._conversations[session_id][-4:]
        context_parts = []
        
        for msg in recent_messages:
            if msg.get("role") == "user":
                prev_query = msg.get("content", "")
                if prev_query and prev_query != current_query:
                    context_parts.append(f"Previous question: {prev_query}")
            elif msg.get("role") == "assistant":
                prev_answer = msg.get("content", "")[:150]  # Truncate
                if prev_answer:
                    context_parts.append(f"Previous answer context: {prev_answer}...")
        
        if context_parts:
            # Reformulate query with context
            context_str = " | ".join(context_parts)
            reformulated = f"{current_query} (Context: {context_str})"
            logger.debug(f"Query reformulated: '{current_query}' -> '{reformulated[:100]}...'")
            return reformulated
        
        return current_query

    def get_context_for_llm(
        self,
        session_id: str,
        branch_id: Optional[str] = None,
        rag_context: Optional[str] = None,
        kb_id: Optional[str] = None,
        current_query: Optional[str] = None
    ) -> str:
        """
        Build comprehensive context string for LLM with strict filtering and conversation awareness.
        
        This method intelligently combines:
        - KB/Branch-specific context
        - Retrieved RAG context
        - Conversation history
        - Conversation summary
        
        Args:
            session_id: Session identifier
            branch_id: Optional branch identifier
            rag_context: Retrieved context from vector store
            kb_id: Optional knowledge base identifier
            current_query: Current user query (for context-aware formatting)
            
        Returns:
            Formatted context string for LLM, or None if no context
        """
        context_parts = []
        
        # Add branch-specific context FIRST and prominently
        if branch_id:
            branch_ctx = self.get_branch_context(branch_id)
            if branch_ctx:
                context_parts.append(f"=== BRANCH: {branch_id.upper()} ===\nBranch Information: {json.dumps(branch_ctx, indent=2)}\n")

        # Add KB-specific context (states/providers)
        if kb_id:
            kb_ctx = self.get_kb_context(kb_id)
            if kb_ctx:
                context_parts.append(f"=== KNOWLEDGE BASE: {kb_id.upper()} ===\nKB Information: {json.dumps(kb_ctx, indent=2)}\n")
        
        # Add RAG context with branch label and STRICT instructions
        if rag_context:
            anti_hallucination_instruction = """
CRITICAL RESPONSE GUIDELINES:

1. BE POLITE, FRIENDLY, AND CONVERSATIONAL:
   - Use warm, welcoming language
   - Be helpful and empathetic
   - Use phrases like "I'd be happy to help", "Let me assist you with that", "I'm here to help"
   - Maintain a professional yet friendly tone throughout

2. ANSWER CONFIDENTLY when information is in the knowledge base below. Use the information directly and naturally.

3. DO NOT include in your response:
   - Source citations, references, or attributions (e.g., "According to...", "The document states...", "As mentioned in...")
   - File names, document titles, or page numbers
   - Technical metadata or markers
   - Phrases like "based on the knowledge base" or "according to the documents"
   - Brackets, parentheses, or special formatting indicating sources
   - Lists of references or citations

4. WRITE NATURALLY as if you are a knowledgeable, friendly assistant providing information directly.

5. ONLY say "I don't have that information" if the knowledge base truly does not contain relevant information about the question. When you don't have information, politely suggest contacting the Agency directly.

6. For questions, provide clear, direct answers using the information from the knowledge base. Be confident and helpful.

7. DO NOT make up information, but DO use the information that IS available confidently.

8. HANDLE SPECIAL QUERIES:
   - Greetings (hi, hello, hey, yo): Respond warmly and explain what information you can help with
   - Thank you: Acknowledge graciously and offer further assistance
   - Please/Help: Be extra helpful and supportive
   - Satisfaction check: If user says "no" or "not satisfied", ask how you can help better

YOUR RESPONSE STYLE:
- Polite, friendly, and conversational
- Warm and welcoming
- Direct, confident, and helpful
- Natural conversational tone
- No citations or references
- Focus on answering the user's question clearly
"""
            
            if kb_id:
                context_parts.append(f"{anti_hallucination_instruction}\n=== KNOWLEDGE BASE FOR {kb_id.upper()} ===\n{rag_context}\n=== END OF {kb_id.upper()} KNOWLEDGE BASE ===")
            elif branch_id:
                context_parts.append(f"{anti_hallucination_instruction}\n=== KNOWLEDGE BASE FOR {branch_id.upper()} BRANCH ===\n{rag_context}\n=== END OF {branch_id.upper()} KNOWLEDGE BASE ===")
            else:
                context_parts.append(f"{anti_hallucination_instruction}\n=== KNOWLEDGE BASE ===\n{rag_context}\n=== END OF KNOWLEDGE BASE ===")
        
        # Add enhanced conversation summary for context awareness
        summary = self.get_conversation_summary(session_id)
        if summary:
            context_parts.append(f"=== CONVERSATION CONTEXT ===\n{summary}\n=== END OF CONVERSATION CONTEXT ===")
        
        # Add recent conversation history for better context understanding (last 2 exchanges)
        # Intelligently truncate to avoid token limits
        if session_id in self._conversations and len(self._conversations[session_id]) > 2:
            recent = self._conversations[session_id][-4:]  # Last 2 user-assistant exchanges
            if recent:
                context_parts.append("=== RECENT CONVERSATION HISTORY ===\n")
                for msg in recent:
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")
                    
                    # Smart truncation: preserve important parts
                    if len(content) > 300:
                        # Try to keep the beginning and end
                        truncated = content[:200] + "... [truncated] ..." + content[-50:]
                    else:
                        truncated = content
                    
                    if role == "user":
                        context_parts.append(f"User: {truncated}")
                    elif role == "assistant":
                        context_parts.append(f"Assistant: {truncated}")
                context_parts.append("=== END OF CONVERSATION HISTORY ===\n")
        
        # Add instruction for handling follow-ups
        if current_query and session_id in self._conversations:
            if len(self._conversations[session_id]) > 2:
                context_parts.append(
                    "=== INSTRUCTIONS ===\n"
                    "This is part of an ongoing conversation. Use the conversation history "
                    "to provide context-aware responses. If the user's question is a follow-up, "
                    "reference the previous conversation naturally.\n"
                    "=== END OF INSTRUCTIONS ===\n"
                )
        
        return "\n\n".join(context_parts) if context_parts else None


# Global conversation manager instance
conversation_manager = ConversationManager()

