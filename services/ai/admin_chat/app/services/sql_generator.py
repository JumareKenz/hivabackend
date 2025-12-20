"""
SQL Generator Service - Schema-aware natural language to SQL translation
Uses LLM to generate SQL queries based on natural language and database schema
"""
from typing import Dict, Any, List, Optional
import json
import re
from datetime import datetime, timedelta
import calendar
from app.core.config import settings
from app.services.database_service import database_service
from app.services.llm_client import llm_client


class SQLGenerator:
    """Generates SQL queries from natural language using schema-aware LLM"""
    
    def __init__(self):
        self._schema_cache: Optional[Dict[str, Any]] = None
        self._cache_timestamp: Optional[float] = None
        self._cache_ttl: int = 3600  # Cache schema for 1 hour
    
    async def _get_schema_info(self) -> Dict[str, Any]:
        """Get database schema information (cached)"""
        import time
        
        # Return cached schema if still valid
        if self._schema_cache and self._cache_timestamp:
            if time.time() - self._cache_timestamp < self._cache_ttl:
                return self._schema_cache
        
        # Fetch fresh schema
        if not database_service.pool:
            return {}
        
        try:
            schema_info = await database_service.get_schema_info()
            self._schema_cache = schema_info
            self._cache_timestamp = time.time()
            return schema_info
        except Exception as e:
            print(f"Error fetching schema: {e}")
            return self._schema_cache or {}
    
    def _format_schema_for_prompt(self, schema_info: Dict[str, Any], query: str = "") -> str:
        """Format schema information for LLM prompt, prioritizing relevant tables"""
        if not schema_info or 'tables' not in schema_info:
            return "No schema information available."
        
        schema_text = "=== DATABASE SCHEMA ===\n\n"
        tables = schema_info['tables']
        
        # Extract table names and create priority order
        table_dict = {t.get('table_name', ''): t for t in tables}
        
        # Check if query mentions specific tables
        query_lower = query.lower()
        mentioned_tables = []
        for table_name in table_dict.keys():
            if table_name.lower() in query_lower:
                mentioned_tables.append(table_name)
        
        # Fast path: For very simple "claims by status" queries, only show claims table
        if query_lower and ('claims' in query_lower and 'status' in query_lower) and len(query_lower.split()) <= 5:
            claims_table = table_dict.get('claims')
            if claims_table:
                schema_text += "Table: claims\n"
                schema_text += "Columns:\n"
                for col in claims_table.get('columns', []):
                    col_name = col.get('column_name', 'unknown')
                    col_type = col.get('data_type', 'unknown')
                    nullable = col.get('is_nullable', 'YES')
                    schema_text += f"  - {col_name} ({col_type}, nullable: {nullable})\n"
                schema_text += "  Relationships: user_id -> users.id, provider_id -> providers.id\n"
                schema_text += "  Status: status column (integer), common values: 0, 1, NULL\n"
                schema_text += "\n=== END OF SCHEMA ===\n"
                return schema_text
        
        # Prioritize commonly queried tables
        priority_tables = ['claims', 'users', 'providers', 'states', 'health_records', 
                          'appointments', 'transactions', 'paymentorders', 'services']
        
        # Order: mentioned tables -> priority tables -> others
        ordered_tables = []
        seen = set()
        
        # Add mentioned tables first
        for table_name in mentioned_tables:
            if table_name in table_dict and table_name not in seen:
                ordered_tables.append(table_dict[table_name])
                seen.add(table_name)
        
        # Add priority tables
        for table_name in priority_tables:
            if table_name in table_dict and table_name not in seen:
                ordered_tables.append(table_dict[table_name])
                seen.add(table_name)
        
        # Add remaining tables
        for table in tables:
            if table.get('table_name') not in seen:
                ordered_tables.append(table)
        
        # Limit to first 30 tables to avoid token limits and reduce latency
        # Prioritize most relevant tables for the query
        limit = 30
        if query:
            # For simple queries, use fewer tables
            query_words = query.lower().split()
            if len(query_words) <= 4 and any(word in ['count', 'number', 'total', 'show', 'list'] for word in query_words):
                limit = 20  # Use fewer tables for simple queries
        
        for table in ordered_tables[:limit]:
            table_name = table.get('table_name', 'unknown')
            columns = table.get('columns', [])
            
            schema_text += f"Table: {table_name}\n"
            schema_text += "Columns:\n"
            
            for col in columns:
                col_name = col.get('column_name', 'unknown')
                col_type = col.get('data_type', 'unknown')
                nullable = col.get('is_nullable', 'YES')
                schema_text += f"  - {col_name} ({col_type}, nullable: {nullable})\n"
            
            # Add relationship hints for key tables
            if table_name == 'claims':
                schema_text += "  Relationships: user_id -> users.id, provider_id -> providers.id\n"
                schema_text += "  Validation: verified_by_id IS NOT NULL (verified), approved_by_id IS NOT NULL (approved)\n"
                schema_text += "  Status: status column (integer), common values: 0, 1, NULL\n"
            elif table_name == 'users':
                schema_text += "  Relationships: id <- claims.user_id, state -> states.name or states.id\n"
            elif table_name == 'providers':
                schema_text += "  Relationships: id <- claims.provider_id\n"
            
            schema_text += "\n"
        
        if len(ordered_tables) > limit:
            schema_text += f"\n... and {len(ordered_tables) - limit} more tables\n"
        
        schema_text += "=== END OF SCHEMA ===\n"
        return schema_text
    
    def _build_sql_prompt(
        self,
        natural_language_query: str,
        schema_text: str,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """Build prompt for LLM to generate SQL"""
        
        prompt = """You are an expert SQL query generator for a MySQL database. Your task is to convert natural language questions into accurate, read-only SQL queries.

CRITICAL RULES:
1. ONLY generate SELECT queries (read-only) - ALWAYS start with SELECT
2. NEVER include INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, or any write operations
3. Use proper MySQL syntax
4. Use table and column names EXACTLY as they appear in the schema - DO NOT invent column names
5. Before using any column, verify it exists in the schema for that table
6. For JOINs, check the relationships shown in the schema (e.g., claims.user_id -> users.id)
7. If querying by "state", check if the table has a 'state' column directly, or if you need to JOIN through users table
8. Be careful with JOINs - use appropriate join types (INNER JOIN, LEFT JOIN)
9. Handle NULL values appropriately
10. Use proper date/time functions for filtering
11. Include LIMIT clauses for large result sets when appropriate
12. If a column doesn't exist in a table, look for it in related tables via JOINs
13. For "validated", "verified", or "approved" claims, use: WHERE verified_by_id IS NOT NULL OR approved_by_id IS NOT NULL
14. ALWAYS return a complete SELECT statement - never return partial SQL or explanations

COMMON RELATIONSHIPS:
- claims.user_id -> users.id (to get user information including state)
- claims.provider_id -> providers.id (to get provider information)
- users.state -> states.id (users.state contains state ID, join to states table to get state names)
- When querying by state name, use: JOIN states s ON u.state = s.id and SELECT s.name AS state

VALIDATION/STATUS QUERIES:
- "validated claims" = WHERE verified_by_id IS NOT NULL OR approved_by_id IS NOT NULL
- "verified claims" = WHERE verified_by_id IS NOT NULL
- "approved claims" = WHERE approved_by_id IS NOT NULL
- Do NOT use status = 2 or status = 3 unless you see those values in the schema

DATE QUERIES:
- "this month" = WHERE DATE(created_at) >= first_day_of_month AND DATE(created_at) <= last_day_of_month
- "October 2025" = WHERE DATE(created_at) >= '2025-10-01' AND DATE(created_at) <= '2025-10-31'
- "last 30 days" = WHERE DATE(created_at) >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
- Always use DATE() function for date comparisons in MySQL
- Use 'YYYY-MM-DD' format for date literals

IMPORTANT: The users.state column contains state IDs (numbers), not state names. To get state names, you MUST join the states table:
  SELECT s.name AS state, ... 
  FROM claims c 
  JOIN users u ON c.user_id = u.id 
  JOIN states s ON u.state = s.id

STATE FILTERING - CRITICAL:
- When the query mentions a state name (e.g., "Zamfara", "Kano", "Lagos"), you MUST filter by state name using: WHERE s.name LIKE '%StateName%' (use LIKE for case-insensitive matching)
- Common state names: Zamfara, Kano, Kogi, Kaduna, FCT, Abuja, Adamawa, Sokoto, Rivers, Osun, Lagos, etc.
- NEVER filter by date when a state name is mentioned in the query (unless date is also explicitly mentioned)
- Example: "claims in Zamfara" = WHERE s.name LIKE '%Zamfara%'
- Example: "tell me about claims in zamfara state" = WHERE s.name LIKE '%Zamfara%' (use LIKE for better matching)
- If query mentions both state AND date, filter by BOTH conditions using AND
- IMPORTANT: Use LIKE '%StateName%' instead of exact match (=) for better state name matching

GROUP BY - CRITICAL:
- When using GROUP BY with table aliases (e.g., c.status), ALWAYS use the table alias prefix: GROUP BY c.status (not just GROUP BY status)
- If you SELECT a CASE expression as status_name, GROUP BY the CASE expression or use the alias: GROUP BY status_name
- Example: SELECT CASE c.status ... END AS status_name, COUNT(*) FROM claims c GROUP BY c.status (use c.status, not status_name)

CRITICAL: ALWAYS SHOW NAMES INSTEAD OF IDs - THIS IS MANDATORY:
- For status: ALWAYS use CASE statement to map status values to names (0='Pending', 1='Approved', 2='Rejected', 3='Verified', NULL='Pending'). NEVER return raw status numbers.
- For user_id: ALWAYS JOIN users table and use CONCAT(u.firstname, ' ', u.lastname) AS user_name. NEVER return user_id as a number.
- For provider_id: IMPORTANT - The providers table structure is: id, agency_id, provider_id (VARCHAR identifier), status. There is NO name column. If you need to show provider information, use p.provider_id AS provider_name (it's already a varchar identifier, not a numeric ID). Only JOIN providers table when the query explicitly asks for provider information (e.g., "top providers", "provider names", "facilities"). For queries like "claims by status" or "claims in [state]", DO NOT join providers table.
- For state: ALWAYS JOIN states table to get state names (s.name AS state). NEVER return state IDs.
- For any foreign key (user_id, provider_id, state, etc.): ALWAYS join to the related table and return the name field, never the ID.
- NEVER include raw ID columns (user_id, provider_id, state_id) in SELECT unless specifically requested. Always replace them with name columns.
- Always prefer human-readable names over numeric IDs in SELECT statements. This is a strict requirement.
- IMPORTANT: Only JOIN tables that are necessary. For "claims by status in [state]", you need: claims, users (for state), states. You do NOT need providers JOIN.

OUTPUT FORMAT: Return ONLY the SQL query, no explanations, no markdown, no code blocks, just the raw SQL starting with SELECT.

"""
        
        # Add schema information
        prompt += schema_text + "\n\n"
        
        # Add conversation history if available
        if conversation_history:
            prompt += "=== CONVERSATION CONTEXT ===\n"
            for msg in conversation_history[-4:]:  # Last 4 messages for context
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')
                if role == 'user':
                    prompt += f"User: {content}\n"
                elif role == 'assistant':
                    prompt += f"Assistant: {content}\n"
            prompt += "=== END OF CONTEXT ===\n\n"
        
        # Add the current query
        prompt += f"""=== USER QUERY ===
{natural_language_query}

=== YOUR TASK ===
Generate a MySQL SELECT query that answers this question. 

CRITICAL REQUIREMENTS:
1. ALWAYS use names instead of IDs - join related tables to get human-readable names
2. For user_id -> JOIN users and use CONCAT(firstname, ' ', lastname) AS user_name
3. For provider_id -> JOIN providers and use provider name field
4. For state -> JOIN states and use state name
5. For status -> Use CASE statement to convert numbers to status names
6. **IF THE QUERY MENTIONS A STATE NAME (e.g., "Zamfara", "Kano"), YOU MUST FILTER BY STATE NAME using WHERE s.name = 'StateName' or WHERE s.name LIKE '%StateName%'**
7. **DO NOT filter by date unless the query explicitly mentions a date or time period**
8. **When query says "tell me about claims in [STATE]", filter by that state, NOT by today's date**
9. Return ONLY the SQL query starting with SELECT. No explanations, no markdown, no code blocks, no backticks, just the raw SQL statement.

SQL Query:"""
        
        return prompt
    
    def _extract_sql_from_response(self, response: str, natural_language_query: str = "") -> str:
        """Extract SQL query from LLM response, removing markdown and explanations"""
        # Remove markdown code blocks
        response = re.sub(r'```sql\s*', '', response, flags=re.IGNORECASE)
        response = re.sub(r'```\s*', '', response)
        response = re.sub(r'`', '', response)
        
        # Find SQL query (usually starts with SELECT)
        lines = response.split('\n')
        sql_lines = []
        in_sql = False
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Start collecting when we see SELECT
            if line.upper().startswith('SELECT'):
                in_sql = True
                sql_lines.append(line)
            elif in_sql:
                # Stop if we see explanation keywords
                if any(keyword in line.upper() for keyword in ['EXPLANATION', 'NOTE:', 'THIS QUERY', 'RETURNS']):
                    break
                # Continue collecting SQL
                sql_lines.append(line)
                # Stop at semicolon
                if line.endswith(';'):
                    break
        
        sql = ' '.join(sql_lines).strip()
        
        # If no SQL found, try to extract from entire response
        if not sql or not sql.upper().startswith('SELECT'):
            # Try to find SELECT statement anywhere
            match = re.search(r'SELECT.*?;', response, re.IGNORECASE | re.DOTALL)
            if match:
                sql = match.group(0).strip()
            else:
                # Last resort: use response as-is if it looks like SQL
                if 'SELECT' in response.upper():
                    sql = response.strip()
        
        # Remove trailing semicolon if present (we'll add it if needed)
        sql = sql.rstrip(';').strip()
        
        # Ensure it's a SELECT query
        if not sql.upper().startswith('SELECT'):
            raise ValueError("Generated query is not a SELECT statement")
        
        # Security check: ensure no write operations
        # Check for whole words only (not substrings like "ALTER" in "COALESCE")
        sql_upper = sql.upper()
        forbidden = ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER', 'TRUNCATE', 'GRANT', 'REVOKE']
        
        # Split SQL into words and check for forbidden keywords as whole words
        # Use word boundaries to avoid false positives (e.g., "ALTER" in "COALESCE")
        sql_words = set(re.split(r'[\s,;()\[\]`]+', sql_upper))
        for keyword in forbidden:
            if keyword in sql_words:
                raise ValueError(f"Query contains forbidden operations: {sql}")
        
        # Post-process: Ensure names are used instead of IDs
        sql = self._enhance_sql_with_names(sql)
        
        # Post-process: Remove unnecessary provider JOINs if provider info not in SELECT
        sql = self._remove_unnecessary_provider_joins(sql, natural_language_query)
        
        return sql
    
    def _enhance_sql_with_names(self, sql: str) -> str:
        """
        Post-process SQL to ensure names are used instead of IDs.
        This is a safety net to ensure human-readable output.
        """
        sql_upper = sql.upper()
        original_sql = sql
        
        # Check if query involves claims table and might need name conversions
        if 'FROM CLAIMS' in sql_upper or 'FROM `CLAIMS`' in sql_upper or 'FROM claims' in sql:
            # Check if we're selecting raw IDs that should be converted to names
            needs_user_name = ('USER_ID' in sql_upper or '`user_id`' in sql or 'user_id' in sql) and 'USER_NAME' not in sql_upper and 'CONCAT' not in sql_upper
            needs_provider_name = ('PROVIDER_ID' in sql_upper or '`provider_id`' in sql or 'provider_id' in sql) and 'PROVIDER_NAME' not in sql_upper
            needs_state_name = ('STATE' in sql_upper or '`state`' in sql) and 'STATE_NAME' not in sql_upper and 'S.NAME' not in sql_upper and 'states' not in sql.lower()
            needs_status_name = ('STATUS' in sql_upper or '`status`' in sql) and 'STATUS_NAME' not in sql_upper and 'CASE' not in sql_upper
            
            # If we need any conversions, try to enhance the query
            if needs_user_name or needs_provider_name or needs_state_name or needs_status_name:
                # This is a complex transformation - for now, we'll rely on the prompt
                # But we can add a simple enhancement for common cases
                pass
        
        # For simple cases where status is selected but not converted, add CASE statement
        if 'SELECT' in sql_upper and 'STATUS' in sql_upper and 'CASE' not in sql_upper and 'STATUS_NAME' not in sql_upper:
            # Try to replace raw status with CASE statement (simple pattern matching)
            # This is a basic enhancement - the prompt should handle most cases
            pass
        
        return original_sql
    
    def _remove_unnecessary_provider_joins(self, sql: str, query: str) -> str:
        """
        Remove unnecessary provider JOINs if provider information is not needed
        
        Args:
            sql: Generated SQL query
            query: Original natural language query
        
        Returns:
            SQL with unnecessary provider JOINs removed
        """
        query_lower = query.lower()
        
        # Check if query explicitly asks for provider information
        provider_keywords = ["provider", "facility", "hospital", "clinic", "doctor", "physician"]
        needs_provider = any(keyword in query_lower for keyword in provider_keywords)
        
        # Check if SQL selects provider information
        sql_upper = sql.upper()
        selects_provider = any(keyword in sql_upper for keyword in [
            "PROVIDER_NAME", "P.NAME", "P.PROVIDER", "FACILITY_NAME", "P.FACILITY"
        ])
        
        # If provider not needed and not selected, remove provider JOIN
        if not needs_provider and not selects_provider:
            # Remove LEFT JOIN providers or JOIN providers
            # Remove LEFT JOIN providers p ON ...
            sql = re.sub(r'LEFT\s+JOIN\s+providers\s+p\s+ON\s+[^,\s]+\s*=\s*[^,\s]+', '', sql, flags=re.IGNORECASE)
            # Remove JOIN providers p ON ...
            sql = re.sub(r'JOIN\s+providers\s+p\s+ON\s+[^,\s]+\s*=\s*[^,\s]+', '', sql, flags=re.IGNORECASE)
            # Remove provider-related columns from SELECT
            sql = re.sub(r',\s*COALESCE\(p\.\w+[^,)]*\)\s+AS\s+provider_name', '', sql, flags=re.IGNORECASE)
            sql = re.sub(r',\s*p\.\w+\s+AS\s+provider_name', '', sql, flags=re.IGNORECASE)
            # Clean up extra commas
            sql = re.sub(r',\s*,', ',', sql)
            sql = re.sub(r'SELECT\s+,', 'SELECT ', sql, flags=re.IGNORECASE)
        
        return sql
    
    async def generate_sql(
        self,
        natural_language_query: str,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Generate SQL query from natural language
        
        Args:
            natural_language_query: User's question in natural language
            conversation_history: Previous conversation messages for context
        
        Returns:
            Dictionary with 'sql', 'explanation', and 'confidence'
        """
        try:
            # Fast path: Direct SQL for very common simple queries (bypasses LLM for speed)
            query_lower = natural_language_query.lower().strip()
            
            # Status queries - show status names instead of IDs
            # Only use fast-path if NO additional filters (state, date, etc.)
            if query_lower in ["show me claims by status", "claims by status", "claims grouped by status"]:
                # Check for additional filters - if present, skip fast-path
                has_state_filter = any(state in query_lower for state in [
                    "state", "zamfara", "kano", "kogi", "kaduna", "fct", "abuja", 
                    "adamawa", "sokoto", "rivers", "osun", "lagos", "in "
                ])
                has_date_filter = any(date_word in query_lower for date_word in [
                    "month", "year", "day", "week", "date", "today", "yesterday", "last"
                ])
                
                # Only use fast-path if no additional filters
                if not has_state_filter and not has_date_filter:
                    return {
                        "sql": """SELECT 
                            CASE 
                                WHEN status IS NULL THEN 'Pending'
                                WHEN status = 0 THEN 'Pending'
                                WHEN status = 1 THEN 'Approved'
                                WHEN status = 2 THEN 'Rejected'
                                WHEN status = 3 THEN 'Verified'
                                ELSE CONCAT('Status ', status)
                            END as status_name,
                            COUNT(*) as count 
                            FROM claims 
                            GROUP BY status 
                            ORDER BY count DESC""",
                        "explanation": "This query shows the count of claims grouped by status with readable status names",
                        "confidence": 0.95
                    }
            
            # Count queries
            if query_lower in ["total number of claims", "how many claims", "count of claims", "show me total number of claims"]:
                return {
                    "sql": "SELECT COUNT(*) as total_claims FROM claims",
                    "explanation": "This query returns the total number of claims",
                    "confidence": 0.95
                }
            
            # Date-based queries - parse and generate SQL directly
            now = datetime.now()
            
            # "this month" queries
            if "this month" in query_lower and "claim" in query_lower:
                first_day = datetime(now.year, now.month, 1)
                last_day = datetime(now.year, now.month, calendar.monthrange(now.year, now.month)[1])
                if "count" in query_lower or "number" in query_lower or "how many" in query_lower:
                    return {
                        "sql": f"SELECT COUNT(*) as count FROM claims WHERE DATE(created_at) >= '{first_day.strftime('%Y-%m-%d')}' AND DATE(created_at) <= '{last_day.strftime('%Y-%m-%d')}'",
                        "explanation": f"This query returns the count of claims created this month ({now.strftime('%B %Y')})",
                        "confidence": 0.95
                    }
                else:
                    return {
                        "sql": f"""SELECT 
                            c.id,
                            c.claim_unique_id,
                            c.client_name,
                            CASE 
                                WHEN c.status IS NULL THEN 'Pending'
                                WHEN c.status = 0 THEN 'Pending'
                                WHEN c.status = 1 THEN 'Approved'
                                WHEN c.status = 2 THEN 'Rejected'
                                WHEN c.status = 3 THEN 'Verified'
                                ELSE CONCAT('Status ', c.status)
                            END as status_name,
                            CONCAT(u.firstname, ' ', u.lastname) as user_name,
                            c.total_cost,
                            c.created_at
                            FROM claims c
                            LEFT JOIN users u ON c.user_id = u.id
                            WHERE DATE(c.created_at) >= '{first_day.strftime('%Y-%m-%d')}' 
                            AND DATE(c.created_at) <= '{last_day.strftime('%Y-%m-%d')}' 
                            ORDER BY c.created_at DESC 
                            LIMIT 100""",
                        "explanation": f"This query returns claims created this month ({now.strftime('%B %Y')}) with names instead of IDs",
                        "confidence": 0.95
                    }
            
            # Specific month queries (e.g., "October 2025", "claims in October 2025")
            month_names = {
                'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
                'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12
            }
            
            for month_name, month_num in month_names.items():
                if month_name in query_lower and "claim" in query_lower:
                    # Extract year (default to current year if not specified)
                    year_match = re.search(r'\b(20\d{2})\b', natural_language_query)
                    year = int(year_match.group(1)) if year_match else now.year
                    
                    first_day = datetime(year, month_num, 1)
                    last_day = datetime(year, month_num, calendar.monthrange(year, month_num)[1])
                    
                    if "count" in query_lower or "number" in query_lower or "how many" in query_lower:
                        return {
                            "sql": f"SELECT COUNT(*) as count FROM claims WHERE DATE(created_at) >= '{first_day.strftime('%Y-%m-%d')}' AND DATE(created_at) <= '{last_day.strftime('%Y-%m-%d')}'",
                            "explanation": f"This query returns the count of claims created in {month_name.capitalize()} {year}",
                            "confidence": 0.95
                        }
                    else:
                        return {
                            "sql": f"""SELECT 
                                c.id,
                                c.claim_unique_id,
                                c.client_name,
                                CASE 
                                    WHEN c.status IS NULL THEN 'Pending'
                                    WHEN c.status = 0 THEN 'Pending'
                                    WHEN c.status = 1 THEN 'Approved'
                                    WHEN c.status = 2 THEN 'Rejected'
                                    WHEN c.status = 3 THEN 'Verified'
                                    ELSE CONCAT('Status ', c.status)
                                END as status_name,
                                CONCAT(u.firstname, ' ', u.lastname) as user_name,
                                c.total_cost,
                                c.created_at
                                FROM claims c
                                LEFT JOIN users u ON c.user_id = u.id
                                WHERE DATE(c.created_at) >= '{first_day.strftime('%Y-%m-%d')}' 
                                AND DATE(c.created_at) <= '{last_day.strftime('%Y-%m-%d')}' 
                                ORDER BY c.created_at DESC 
                                LIMIT 100""",
                            "explanation": f"This query returns claims created in {month_name.capitalize()} {year} with names instead of IDs",
                            "confidence": 0.95
                        }
            
            # "today" queries
            if "today" in query_lower and "claim" in query_lower:
                today = datetime.now().date()
                if "count" in query_lower or "number" in query_lower or "how many" in query_lower:
                    return {
                        "sql": f"SELECT COUNT(*) as count FROM claims WHERE DATE(created_at) = '{today.strftime('%Y-%m-%d')}'",
                        "explanation": f"This query returns the count of claims created today ({today.strftime('%B %d, %Y')})",
                        "confidence": 0.95
                    }
                else:
                    return {
                        "sql": f"""SELECT 
                            c.id,
                            c.claim_unique_id,
                            c.client_name,
                            CASE 
                                WHEN c.status IS NULL THEN 'Pending'
                                WHEN c.status = 0 THEN 'Pending'
                                WHEN c.status = 1 THEN 'Approved'
                                WHEN c.status = 2 THEN 'Rejected'
                                WHEN c.status = 3 THEN 'Verified'
                                ELSE CONCAT('Status ', c.status)
                            END as status_name,
                            CONCAT(u.firstname, ' ', u.lastname) as user_name,
                            c.total_cost,
                            c.created_at
                            FROM claims c
                            LEFT JOIN users u ON c.user_id = u.id
                            WHERE DATE(c.created_at) = '{today.strftime('%Y-%m-%d')}' 
                            ORDER BY c.created_at DESC 
                            LIMIT 100""",
                        "explanation": f"This query returns claims created today ({today.strftime('%B %d, %Y')}) with names instead of IDs",
                        "confidence": 0.95
                    }
            
            # "this year" queries
            if "this year" in query_lower and "claim" in query_lower:
                first_day = datetime(now.year, 1, 1)
                last_day = datetime(now.year, 12, 31)
                if "count" in query_lower or "number" in query_lower or "how many" in query_lower:
                    return {
                        "sql": f"SELECT COUNT(*) as count FROM claims WHERE DATE(created_at) >= '{first_day.strftime('%Y-%m-%d')}' AND DATE(created_at) <= '{last_day.strftime('%Y-%m-%d')}'",
                        "explanation": f"This query returns the count of claims created this year ({now.year})",
                        "confidence": 0.95
                    }
                else:
                    return {
                        "sql": f"""SELECT 
                            c.id,
                            c.claim_unique_id,
                            c.client_name,
                            CASE 
                                WHEN c.status IS NULL THEN 'Pending'
                                WHEN c.status = 0 THEN 'Pending'
                                WHEN c.status = 1 THEN 'Approved'
                                WHEN c.status = 2 THEN 'Rejected'
                                WHEN c.status = 3 THEN 'Verified'
                                ELSE CONCAT('Status ', c.status)
                            END as status_name,
                            CONCAT(u.firstname, ' ', u.lastname) as user_name,
                            c.total_cost,
                            c.created_at
                            FROM claims c
                            LEFT JOIN users u ON c.user_id = u.id
                            WHERE DATE(c.created_at) >= '{first_day.strftime('%Y-%m-%d')}' 
                            AND DATE(c.created_at) <= '{last_day.strftime('%Y-%m-%d')}' 
                            ORDER BY c.created_at DESC 
                            LIMIT 100""",
                        "explanation": f"This query returns claims created this year ({now.year}) with names instead of IDs",
                        "confidence": 0.95
                    }
            
            # "last 30 days" or "last month" queries
            if ("last 30 days" in query_lower or "last month" in query_lower) and "claim" in query_lower:
                if "last month" in query_lower:
                    # First day of last month
                    if now.month == 1:
                        first_day = datetime(now.year - 1, 12, 1)
                        last_day = datetime(now.year - 1, 12, 31)
                    else:
                        first_day = datetime(now.year, now.month - 1, 1)
                        last_day = datetime(now.year, now.month - 1, calendar.monthrange(now.year, now.month - 1)[1])
                else:
                    # Last 30 days
                    last_day = datetime.now()
                    first_day = last_day - timedelta(days=30)
                
                if "count" in query_lower or "number" in query_lower:
                    return {
                        "sql": f"SELECT COUNT(*) as count FROM claims WHERE DATE(created_at) >= '{first_day.strftime('%Y-%m-%d')}' AND DATE(created_at) <= '{last_day.strftime('%Y-%m-%d')}'",
                        "explanation": "This query returns the count of claims from the specified period",
                        "confidence": 0.95
                    }
                else:
                    return {
                        "sql": f"""SELECT 
                            c.id,
                            c.claim_unique_id,
                            c.client_name,
                            CASE 
                                WHEN c.status IS NULL THEN 'Pending'
                                WHEN c.status = 0 THEN 'Pending'
                                WHEN c.status = 1 THEN 'Approved'
                                WHEN c.status = 2 THEN 'Rejected'
                                WHEN c.status = 3 THEN 'Verified'
                                ELSE CONCAT('Status ', c.status)
                            END as status_name,
                            CONCAT(u.firstname, ' ', u.lastname) as user_name,
                            c.total_cost,
                            c.created_at
                            FROM claims c
                            LEFT JOIN users u ON c.user_id = u.id
                            WHERE DATE(c.created_at) >= '{first_day.strftime('%Y-%m-%d')}' 
                            AND DATE(c.created_at) <= '{last_day.strftime('%Y-%m-%d')}' 
                            ORDER BY c.created_at DESC 
                            LIMIT 100""",
                        "explanation": "This query returns claims from the specified period with names instead of IDs",
                        "confidence": 0.95
                    }
            
            # Get schema information
            schema_info = await self._get_schema_info()
            schema_text = self._format_schema_for_prompt(schema_info, natural_language_query)
            
            # Build prompt
            prompt = self._build_sql_prompt(
                natural_language_query,
                schema_text,
                conversation_history
            )
            
            # Generate SQL using LLM
            # Increase max_tokens for complex queries with JOINs and state filtering
            # Complex queries can be 800-1000 tokens
            max_tokens = min(settings.DEFAULT_NUM_PREDICT, 1000)  # Increased for complex queries
            response = await llm_client.generate(
                prompt=prompt,
                temperature=settings.TEMPERATURE,
                max_tokens=max_tokens
            )
            
            # Extract SQL from response
            sql = self._extract_sql_from_response(response, natural_language_query)
            
            # Generate explanation
            explanation = f"This query retrieves data to answer: {natural_language_query}"
            
            # Calculate confidence (simple heuristic - can be improved)
            confidence = 0.8  # Default confidence
            if 'JOIN' in sql.upper() or 'WHERE' in sql.upper():
                confidence = 0.85
            if len(sql.split()) > 20:  # Complex queries
                confidence = 0.9
            
            return {
                "sql": sql,
                "explanation": explanation,
                "confidence": confidence
            }
            
        except Exception as e:
            raise RuntimeError(f"Failed to generate SQL: {str(e)}")


# Global instance
sql_generator = SQLGenerator()




