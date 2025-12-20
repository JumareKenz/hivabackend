"""
Intent Router - Classifies user queries into actionable intents
Uses ReAct pattern to determine the appropriate action
Enhanced with robust pattern matching and LLM fallback
"""
from typing import Dict, Any, Optional, List
from enum import Enum
import asyncio
import re
import logging

logger = logging.getLogger(__name__)


class IntentType(str, Enum):
    """Types of user intents"""
    GREETING = "greeting"
    DATA_QUERY = "data_query"  # New SQL query needed
    FOLLOW_UP_QUERY = "follow_up_query"  # Refinement of previous query
    NARRATIVE = "narrative"  # Analysis of existing results
    CLARIFICATION = "clarification"  # Need more info from user
    UNKNOWN = "unknown"


class IntentRouter:
    """
    Routes user queries to appropriate handlers based on intent classification.
    Implements ReAct (Reasoning + Acting) pattern with multi-layer detection.
    """
    
    def __init__(self):
        # Enhanced greeting patterns - more comprehensive
        self.greeting_patterns = [
            r'\b(hello|hi|hey|greetings|howdy|hola|salut)\b',
            r'\b(good\s+(morning|afternoon|evening|day|night))\b',
            r'^(hello|hi|hey)[\s!.,]*$',  # Standalone greetings
            r'^how\s+(are\s+you|do\s+you\s+do|is\s+it\s+going)[\s?.,]*$',
            r'^(what\'?s\s+up|sup|wassup)[\s?.,]*$',
            r'^(nice\s+to\s+meet\s+you|pleased\s+to\s+meet\s+you)[\s!.,]*$'
        ]
        
        # Follow-up patterns - queries that refine previous queries
        self.follow_up_patterns = [
            r'\b(tell\s+me\s+more|what\s+else|more\s+details|more\s+about)\b',
            r'\b(explain|elaborate|can\s+you\s+explain)\b',
            r'\b(what\s+about|how\s+about|also|and\s+then)\b',
            r'\b(continue|go\s+on|keep\s+going)\b',
            r'\b(breakdown|break\s+down|analyze|interpret)\b',
            r'\b(refine|adjust|modify|change)\b'
        ]
        
        # Narrative patterns - analysis of existing results (NO SQL)
        self.narrative_patterns = [
            r'\b(what\s+does\s+(this|that|it)\s+mean)\b',
            r'\b(explain\s+(this|that|it)|analyze\s+(this|that|it))\b',
            r'\b(interpret|summary|insights)\b',
            r'\b(what\s+can\s+you\s+tell\s+me|what\s+do\s+you\s+see)\b',
            r'\b(what\s+stands\s+out|what\'?s\s+interesting)\b',
            r'\b(so\s+what|what\s+does\s+this\s+show|what\s+does\s+this\s+tell\s+us)\b'
        ]
        
        # Clarification patterns
        self.clarification_patterns = [
            r'\b(what\s+do\s+you\s+mean|i\s+don\'?t\s+understand)\b',
            r'\b(can\s+you\s+clarify|what\s+are\s+you\s+asking)\b',
            r'\b(i\'?m\s+confused|unclear|not\s+sure)\b'
        ]
        
        # Data query indicators - words that suggest a data query
        self.data_query_indicators = [
            r'\b(show|display|list|find|get|fetch|retrieve|query)\b',
            r'\b(count|total|sum|average|compare|analyze)\b',
            r'\b(how\s+many|how\s+much|what\s+is\s+the|which)\b',
            r'\b(claims?|transactions?|users?|providers?|patients?)\b',
            r'\b(state|month|year|date|period|volume)\b'
        ]
    
    async def classify_intent(
        self,
        user_query: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        has_previous_results: bool = False
    ) -> Dict[str, Any]:
        """
        Classify user intent using multi-layer pattern matching and LLM reasoning.
        
        Args:
            user_query: The user's message
            conversation_history: Previous conversation messages
            has_previous_results: Whether there are results from a previous query
        
        Returns:
            Dict with:
                - intent: IntentType
                - confidence: float (0-1)
                - reasoning: str (explanation)
                - requires_sql: bool
                - requires_previous_data: bool
        """
        if not user_query or not user_query.strip():
            return {
                "intent": IntentType.CLARIFICATION,
                "confidence": 1.0,
                "reasoning": "Empty query",
                "requires_sql": False,
                "requires_previous_data": False
            }
        
        query_lower = user_query.lower().strip()
        query_words = query_lower.split()
        
        # Layer 1: Strong greeting detection (regex-based, high confidence)
        for pattern in self.greeting_patterns:
            if re.search(pattern, query_lower, re.IGNORECASE):
                # Additional check: if it's a standalone greeting (very short or just greeting)
                if len(query_words) <= 3 or re.match(r'^(hello|hi|hey)[\s!.,]*$', query_lower):
                    logger.info(f"Greeting detected: {user_query[:50]}")
                    return {
                        "intent": IntentType.GREETING,
                        "confidence": 0.98,
                        "reasoning": "Strong greeting pattern match",
                        "requires_sql": False,
                        "requires_previous_data": False
                    }
        
        # Layer 2: Narrative intent (requires previous results)
        if has_previous_results:
            # Check for narrative patterns
            for pattern in self.narrative_patterns:
                if re.search(pattern, query_lower, re.IGNORECASE):
                    logger.info(f"Narrative intent detected: {user_query[:50]}")
                    return {
                        "intent": IntentType.NARRATIVE,
                        "confidence": 0.92,
                        "reasoning": "Narrative pattern with previous results available",
                        "requires_sql": False,
                        "requires_previous_data": True
                    }
            
            # Short queries with previous results = likely narrative
            if len(query_words) <= 4:
                # Check if it contains data query indicators
                has_data_indicators = any(
                    re.search(indicator, query_lower, re.IGNORECASE) 
                    for indicator in self.data_query_indicators
                )
                
                if not has_data_indicators:
                    logger.info(f"Short narrative query detected: {user_query[:50]}")
                    return {
                        "intent": IntentType.NARRATIVE,
                        "confidence": 0.85,
                        "reasoning": "Short query without data indicators, with previous results",
                        "requires_sql": False,
                        "requires_previous_data": True
                    }
            
            # Follow-up patterns with previous results = narrative
            for pattern in self.follow_up_patterns:
                if re.search(pattern, query_lower, re.IGNORECASE):
                    logger.info(f"Follow-up narrative detected: {user_query[:50]}")
                    return {
                        "intent": IntentType.NARRATIVE,
                        "confidence": 0.88,
                        "reasoning": "Follow-up pattern with previous results available",
                        "requires_sql": False,
                        "requires_previous_data": True
                    }
        
        # Layer 3: Clarification patterns
        for pattern in self.clarification_patterns:
            if re.search(pattern, query_lower, re.IGNORECASE):
                logger.info(f"Clarification intent detected: {user_query[:50]}")
                return {
                    "intent": IntentType.CLARIFICATION,
                    "confidence": 0.9,
                    "reasoning": "Clarification pattern detected",
                    "requires_sql": False,
                    "requires_previous_data": False
                }
        
        # Layer 4: Follow-up query (refinement, needs SQL)
        if conversation_history and len(conversation_history) > 0:
            for pattern in self.follow_up_patterns:
                if re.search(pattern, query_lower, re.IGNORECASE):
                    # Check if it also has data query indicators (refinement)
                    has_data_indicators = any(
                        re.search(indicator, query_lower, re.IGNORECASE) 
                        for indicator in self.data_query_indicators
                    )
                    if has_data_indicators:
                        logger.info(f"Follow-up query detected: {user_query[:50]}")
                        return {
                            "intent": IntentType.FOLLOW_UP_QUERY,
                            "confidence": 0.85,
                            "reasoning": "Follow-up pattern with data indicators",
                            "requires_sql": True,
                            "requires_previous_data": False
                        }
        
        # Layer 5: LLM-based classification for ambiguous cases
        try:
            intent_result = await self._classify_with_llm(
                user_query, 
                conversation_history, 
                has_previous_results
            )
            if intent_result and intent_result.get("confidence", 0) > 0.75:
                logger.info(f"LLM classified intent: {intent_result.get('intent')} for: {user_query[:50]}")
                return intent_result
        except Exception as e:
            logger.warning(f"LLM intent classification failed: {e}")
        
        # Layer 6: Default - check for data query indicators
        has_data_indicators = any(
            re.search(indicator, query_lower, re.IGNORECASE) 
            for indicator in self.data_query_indicators
        )
        
        if has_data_indicators:
            logger.info(f"Data query detected (default): {user_query[:50]}")
            return {
                "intent": IntentType.DATA_QUERY,
                "confidence": 0.75,
                "reasoning": "Data query indicators found",
                "requires_sql": True,
                "requires_previous_data": False
            }
        
        # Final fallback: assume data query but with lower confidence
        logger.warning(f"Unclear intent, defaulting to DATA_QUERY: {user_query[:50]}")
        return {
            "intent": IntentType.DATA_QUERY,
            "confidence": 0.6,
            "reasoning": "Default classification - unclear intent",
            "requires_sql": True,
            "requires_previous_data": False
        }
    
    async def _classify_with_llm(
        self,
        user_query: str,
        conversation_history: Optional[List[Dict[str, Any]]],
        has_previous_results: bool
    ) -> Optional[Dict[str, Any]]:
        """Use LLM for more nuanced intent classification with improved prompt"""
        try:
            from app.services.ollama_client import get_ollama_client
            
            # Build context
            context_parts = []
            if has_previous_results:
                context_parts.append("The user has previous query results available in memory.")
            if conversation_history:
                recent_user_msgs = [
                    msg.get("content", "") for msg in conversation_history[-4:] 
                    if msg.get("role") == "user"
                ]
                if recent_user_msgs:
                    context_parts.append(f"Recent user messages: {'; '.join(recent_user_msgs[-2:])}")
            
            context = " ".join(context_parts) if context_parts else "No previous context."
            
            prompt = f"""You are an expert intent classifier for a data analytics chatbot.

Context: {context}

User query: "{user_query}"

Classify the user's intent into ONE of these categories:

1. GREETING: Simple greeting, chitchat, or social pleasantries (e.g., "hello", "hi", "how are you", "good morning")
   - These should NOT trigger database queries
   - requires_sql: false

2. DATA_QUERY: New question requiring SQL generation (e.g., "show me claims", "how many users", "compare volumes")
   - requires_sql: true

3. FOLLOW_UP_QUERY: Refinement or extension of previous query that needs new SQL (e.g., "also show me providers", "add state breakdown")
   - requires_sql: true

4. NARRATIVE: Analysis/explanation of PREVIOUS results, NO new SQL needed (e.g., "tell me more", "what does this mean", "explain this")
   - Only use if previous results exist
   - requires_sql: false
   - requires_previous_data: true

5. CLARIFICATION: User needs clarification or is confused (e.g., "what do you mean", "I don't understand")
   - requires_sql: false

IMPORTANT RULES:
- If the query is a simple greeting (hello, hi, etc.), it's GREETING
- If asking about data that needs to be fetched, it's DATA_QUERY
- If asking to explain/analyze previous results, it's NARRATIVE
- Be conservative: when in doubt, choose DATA_QUERY

Respond ONLY with valid JSON (no markdown, no code blocks):
{{
    "intent": "INTENT_NAME",
    "reasoning": "Brief explanation",
    "requires_sql": true/false,
    "requires_previous_data": true/false
}}"""

            ollama_client = await get_ollama_client()
            response = await asyncio.wait_for(
                ollama_client.chat(
                    messages=[
                        {
                            "role": "system", 
                            "content": "You are a precise intent classification system. Respond only with valid JSON, no additional text."
                        },
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.2,  # Lower temperature for more consistent classification
                    max_tokens=200
                ),
                timeout=5.0  # Increased timeout
            )
            
            import json
            
            # Extract JSON from response (handle markdown code blocks)
            response_clean = response.strip()
            if response_clean.startswith("```"):
                # Remove markdown code blocks
                response_clean = re.sub(r'```json\s*', '', response_clean)
                response_clean = re.sub(r'```\s*', '', response_clean)
            
            # Try to find JSON object
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_clean, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group(0))
                    intent_str = result.get("intent", "DATA_QUERY").upper().strip()
                    
                    # Map to IntentType
                    intent_map = {
                        "GREETING": IntentType.GREETING,
                        "DATA_QUERY": IntentType.DATA_QUERY,
                        "FOLLOW_UP_QUERY": IntentType.FOLLOW_UP_QUERY,
                        "NARRATIVE": IntentType.NARRATIVE,
                        "CLARIFICATION": IntentType.CLARIFICATION
                    }
                    
                    mapped_intent = intent_map.get(intent_str, IntentType.DATA_QUERY)
                    
                    return {
                        "intent": mapped_intent,
                        "confidence": 0.88,
                        "reasoning": result.get("reasoning", "LLM classification"),
                        "requires_sql": bool(result.get("requires_sql", True)),
                        "requires_previous_data": bool(result.get("requires_previous_data", False))
                    }
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse LLM JSON response: {e}, response: {response_clean[:100]}")
            else:
                logger.warning(f"No JSON found in LLM response: {response_clean[:100]}")
                
        except asyncio.TimeoutError:
            logger.warning("LLM intent classification timed out")
        except Exception as e:
            logger.warning(f"LLM intent classification error: {e}", exc_info=True)
        
        return None


# Global instance
intent_router = IntentRouter()

