"""
SQL Generator Service - Converts Natural Language to SQL using LLM
"""
from typing import Optional, Dict, Any, List
import json
import re
from app.services.ollama_client import get_ollama_client
from app.services.database_service import database_service


class SQLGenerator:
    """Generates SQL queries from natural language using schema-aware LLM"""
    
    def __init__(self):
        self._schema_cache: Optional[Dict[str, Any]] = None
    
    async def get_schema_context(self) -> str:
        """Get database schema as context for LLM"""
        if not self._schema_cache:
            schema_info = await database_service.get_schema_info()
            self._schema_cache = schema_info
        
        if not self._schema_cache or not self._schema_cache.get("tables"):
            return "Database schema information is not available."
        
        # Format schema for LLM prompt
        schema_text = "DATABASE SCHEMA:\n\n"
        for table in self._schema_cache.get("tables", []):
            table_name = table.get("table_name", "")
            columns = table.get("columns", [])
            
            schema_text += f"Table: {table_name}\n"
            schema_text += "Columns:\n"
            for col in columns:
                col_name = col.get("column_name", "")
                col_type = col.get("data_type", "")
                nullable = "NULL" if col.get("is_nullable") == "YES" else "NOT NULL"
                schema_text += f"  - {col_name} ({col_type}, {nullable})\n"
            schema_text += "\n"
        
        return schema_text
    
    async def generate_sql(
        self,
        natural_language_query: str,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Generate SQL query from natural language
        
        Args:
            natural_language_query: User's natural language question
            conversation_history: Previous conversation messages for context
        
        Returns:
            Dictionary with 'sql', 'explanation', and 'confidence'
        """
        # Get schema context
        schema_context = await self.get_schema_context()
        
        # Build conversation context
        history_context = ""
        if conversation_history:
            # Include last 3 exchanges for context
            recent_history = conversation_history[-6:] if len(conversation_history) > 6 else conversation_history
            history_context = "\n\nPREVIOUS CONVERSATION:\n"
            for msg in recent_history:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                history_context += f"{role.upper()}: {content}\n"
        
        # Detect database type for appropriate SQL syntax
        db_type = database_service.db_type or "mysql"  # Default to MySQL
        
        # Create prompt for LLM
        system_prompt = f"""You are an expert SQL query generator for a {db_type.upper()} analytics database.

Your task is to convert natural language questions into accurate, safe, read-only SQL queries.

CRITICAL RULES:
1. ONLY generate SELECT queries (read-only)
2. NEVER include INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, or any write operations
3. Use proper SQL syntax for {db_type.upper()}
4. Use parameterized queries when appropriate
5. Include proper JOINs when needed
6. Use aggregate functions (COUNT, SUM, AVG, etc.) when requested
7. Add appropriate WHERE clauses for filtering
8. Use LIMIT when user asks for "top N" or "first N"
9. Format dates properly (use DATE functions - {db_type.upper()} syntax)
10. Handle NULL values appropriately
11. For MySQL: Use backticks (`) for table/column names if they contain special characters
12. For MySQL: Use %s for parameter placeholders (not $1 like PostgreSQL)

OUTPUT FORMAT:
You must respond with ONLY a valid JSON object in this exact format:
{{
    "sql": "SELECT ... FROM ... WHERE ...",
    "explanation": "Brief explanation of what the query does",
    "confidence": 0.95
}}

The SQL must be executable {db_type.upper()} syntax. The confidence should be between 0.0 and 1.0."""
        
        user_prompt = f"""{schema_context}

{history_context}

USER QUESTION: {natural_language_query}

Generate a SQL query to answer this question. Remember:
- Only SELECT queries (read-only)
- Use proper {db_type.upper()} syntax
- Include appropriate filters, joins, and aggregations
- Return ONLY the JSON object, no other text"""
        
        # Get LLM client
        ollama_client = await get_ollama_client()
        
        # Generate SQL using LLM
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            response = await ollama_client.chat(
                messages=messages,
                temperature=0.1,  # Low temperature for accuracy
                max_tokens=1000
            )
            
            # Parse response
            response_text = response.strip()
            
            # Extract JSON from response (handle markdown code blocks)
            json_match = re.search(r'\{[^{}]*"sql"[^{}]*\}', response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(0)
            
            # Try to parse as JSON
            try:
                result = json.loads(response_text)
            except json.JSONDecodeError:
                # Fallback: try to extract SQL directly
                sql_match = re.search(r'SELECT.*?(?:;|$)', response_text, re.IGNORECASE | re.DOTALL)
                if sql_match:
                    result = {
                        "sql": sql_match.group(0).strip().rstrip(';'),
                        "explanation": "Generated SQL query",
                        "confidence": 0.7
                    }
                else:
                    raise ValueError("Could not parse LLM response")
            
            # Validate SQL
            sql = result.get("sql", "").strip()
            if not sql.upper().startswith("SELECT"):
                raise ValueError("Generated query is not a SELECT statement")
            
            # Clean up SQL
            sql = sql.rstrip(';').strip()
            
            return {
                "sql": sql,
                "explanation": result.get("explanation", "SQL query generated"),
                "confidence": float(result.get("confidence", 0.7))
            }
            
        except Exception as e:
            raise RuntimeError(f"Failed to generate SQL: {str(e)}")
    
    def clear_schema_cache(self):
        """Clear schema cache (call when schema changes)"""
        self._schema_cache = None


# Global instance
sql_generator = SQLGenerator()

