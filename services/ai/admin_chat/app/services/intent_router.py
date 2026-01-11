"""
Intent Router Service
Classifies user queries as [DATA] or [CHAT] and routes to appropriate handler
"""
from typing import Literal
from app.services.llm_client import llm_client
from app.core.config import settings


class IntentRouter:
    """
    Router that classifies user intent and routes to appropriate handler
    
    [DATA]: Database queries, statistics, records, lists
    [CHAT]: Greetings, general conversation, questions about capabilities
    """
    
    ROUTER_PROMPT = """You are an Intent Classifier. Your only job is to determine if a user wants to talk to the database or have a general conversation.

Categories:

[DATA]: Use this if the user asks for numbers, claims, records, lists, statistics, or status updates on data.

[CHAT]: Use this for greetings ("hi", "hello"), social questions ("how are you"), or asking what the tool can do.

Rules:

Respond ONLY with the tag [DATA] or [CHAT].

If you are unsure, default to [CHAT].

Never execute a command. Just classify."""

    DATA_SPECIALIST_PROMPT = """You are a SQL Data Expert. You have access to tools via MCP.

Operational Guidelines:

No Guessing: If a query is vague (e.g., "show claims"), do not default to "today." Ask the user: "What time period should I look at?"

Identity: You only respond to data requests.

Validation: Before running a tool, explain briefly what you are searching for.

Empty Results: If a query returns 0 results, do not hallucinate. State "No records found matching those criteria."

You have access to the following tools:
- generate_sql: Generate SQL queries from natural language
- execute_query: Execute SQL queries and get results
- get_schema: Get database schema information
- create_visualization: Create charts and visualizations
- manage_conversation: Manage conversation context"""

    CHAT_PROMPT = """You are a helpful assistant for the HIVA Admin Chat service. You help users understand how to use the data analytics system.

Your role:
- Answer questions about the system's capabilities
- Engage in friendly conversation
- Provide brief guidance when asked

IMPORTANT RULES:
- If a user asks about data (numbers, claims, statistics, lists, providers, transactions, amounts), DO NOT provide example queries or SQL
- Instead, simply say: "I can help you query that data. Please ask your question in a format like 'Show me [what you want]' and I'll retrieve it for you."
- Only provide example queries if the user explicitly asks "how do I query" or "what queries can I use" or "what can this system do"
- Keep responses brief and friendly
- For greetings, be warm and welcoming
- Do NOT generate SQL queries or provide detailed query examples unless explicitly asked about system capabilities

Be friendly, professional, and helpful."""

    async def classify_intent(self, user_query: str) -> Literal["DATA", "CHAT"]:
        """
        Classify user query intent
        
        Args:
            user_query: User's input query
        
        Returns:
            "DATA" for database queries, "CHAT" for general conversation
        """
        if not user_query or not user_query.strip():
            return "CHAT"
        
        query_lower = user_query.lower().strip()
        
        # Fast-path classification for obvious cases
        # Greetings
        greetings = {"hello", "hi", "hey", "good morning", "good afternoon", 
                    "good evening", "greetings", "howdy", "what's up"}
        if query_lower in greetings or (len(query_lower.split()) <= 2 and query_lower in ["hi", "hey", "hello"]):
            return "CHAT"
        
        # Social questions
        social_patterns = ["how are you", "how's it going", "what can you do", 
                          "what are you", "who are you", "help me", "what is this"]
        if any(pattern in query_lower for pattern in social_patterns):
            return "CHAT"
        
        # Data-related keywords (strong indicators)
        data_keywords = ["show", "count", "total", "number", "list", "claims", 
                        "users", "providers", "status", "by", "statistics", 
                        "records", "data", "query", "find", "get", "display",
                        "chart", "graph", "visualization", "top", "bottom",
                        "how many", "what is the", "breakdown", "volume",
                        "who are", "what are", "transaction", "amount", "per",
                        "give me", "tell me", "which", "highest", "lowest",
                        "most", "least", "disease", "diagnosis", "patient",
                        "state", "kogi", "zamfara", "kano", "lagos", "kaduna"]
        
        # Check for data keywords - if found, likely DATA intent
        if any(keyword in query_lower for keyword in data_keywords):
            # Strong data indicators - return DATA directly
            # Only use LLM if query is clearly about capabilities
            capability_patterns = ["what can you", "how do i", "how to", "what is this", "what does this"]
            if any(pattern in query_lower for pattern in capability_patterns):
                # Might be asking about capabilities, use LLM
                return await self._llm_classify(user_query)
            else:
                # Clear data query
                return "DATA"
        
        # Default to LLM classification for unclear cases
        return await self._llm_classify(user_query)
    
    async def _llm_classify(self, user_query: str) -> Literal["DATA", "CHAT"]:
        """
        Use LLM to classify intent when fast-path doesn't work
        
        Args:
            user_query: User's input query
        
        Returns:
            "DATA" or "CHAT"
        """
        try:
            prompt = f"{self.ROUTER_PROMPT}\n\nUser Query: {user_query}\n\nClassification:"
            
            # Use low temperature for consistent classification
            response = await llm_client.generate(
                prompt=prompt,
                temperature=0.0,  # Very low temperature for consistent results
                max_tokens=10  # Only need [DATA] or [CHAT]
            )
            
            # Extract classification from response
            response_upper = response.strip().upper()
            
            if "[DATA]" in response_upper:
                return "DATA"
            elif "[CHAT]" in response_upper:
                return "CHAT"
            else:
                # Default to CHAT if unclear
                return "CHAT"
        
        except Exception as e:
            # On error, default to CHAT (safer fallback)
            print(f"⚠️ Intent classification error: {e}, defaulting to CHAT")
            return "CHAT"
    
    def get_data_specialist_prompt(self) -> str:
        """Get the data specialist system prompt"""
        return self.DATA_SPECIALIST_PROMPT
    
    def get_chat_prompt(self) -> str:
        """Get the chat system prompt"""
        return self.CHAT_PROMPT


# Global instance
intent_router = IntentRouter()
