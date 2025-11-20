"""
Branch detection and identification service
"""
import re
from typing import Optional
from app.services.branch_config import BRANCH_CONFIGS


class BranchDetector:
    """Detect branch from user query or session"""
    
    # Branch keywords and patterns
    BRANCH_KEYWORDS = {
        "kano": ["kano", "kschma"],
        "kogi": ["kogi", "kgshia"],
        "kaduna": ["kaduna", "kadchma"],
        "fct": ["fct", "federal capital territory", "abuja", "fhis"],
        "adamawa": ["adamawa", "aschma"],
        "zamfara": ["zamfara", "zamchema"],
        "sokoto": ["sokoto", "sohema"],
        "rivers": ["rivers", "rivchpp", "port harcourt"],
        "osun": ["osun", "oshia"]
    }
    
    @classmethod
    def detect_from_query(cls, query: str) -> Optional[str]:
        """
        Detect branch ID from user query text
        
        Args:
            query: User query string
            
        Returns:
            Branch ID if detected, None otherwise
        """
        query_lower = query.lower()
        
        # Check for branch keywords
        for branch_id, keywords in cls.BRANCH_KEYWORDS.items():
            for keyword in keywords:
                if keyword in query_lower:
                    return branch_id
        
        # Check for abbreviations in parentheses (e.g., "KSCHMA", "KGSHIA")
        abbrev_pattern = r'\b(KSCHMA|KGSHIA|KADCHMA|FHIS|ASCHMA|ZAMCHEMA|SOHEMA|RIVCHPP|OSHIA)\b'
        match = re.search(abbrev_pattern, query, re.IGNORECASE)
        if match:
            abbrev_map = {
                "KSCHMA": "kano",
                "KGSHIA": "kogi",
                "KADCHMA": "kaduna",
                "FHIS": "fct",
                "ASCHMA": "adamawa",
                "ZAMCHEMA": "zamfara",
                "SOHEMA": "sokoto",
                "RIVCHPP": "rivers",
                "OSHIA": "osun"
            }
            return abbrev_map.get(match.group(1).upper())
        
        return None
    
    @classmethod
    def get_branch_from_session(cls, session_id: str, conversation_manager) -> Optional[str]:
        """
        Get branch ID from conversation history
        
        Args:
            session_id: Session ID
            conversation_manager: Conversation manager instance
            
        Returns:
            Branch ID if found in history, None otherwise
        """
        messages = conversation_manager.get_messages(session_id, max_messages=10)
        
        # Check recent messages for branch mentions
        for msg in reversed(messages):  # Check most recent first
            if msg["role"] == "user":
                branch_id = cls.detect_from_query(msg["content"])
                if branch_id:
                    return branch_id
        
        # Check metadata in conversation
        if session_id in conversation_manager._conversations:
            for msg in conversation_manager._conversations[session_id]:
                branch_id = msg.get("metadata", {}).get("branch_id")
                if branch_id:
                    return branch_id
        
        return None
    
    @classmethod
    def smart_detect(
        cls,
        query: str,
        session_id: str,
        explicit_branch_id: Optional[str],
        conversation_manager
    ) -> Optional[str]:
        """
        Smart branch detection with priority:
        1. Explicit branch_id from request (highest priority)
        2. Branch mentioned in current query
        3. Branch from conversation history
        
        Args:
            query: Current user query
            session_id: Session ID
            explicit_branch_id: Branch ID explicitly provided in request
            conversation_manager: Conversation manager instance
            
        Returns:
            Detected branch ID
        """
        # Priority 1: Explicit branch_id (user specified)
        if explicit_branch_id:
            return explicit_branch_id
        
        # Priority 2: Detect from current query
        branch_from_query = cls.detect_from_query(query)
        if branch_from_query:
            return branch_from_query
        
        # Priority 3: Get from conversation history
        branch_from_history = cls.get_branch_from_session(session_id, conversation_manager)
        if branch_from_history:
            return branch_from_history
        
        return None

