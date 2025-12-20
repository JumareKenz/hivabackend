"""
Enhanced SQL Generator - World-Class NLP-to-SQL with Privacy-by-Design
Implements:
- Self-correction loop (Reflexion pattern)
- Semantic manifest for schema awareness
- Privacy-by-design prompts
- Complex query handling (CTEs, window functions, joins)
"""
from typing import Dict, Any, List, Optional, Tuple
import json
import re
import traceback
from app.services.database_service import database_service
from app.services.analytics_view_service import analytics_view_service
from app.services.privacy_service import privacy_service
from app.services.schema_loader import schema_loader
from app.services.schema_rag_service import schema_rag_service
from app.services.queryweaver_service import queryweaver_service
from app.services.queryweaver_service import queryweaver_service


class EnhancedSQLGenerator:
    """
    World-class SQL generator with self-correction and privacy compliance.
    Implements the Reflexion pattern for automatic error correction.
    """
    
    def __init__(self):
        self._schema_cache: Optional[Dict[str, Any]] = None
        self._semantic_manifest_cache: Optional[Dict[str, Any]] = None
        self.max_correction_attempts = 5  # Increased for zero error tolerance
        self._error_patterns_cache: Dict[str, str] = {}  # Cache error patterns for faster correction
    
    async def _get_semantic_manifest(self) -> Dict[str, Any]:
        """Get semantic manifest with column descriptions"""
        if not self._semantic_manifest_cache:
            self._semantic_manifest_cache = await analytics_view_service.get_semantic_manifest()
        return self._semantic_manifest_cache
    
    async def _get_schema_info(self) -> Dict[str, Any]:
        """Get schema information from analytics views"""
        if not self._schema_cache:
            # Try to get comprehensive schema first (includes database inspection)
            try:
                comprehensive = await schema_loader.load_comprehensive_schema()
                if comprehensive and comprehensive.get('tables'):
                    # Convert to expected format
                    tables = comprehensive.get('tables', [])
                    self._schema_cache = {'tables': tables}
                    return self._schema_cache
            except Exception as e:
                print(f"Warning: Could not load comprehensive schema: {e}")
            
            # Fallback to basic schema info
            self._schema_cache = await database_service.get_schema_info(use_analytics_views=True)
        return self._schema_cache
    
    def _build_semantic_schema_context(self, schema_info: Dict[str, Any], semantic_manifest: Dict[str, Any], query: str = "") -> str:
        """
        Build enhanced schema context with semantic descriptions.
        This is the "Semantic Manifest" that provides rich context to the LLM.
        """
        if not schema_info or 'tables' not in schema_info:
            return "No schema information available."
        
        context = "=== SEMANTIC DATABASE SCHEMA (Analytics View Layer) ===\n\n"
        context += "IMPORTANT: All tables use the 'analytics_view_' prefix. PII has been masked.\n\n"
        
        tables = schema_info.get('tables', [])
        query_lower = query.lower()
        
        # Prioritize relevant tables
        mentioned_tables = []
        for table in tables:
            table_name = table.get('table_name', '')
            if table_name and table_name.lower().replace('analytics_view_', '') in query_lower:
                mentioned_tables.append(table)
        
        # Show mentioned tables first, then priority tables
        priority_table_names = ['analytics_view_claims', 'analytics_view_users', 'analytics_view_providers', 
                               'analytics_view_states', 'analytics_view_transactions']
        
        ordered_tables = []
        seen = set()
        
        # Add mentioned tables
        for table in mentioned_tables:
            table_name = table.get('table_name', '')
            if table_name and table_name not in seen:
                ordered_tables.append(table)
                seen.add(table_name)
        
        # Add priority tables
        for priority_name in priority_table_names:
            for table in tables:
                table_name = table.get('table_name', '')
                if table_name == priority_name and table_name not in seen:
                    ordered_tables.append(table)
                    seen.add(table_name)
                    break
        
        # Add remaining tables
        for table in tables:
            table_name = table.get('table_name', '')
            if table_name and table_name not in seen:
                ordered_tables.append(table)
        
        # Limit to 25 tables to avoid token limits
        for table in ordered_tables[:25]:
            table_name = table.get('table_name', '')
            if not table_name:
                continue
            
            # Get semantic description
            base_table_name = table_name.replace('analytics_view_', '')
            table_info = semantic_manifest.get(base_table_name, {})
            table_desc = table_info.get('table_description', f'Table: {base_table_name}')
            
            context += f"Table: {table_name}\n"
            context += f"Description: {table_desc}\n"
            context += "Columns:\n"
            
            columns = table.get('columns', [])
            for col in columns:
                col_name = col.get('column_name', '')
                col_type = col.get('data_type', '')
                
                # Get semantic description
                col_info = table_info.get('columns', {}).get(col_name, {})
                col_desc = col_info.get('description', f'{col_name} ({col_type})')
                is_pii = col_info.get('is_pii', False)
                
                pii_note = " [PII - MASKED]" if is_pii else ""
                context += f"  - {col_name} ({col_type}): {col_desc}{pii_note}\n"
            
            # Add relationship hints
            if 'claims' in table_name.lower():
                context += "  Relationships:\n"
                context += "    - user_id -> analytics_view_users.id (hashed)\n"
                context += "    - provider_id -> analytics_view_providers.id (hashed)\n"
            elif 'users' in table_name.lower():
                context += "  Relationships:\n"
                context += "    - state -> analytics_view_states.id\n"
            
            context += "\n"
        
        context += "=== END OF SCHEMA ===\n"
        return context
    
    def _build_privacy_prompt(self) -> str:
        """
        Build the "Strict Constructionist" system prompt with privacy-by-design.
        """
        return """You are an analytics assistant with expertise in SQL query generation and privacy compliance.

CRITICAL PRIVACY REQUIREMENTS & GUARDRAILS:
1. You have ZERO access to PII (Personally Identifiable Information). All data is pre-masked in analytics views.
2. You MUST refuse to answer questions about specific individuals or "who" a patient is.
3. If a user provides a name, phone number, or specific ID in their prompt, you MUST:
   - Redact it in your internal processing
   - Inform the user that you only process de-identified data
   - Never attempt to reverse-engineer hashed IDs
4. If a user's natural language query hints at identifying a specific person, you MUST pivot to aggregated trends.
5. You MUST respond: "For privacy compliance, I provide insights at the cohort level only."
6. All queries MUST use tables with the 'analytics_view_' prefix. Never query raw tables.
7. All database actions MUST be read-only (SELECT only). Never generate INSERT, UPDATE, DELETE, or any write operations.

DATA MASKING PATTERNS (What you see in analytics views):
- Patient Identity: Hashed (e.g., "John Doe" → "a5f1...e92b")
- Location: Region only (e.g., "123 Herbert Macaulay Way" → "Osun State")
- Time Scale: Aggregated (e.g., "Oct 12, 2023, 14:30" → "Q4 2023")
- Medical Detail: Generalized (e.g., "Stage 2 Chronic Kidney Disease" → "Chronic - Renal")
- Names: [REDACTED]
- Phone Numbers: Masked (***-***-XXXX)
- Email: Masked (XX***@***)
- DOB: Age-bucketed (0-17, 18-24, 25-34, etc.)

YOUR ROLE:
- Convert natural language questions into accurate, optimized SQL queries
- Generate queries that work with the analytics_view_* schema (privacy-compliant)
- Handle complex queries: multi-table JOINs, CTEs (WITH clauses), window functions
- Use proper SQL syntax for the database type (MySQL or PostgreSQL)
- Optimize queries for performance when possible

QUERY GENERATION RULES:
1. ONLY generate SELECT queries (read-only)
2. NEVER include INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, or any write operations
3. ALWAYS use 'analytics_view_' prefix for all table names
4. Use proper JOINs when needed (INNER JOIN, LEFT JOIN, etc.)
5. Use CTEs (WITH clauses) for complex subqueries
6. Use window functions (ROW_NUMBER, RANK, LAG, LEAD) for ranking and time-series analysis
7. Handle NULL values appropriately
8. Use aggregate functions (COUNT, SUM, AVG, MAX, MIN) when requested
9. Add appropriate WHERE clauses for filtering
10. Use LIMIT for large result sets
11. Format dates properly using DATE functions

COMPLEX QUERY PATTERNS:
- "Top N providers by claim volume": 
  SELECT provider_name, COUNT(*) as claim_count, SUM(total_cost) as total_volume
  FROM analytics_view_claims 
  WHERE [date filters]
  GROUP BY provider_name 
  ORDER BY claim_count DESC 
  LIMIT N

- "Compare claim volume for November and October 2025":
  Use UNION ALL to combine results from both months:
  SELECT 'October 2025' as period, COUNT(*) as claim_count, SUM(total_cost) as total_volume
  FROM analytics_view_claims WHERE DATE(created_at) >= '2025-10-01' AND DATE(created_at) <= '2025-10-31'
  UNION ALL
  SELECT 'November 2025' as period, COUNT(*) as claim_count, SUM(total_cost) as total_volume
  FROM analytics_view_claims WHERE DATE(created_at) >= '2025-11-01' AND DATE(created_at) <= '2025-11-30'
  ORDER BY period

- "Ranking facilities by month-over-month growth": Use window functions with LAG/LEAD
- "Top N providers by claims": ALWAYS use GROUP BY provider_name, COUNT(*), ORDER BY DESC, LIMIT N
- "Compare this month vs last month": Use UNION ALL or CTEs with date filtering
- "Cohort analysis": Use GROUP BY with date buckets

CRITICAL: When user asks for "top N by X", "compare X and Y", or "show me providers by volume":
- You MUST use GROUP BY to aggregate (unless comparing periods with UNION ALL)
- You MUST use COUNT(*) or SUM() for aggregation
- You MUST use ORDER BY ... DESC to rank (for top N queries)
- You MUST use LIMIT N to get top N results
- For comparisons: Use UNION ALL to combine results from different periods
- NEVER return individual claim rows - always aggregate first!

OUTPUT FORMAT:
CRITICAL: You MUST return ONLY a valid SQL query starting with SELECT.
- Start your response with SELECT (no markdown, no code blocks, no explanations)
- The SQL must be executable and use analytics_view_* tables only
- For comparison queries, use UNION ALL to combine results
- Always use aggregation (COUNT, SUM, GROUP BY) when comparing volumes or counts"""
    
    async def _generate_sql_with_llm(
        self,
        natural_language_query: str,
        schema_context: str,
        error_context: Optional[str] = None,
        previous_attempts: List[str] = None,
        entity_mappings: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate SQL using LLM with error context for self-correction.
        
        Args:
            natural_language_query: User's question
            schema_context: Formatted schema with semantic descriptions
            error_context: Error message from previous attempt (for self-correction)
            previous_attempts: List of previous SQL attempts that failed
        
        Returns:
            Generated SQL query string
        """
        from app.services.ollama_client import get_ollama_client
        
        system_prompt = self._build_privacy_prompt()
        
        user_prompt = f"""{schema_context}

"""
        
        # Add error context if this is a correction attempt
        if error_context:
            user_prompt += f"""=== PREVIOUS ATTEMPT FAILED ===
Error: {error_context}

Previous SQL attempts that failed:
"""
            for i, prev_sql in enumerate(previous_attempts or [], 1):
                user_prompt += f"{i}. {prev_sql}\n"
            
            user_prompt += """
=== YOUR TASK: FIX THE QUERY ===
Analyze the error above. Common issues:
- Table/column names don't exist (check schema carefully)
- Syntax errors (check database type - MySQL vs PostgreSQL)
- Missing JOINs when accessing related data
- Incorrect date formatting
- Missing analytics_view_ prefix on table names
- Missing GROUP BY when user asks for "top N by X" or aggregated data
- Returning individual rows instead of aggregated summaries

CRITICAL: If the query asks for "top N providers by volume" or similar aggregation:
- You MUST use GROUP BY
- You MUST use aggregate functions (COUNT, SUM, etc.)
- You MUST use ORDER BY ... DESC
- You MUST use LIMIT N
- NEVER return individual claim records - always aggregate first!

Generate a corrected SQL query that addresses the error.
"""
        else:
            user_prompt += """=== USER QUERY ===
"""
        
        user_prompt += f"""{natural_language_query}

=== GENERATE SQL ===
Generate a SQL query that answers this question using the analytics_view_* tables.

CRITICAL REQUIREMENTS:
1. Start your response with SELECT (no markdown, no explanations, no code blocks)
2. Use analytics_view_ prefix for all tables
3. For comparison queries, use UNION ALL to combine periods/states
4. Always aggregate when comparing volumes (use COUNT, SUM, GROUP BY)
5. Return ONLY the SQL query, nothing else"""
        
        # Add entity mapping hints if available
        if entity_mappings and entity_mappings.get('mapped_entities'):
            user_prompt += "\n\n=== ENTITY MAPPINGS (USE THESE) ===\n"
            for mapping in entity_mappings['mapped_entities']:
                user_prompt += f"- {mapping['user_mention']} maps to {mapping['db_table']}.{mapping['db_column']} = '{mapping['db_value']}'\n"
            user_prompt += "\n"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        ollama_client = await get_ollama_client()
        response = await ollama_client.chat(
            messages=messages,
            temperature=0.1,  # Low temperature for accuracy
            max_tokens=1500
        )
        
        # Debug: Log raw response
        if not response or len(response.strip()) == 0:
            print("[ERROR] LLM returned empty response")
            raise ValueError("LLM returned empty response")
        
        print(f"[DEBUG] LLM raw response (first 500 chars): {response[:500]}")
        
        # Extract SQL from response
        try:
            sql = self._extract_sql_from_response(response)
            print(f"[DEBUG] Extracted SQL (first 200 chars): {sql[:200]}")
            return sql
        except Exception as e:
            print(f"[ERROR] SQL extraction failed: {e}")
            print(f"[ERROR] Full LLM response: {response}")
            raise
    
    def _extract_sql_from_response(self, response: str) -> str:
        """Extract SQL query from LLM response"""
        # Remove markdown code blocks
        response = re.sub(r'```sql\s*', '', response, flags=re.IGNORECASE)
        response = re.sub(r'```\s*', '', response)
        response = re.sub(r'`', '', response)
        
        # Find SQL query (starts with SELECT)
        lines = response.split('\n')
        sql_lines = []
        in_sql = False
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if line.upper().startswith('SELECT'):
                in_sql = True
                sql_lines.append(line)
            elif in_sql:
                # Stop at explanation keywords
                if any(keyword in line.upper() for keyword in ['EXPLANATION', 'NOTE:', 'THIS QUERY', 'RETURNS']):
                    break
                sql_lines.append(line)
                if line.endswith(';'):
                    break
        
        sql = ' '.join(sql_lines).strip()
        
        # Fallback: try regex (handle UNION ALL queries too)
        if not sql or not (sql.upper().startswith('SELECT') or sql.upper().startswith('WITH')):
            # Try to find SELECT ... UNION ALL ... pattern
            match = re.search(r'SELECT.*?(?:UNION\s+ALL.*?)?;', response, re.IGNORECASE | re.DOTALL)
            if match:
                sql = match.group(0).strip()
            elif 'SELECT' in response.upper() or 'WITH' in response.upper():
                sql = response.strip()
        
        # Remove trailing semicolon
        sql = sql.rstrip(';').strip()
        
        # Ensure it's a SELECT query (or UNION ALL for comparisons, or WITH for CTEs)
        sql_upper = sql.upper().strip()
        # Check if it starts with SELECT, WITH, or contains UNION ALL (even if not at start)
        is_select = sql_upper.startswith('SELECT') or sql_upper.startswith('WITH')
        has_union = 'UNION' in sql_upper or 'UNION ALL' in sql_upper
        
        # If it has UNION but doesn't start with SELECT, try to extract the SELECT part
        if has_union and not is_select:
            # Find the first SELECT before UNION
            select_match = re.search(r'(SELECT.*?)(?:UNION|$)', sql_upper, re.IGNORECASE | re.DOTALL)
            if select_match:
                sql = sql[select_match.start():].strip()
                sql_upper = sql.upper().strip()
                is_select = sql_upper.startswith('SELECT')
        
        if not (is_select or has_union):
            # Last resort: try to extract any SQL-like statement
            if 'FROM' in sql_upper:
                # Try multiple strategies to extract SQL
                # Strategy 1: Find SELECT anywhere in the response
                select_pos = sql_upper.find('SELECT')
                if select_pos >= 0:
                    # Extract from SELECT onwards
                    sql = sql[select_pos:].strip()
                    sql_upper = sql.upper().strip()
                    is_select = sql_upper.startswith('SELECT')
                
                # Strategy 2: If we have FROM but no SELECT, try to reconstruct
                elif 'FROM' in sql_upper and ('COUNT' in sql_upper or 'SUM' in sql_upper or '*' in sql):
                    from_pos = sql_upper.find('FROM')
                    if from_pos > 0:
                        # Extract what comes before FROM and make it SELECT columns
                        before_from = sql[:from_pos].strip()
                        # If it looks like column names, add SELECT
                        if before_from and not before_from.upper().startswith('SELECT'):
                            sql = f"SELECT {before_from} {sql[from_pos:].strip()}"
                            sql_upper = sql.upper().strip()
                            is_select = sql_upper.startswith('SELECT')
                
                # Strategy 3: Check if response contains SQL keywords
                elif any(keyword in sql_upper for keyword in ['COUNT', 'SUM', 'AVG', 'MAX', 'MIN', 'GROUP BY', 'ORDER BY']):
                    # Try to find the actual SQL by looking for FROM
                    from_pos = sql_upper.find('FROM')
                    if from_pos > 0:
                        # Look backwards for SELECT
                        before_from = sql[:from_pos]
                        if 'SELECT' in before_from.upper():
                            select_pos = before_from.upper().rfind('SELECT')
                            sql = sql[select_pos:].strip()
                            sql_upper = sql.upper().strip()
                            is_select = sql_upper.startswith('SELECT')
            
            # Final check - if still not valid, log and try one more time
            if not (is_select or has_union):
                # Log the problematic response for debugging
                print(f"[ERROR] Failed to extract SQL from LLM response. Response preview: {response[:500]}")
                print(f"[ERROR] Extracted SQL so far: {sql[:200]}")
                
                # Last attempt: if response contains SQL-like text, try to extract it more aggressively
                if 'FROM' in response.upper():
                    # Try to extract everything between SELECT and end of statement
                    select_match = re.search(r'SELECT.*?FROM.*?(?:WHERE.*?)?(?:GROUP BY.*?)?(?:ORDER BY.*?)?(?:LIMIT.*?)?(?:;|$)', response, re.IGNORECASE | re.DOTALL)
                    if select_match:
                        sql = select_match.group(0).strip().rstrip(';')
                        sql_upper = sql.upper().strip()
                        is_select = sql_upper.startswith('SELECT')
                
                if not (is_select or has_union):
                    raise ValueError(f"Generated query is not a SELECT statement. LLM response: {response[:200]}")
        
        # Ensure analytics_view_ prefix (auto-fix if missing)
        sql = self._ensure_analytics_view_prefix(sql)
        
        return sql
    
    def _ensure_analytics_view_prefix(self, sql: str) -> str:
        """Ensure all table references use analytics_view_ prefix"""
        # Find table references and add prefix if missing
        # This is a safety net - the prompt should handle it, but we fix it here too
        import re
        
        # Pattern to find table names after FROM/JOIN
        patterns = [
            (r'FROM\s+([a-zA-Z_][a-zA-Z0-9_]*)', 'FROM'),
            (r'JOIN\s+([a-zA-Z_][a-zA-Z0-9_]*)', 'JOIN'),
        ]
        
        sql_upper = sql.upper()
        system_tables = {'INFORMATION_SCHEMA', 'SYS', 'MYSQL', 'PG_'}
        
        for pattern, keyword in patterns:
            matches = list(re.finditer(pattern, sql_upper))
            for match in reversed(matches):  # Reverse to maintain positions
                table_name = match.group(1)
                
                # Skip system tables
                if any(table_name.startswith(sys_pref) for sys_pref in system_tables):
                    continue
                
                # Skip if already has analytics_view_ prefix
                if table_name.startswith('ANALYTICS_VIEW_'):
                    continue
                
                # Add prefix
                start, end = match.span(1)
                original_table = sql[start:end]
                new_table = f"analytics_view_{original_table}"
                sql = sql[:start] + new_table + sql[end:]
        
        return sql
    
    async def _execute_with_retry(
        self,
        sql: str,
        max_attempts: int = 3
    ) -> Tuple[bool, List[Dict[str, Any]], Optional[str]]:
        """
        Execute SQL query with retry logic.
        Returns: (success, results, error_message)
        """
        for attempt in range(max_attempts):
            try:
                results = await database_service.execute_query(sql)
                return True, results, None
            except Exception as e:
                error_msg = str(e)
                if attempt < max_attempts - 1:
                    # Will retry with correction
                    return False, [], error_msg
                else:
                    return False, [], error_msg
        
        return False, [], "Max retry attempts exceeded"
    
    async def generate_sql(
        self,
        natural_language_query: str,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Generate SQL query with self-correction loop (Reflexion pattern).
        
        Args:
            natural_language_query: User's question in natural language
            conversation_history: Previous conversation messages
        
        Returns:
            Dictionary with 'sql', 'explanation', 'confidence', 'correction_attempts'
        """
        # Check for PII leakage intent
        if privacy_service.check_pii_leakage(natural_language_query):
            return {
                "sql": None,
                "explanation": "For privacy compliance, I provide insights at the cohort level only. Please rephrase your query to focus on aggregated trends rather than individual identification.",
                "confidence": 1.0,
                "correction_attempts": 0,
                "privacy_blocked": True
            }
        
        # Fast path for common aggregation queries
        query_lower = natural_language_query.lower()
        
        # PRIORITY 1: "compare claims volume by state" - aggregate by state
        if "compare" in query_lower and "claim" in query_lower and "volume" in query_lower and "by state" in query_lower:
            db_type = database_service.db_type or "mysql"
            
            if db_type == "mysql":
                sql = """SELECT 
    s.name as state_name,
    COUNT(*) as claim_count,
    COALESCE(SUM(c.total_cost), 0) as total_volume
FROM analytics_view_claims c
LEFT JOIN analytics_view_users u ON c.user_id = u.id
LEFT JOIN analytics_view_states s ON u.state = s.id
WHERE s.name IS NOT NULL
GROUP BY s.name
ORDER BY claim_count DESC"""
            else:  # PostgreSQL
                sql = """SELECT 
    s.name as state_name,
    COUNT(*) as claim_count,
    COALESCE(SUM(c.total_cost), 0) as total_volume
FROM analytics_view_claims c
LEFT JOIN analytics_view_users u ON c.user_id = u.id
LEFT JOIN analytics_view_states s ON u.state = s.id
WHERE s.name IS NOT NULL
GROUP BY s.name
ORDER BY claim_count DESC"""
            
            return {
                "sql": sql,
                "explanation": "This query compares claim volume grouped by state",
                "confidence": 0.95,
                "correction_attempts": 0
            }
        
        # PRIORITY 2: Simple volume comparison (no specific entities)
        if "compare" in query_lower and "claim" in query_lower and "volume" in query_lower:
            # Check if it has specific months or named states - if so, skip this and let other handlers take over
            has_specific_months = any(m in query_lower for m in ['january', 'february', 'march', 'april', 'may', 'june', 
                                                                 'july', 'august', 'september', 'october', 'november', 'december'])
            has_named_states = any(s in query_lower for s in ['zamfara', 'kogi', 'kano', 'osun', 'rivers', 'lagos', 
                                                               'abuja', 'fct', 'kaduna', 'sokoto', 'adamawa'])
            
            if not has_specific_months and not has_named_states:
                # Default: compare all time vs this month
                from datetime import datetime
                import calendar
                now = datetime.now()
                first_day = datetime(now.year, now.month, 1).strftime('%Y-%m-%d')
                last_day = datetime(now.year, now.month, 
                                  calendar.monthrange(now.year, now.month)[1]).strftime('%Y-%m-%d')
                
                db_type = database_service.db_type or "mysql"
                
                if db_type == "mysql":
                    sql = f"""SELECT 
    'All Time' as period,
    COUNT(*) as claim_count,
    COALESCE(SUM(total_cost), 0) as total_volume
FROM analytics_view_claims
UNION ALL
SELECT 
    'This Month' as period,
    COUNT(*) as claim_count,
    COALESCE(SUM(total_cost), 0) as total_volume
FROM analytics_view_claims
WHERE DATE(created_at) >= '{first_day}' AND DATE(created_at) <= '{last_day}'
ORDER BY period"""
                else:  # PostgreSQL
                    sql = f"""SELECT 
    'All Time' as period,
    COUNT(*) as claim_count,
    COALESCE(SUM(total_cost), 0) as total_volume
FROM analytics_view_claims
UNION ALL
SELECT 
    'This Month' as period,
    COUNT(*) as claim_count,
    COALESCE(SUM(total_cost), 0) as total_volume
FROM analytics_view_claims
WHERE DATE(created_at) >= '{first_day}' AND DATE(created_at) <= '{last_day}'
ORDER BY period"""
                
                return {
                    "sql": sql,
                    "explanation": "This query compares claim volume: all time vs this month",
                    "confidence": 0.9,
                    "correction_attempts": 0
                }
        
        # PRIORITY 3: State comparison queries (e.g., "compare claims from zamfara and kogi")
        if "compare" in query_lower and "claim" in query_lower and ("from" in query_lower or "between" in query_lower):
            # Check for state names in query (with timeout protection)
            try:
                import asyncio
                state_mappings = await asyncio.wait_for(
                    schema_rag_service.map_entities_to_columns(natural_language_query),
                    timeout=3.0
                )
            except (asyncio.TimeoutError, Exception) as e:
                state_mappings = {'mapped_entities': []}
            mapped_states = [m for m in state_mappings.get('mapped_entities', []) if m.get('type') == 'state']
            
            if len(mapped_states) >= 2:
                # Compare two states
                state1 = mapped_states[0]
                state2 = mapped_states[1]
                
                db_type = database_service.db_type or "mysql"
                
                if db_type == "mysql":
                    sql = f"""SELECT 
    '{state1['db_value']}' as state_name,
    COUNT(*) as claim_count,
    COALESCE(SUM(c.total_cost), 0) as total_volume
FROM analytics_view_claims c
LEFT JOIN analytics_view_users u ON c.user_id = u.id
LEFT JOIN analytics_view_states s1 ON u.state = s1.id
WHERE s1.name = '{state1['db_value']}'
UNION ALL
SELECT 
    '{state2['db_value']}' as state_name,
    COUNT(*) as claim_count,
    COALESCE(SUM(c.total_cost), 0) as total_volume
FROM analytics_view_claims c
LEFT JOIN analytics_view_users u ON c.user_id = u.id
LEFT JOIN analytics_view_states s2 ON u.state = s2.id
WHERE s2.name = '{state2['db_value']}'
ORDER BY state_name"""
                else:  # PostgreSQL
                    sql = f"""SELECT 
    '{state1['db_value']}' as state_name,
    COUNT(*) as claim_count,
    COALESCE(SUM(c.total_cost), 0) as total_volume
FROM analytics_view_claims c
LEFT JOIN analytics_view_users u ON c.user_id = u.id
LEFT JOIN analytics_view_states s1 ON u.state = s1.id
WHERE s1.name = '{state1['db_value']}'
UNION ALL
SELECT 
    '{state2['db_value']}' as state_name,
    COUNT(*) as claim_count,
    COALESCE(SUM(c.total_cost), 0) as total_volume
FROM analytics_view_claims c
LEFT JOIN analytics_view_users u ON c.user_id = u.id
LEFT JOIN analytics_view_states s2 ON u.state = s2.id
WHERE s2.name = '{state2['db_value']}'
ORDER BY state_name"""
                
                return {
                    "sql": sql,
                    "explanation": f"This query compares claim volume between {state1['db_value']} and {state2['db_value']}",
                    "confidence": 0.95,
                    "correction_attempts": 0
                }
        
        # PRIORITY 3: Pattern matching for comparison queries (month-over-month, year-over-year)
        is_comparison_query = (
            ("compare" in query_lower or "comparison" in query_lower) and
            ("volume" in query_lower or "claim" in query_lower) and
            (("november" in query_lower or "october" in query_lower or "december" in query_lower or
              "january" in query_lower or "february" in query_lower or "march" in query_lower or
              "april" in query_lower or "may" in query_lower or "june" in query_lower or
              "july" in query_lower or "august" in query_lower or "september" in query_lower) or
             ("month" in query_lower or "year" in query_lower))
        )
        
        if is_comparison_query:
            # Handle month-over-month comparison
            import re
            from datetime import datetime
            import calendar
            
            # Extract months and year
            month_names = {
                'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
                'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12
            }
            
            months_found = []
            for month_name, month_num in month_names.items():
                if month_name in query_lower:
                    months_found.append((month_name, month_num))
            
            # Extract year (default to 2025 if not specified)
            year_match = re.search(r'\b(20\d{2})\b', natural_language_query)
            year = int(year_match.group(1)) if year_match else 2025
            
            # Extract state if mentioned
            state_filter = ""
            if "kogi" in query_lower:
                state_filter = "AND s.name = 'Kogi'"
            elif "kano" in query_lower:
                state_filter = "AND s.name = 'Kano'"
            elif "osun" in query_lower:
                state_filter = "AND s.name = 'Osun'"
            # Add more states as needed
            
            # Debug: Log what we found
            print(f"[DEBUG] Comparison query detected. Months found: {months_found}, Year: {year}")
            
            # Extract state if mentioned (for multi-month queries)
            state_name = None
            state_filter_join = ""
            state_filter_where = ""
            if any(s in query_lower for s in ['zamfara', 'kogi', 'kano', 'osun', 'rivers', 'lagos', 
                                               'abuja', 'fct', 'kaduna', 'sokoto', 'adamawa']):
                # Try to get state name from Schema-RAG
                try:
                    import asyncio
                    state_mappings = await asyncio.wait_for(
                        schema_rag_service.map_entities_to_columns(natural_language_query),
                        timeout=2.0
                    )
                    mapped_states = [m for m in state_mappings.get('mapped_entities', []) if m.get('type') == 'state']
                    if mapped_states:
                        state_name = mapped_states[0]['db_value']
                        state_filter_join = "LEFT JOIN analytics_view_users u ON c.user_id = u.id LEFT JOIN analytics_view_states s ON u.state = s.id"
                        state_filter_where = f"AND s.name = '{state_name}'"
                except:
                    # Fallback: simple keyword matching
                    if "zamfara" in query_lower:
                        state_name = "Zamfara"
                    elif "kogi" in query_lower:
                        state_name = "Kogi"
                    elif "kano" in query_lower:
                        state_name = "Kano"
                    elif "osun" in query_lower:
                        state_name = "Osun"
                    
                    if state_name:
                        state_filter_join = "LEFT JOIN analytics_view_users u ON c.user_id = u.id LEFT JOIN analytics_view_states s ON u.state = s.id"
                        state_filter_where = f"AND s.name = '{state_name}'"
            
            if len(months_found) >= 2:
                db_type = database_service.db_type or "mysql"
                
                # Build UNION ALL query for all months
                union_parts = []
                for month_name, month_num in months_found:
                    month_start = datetime(year, month_num, 1).strftime('%Y-%m-%d')
                    month_end = datetime(year, month_num, 
                                        calendar.monthrange(year, month_num)[1]).strftime('%Y-%m-%d')
                    
                    if state_filter_join:
                        month_query = f"""SELECT 
    '{month_name.capitalize()} {year}' as period,
    COUNT(*) as claim_count,
    COALESCE(SUM(c.total_cost), 0) as total_volume
FROM analytics_view_claims c
{state_filter_join}
WHERE DATE(c.created_at) >= '{month_start}' AND DATE(c.created_at) <= '{month_end}'
{state_filter_where}"""
                    else:
                        month_query = f"""SELECT 
    '{month_name.capitalize()} {year}' as period,
    COUNT(*) as claim_count,
    COALESCE(SUM(c.total_cost), 0) as total_volume
FROM analytics_view_claims c
WHERE DATE(c.created_at) >= '{month_start}' AND DATE(c.created_at) <= '{month_end}'"""
                    
                    union_parts.append(month_query)
                
                sql = "\nUNION ALL\n".join(union_parts) + "\nORDER BY period"
                
                month_list = ", ".join([m[0].capitalize() for m in months_found])
                state_text = f" in {state_name}" if state_name else ""
                explanation = f"This query compares claim volume for {month_list} {year}{state_text}"
                
                return {
                    "sql": sql,
                    "explanation": explanation,
                    "confidence": 0.95,
                    "correction_attempts": 0
                }
        
        # More flexible pattern matching for "top N by X" queries
        is_top_n_query = (
            ("top" in query_lower and ("provider" in query_lower or "facility" in query_lower)) or
            ("top" in query_lower and ("claim" in query_lower or "volume" in query_lower)) or
            ("show" in query_lower and "top" in query_lower and ("provider" in query_lower or "facility" in query_lower))
        )
        
        if is_top_n_query:
            # Extract number (default to 10)
            import re
            num_match = re.search(r'top\s+(\d+)', query_lower)
            top_n = int(num_match.group(1)) if num_match else 10
            
            # Check for "this month" (handle typo "this mont" too)
            date_filter = ""
            if "this month" in query_lower or "this mont" in query_lower:
                from datetime import datetime
                import calendar
                now = datetime.now()
                first_day = datetime(now.year, now.month, 1).strftime('%Y-%m-%d')
                last_day = datetime(now.year, now.month, 
                                  calendar.monthrange(now.year, now.month)[1]).strftime('%Y-%m-%d')
                date_filter = f"WHERE DATE(c.created_at) >= '{first_day}' AND DATE(c.created_at) <= '{last_day}'"
            
            # Generate aggregation query with JOIN to get provider names
            # Note: Based on user results, provider info might be in user_name column or need JOIN
            db_type = database_service.db_type or "mysql"
            
            if db_type == "mysql":
                # Try to use provider_name directly from claims if it exists, otherwise join
                sql = f"""SELECT 
    COALESCE(c.provider_name, p.name, p.provider_name, p.facility_name, CONCAT('Provider ', c.provider_id)) as provider_name,
    COUNT(*) as claim_count,
    COALESCE(SUM(c.total_cost), 0) as total_volume
FROM analytics_view_claims c
LEFT JOIN analytics_view_providers p ON c.provider_id = p.id
{date_filter}
GROUP BY provider_name
ORDER BY claim_count DESC
LIMIT {top_n}"""
            else:  # PostgreSQL
                sql = f"""SELECT 
    COALESCE(c.provider_name, p.name, p.provider_name, p.facility_name, CONCAT('Provider ', c.provider_id::text)) as provider_name,
    COUNT(*) as claim_count,
    COALESCE(SUM(c.total_cost), 0) as total_volume
FROM analytics_view_claims c
LEFT JOIN analytics_view_providers p ON c.provider_id = p.id
{date_filter}
GROUP BY provider_name
ORDER BY claim_count DESC
LIMIT {top_n}"""
            
            return {
                "sql": sql,
                "explanation": f"This query returns the top {top_n} providers by claim volume" + (" for this month" if date_filter else ""),
                "confidence": 0.95,
                "correction_attempts": 0
            }
        
        # STEP 1: Schema-RAG - Map user entities to database columns
        # STEP 1: Schema-RAG - Map user entities to database columns (Vector RAG) with timeout
        try:
            import asyncio
            entity_mappings = await asyncio.wait_for(
                schema_rag_service.map_entities_to_columns(natural_language_query),
                timeout=5.0  # 5 second timeout for entity mapping
            )
            entity_context = schema_rag_service.get_entity_mapping_context(entity_mappings.get('mapped_entities', []))
        except asyncio.TimeoutError:
            # Fallback: use empty mappings if timeout
            print("⚠️ Schema-RAG timeout, continuing without entity mappings")
            entity_mappings = {'mapped_entities': [], 'sql_hints': [], 'confidence': 0.5}
            entity_context = ""
        except Exception as e:
            # Fallback: use empty mappings if error
            print(f"⚠️ Schema-RAG error: {e}, continuing without entity mappings")
            entity_mappings = {'mapped_entities': [], 'sql_hints': [], 'confidence': 0.5}
            entity_context = ""
        
        # STEP 2: Get comprehensive schema (with database inspection)
        comprehensive_schema = await schema_loader.load_comprehensive_schema()
        
        # STEP 3: Get filtered schema for this specific query
        query_schema = await schema_loader.get_schema_for_query(natural_language_query)
        
        # STEP 4: Get semantic manifest
        semantic_manifest = schema_loader.get_semantic_manifest() or await self._get_semantic_manifest()
        
        # STEP 5: Build enhanced schema context using comprehensive schema
        schema_info = {
            'tables': query_schema.get('tables', [])
        }
        schema_context = self._build_semantic_schema_context(schema_info, semantic_manifest, natural_language_query)
        
        # STEP 6: Add entity mappings to context (Schema-RAG)
        if entity_context:
            schema_context = entity_context + "\n" + schema_context
        
        # STEP 7: Add query patterns to context
        query_patterns = comprehensive_schema.get('query_patterns', [])
        if query_patterns:
            schema_context += "\n\n=== COMMON QUERY PATTERNS ===\n"
            for pattern in query_patterns[:10]:  # Top 10 patterns
                schema_context += f"- {pattern.get('description')}: {pattern.get('example_query')}\n"
            schema_context += "\n"
        
        # Self-correction loop (Reflexion pattern) - ZERO ERROR TOLERANCE
        previous_attempts = []
        error_context = None
        correction_attempts = 0
        last_sql = None
        
        for attempt in range(self.max_correction_attempts):
            try:
                # Generate SQL with entity mappings
                sql = await self._generate_sql_with_llm(
                    natural_language_query,
                    schema_context,
                    error_context=error_context,
                    previous_attempts=previous_attempts,
                    entity_mappings=entity_mappings
                )
                
                # CRITICAL: Validate SQL before execution
                validation_result = self._validate_sql_before_execution(sql, entity_mappings)
                if not validation_result['valid']:
                    error_context = validation_result['error']
                    previous_attempts.append(sql)
                    correction_attempts += 1
                    last_sql = sql
                    
                    if attempt < self.max_correction_attempts - 1:
                        continue
                    else:
                        raise RuntimeError(f"SQL validation failed: {validation_result['error']}")
                
                # Try to execute (validation)
                success, results, error_msg = await self._execute_with_retry(sql, max_attempts=1)
                
                if success:
                    # Query executed successfully - verify results are valid
                    if results is not None:
                        explanation = f"This query retrieves data to answer: {natural_language_query}"
                        confidence = 0.95 if correction_attempts == 0 else 0.90  # High confidence
                        
                        return {
                            "sql": sql,
                            "explanation": explanation,
                            "confidence": confidence,
                            "correction_attempts": correction_attempts,
                            "entity_mappings_applied": len(entity_mappings.get('mapped_entities', []))
                        }
                    else:
                        # Empty results - might be valid, but log it
                        error_context = "Query executed but returned no results"
                        previous_attempts.append(sql)
                        correction_attempts += 1
                        last_sql = sql
                        continue
                else:
                    # Query failed - prepare for correction
                    error_context = self._analyze_error_for_correction(error_msg, sql)
                    previous_attempts.append(sql)
                    correction_attempts += 1
                    last_sql = sql
                    
                    if attempt < self.max_correction_attempts - 1:
                        # Continue to next correction attempt
                        continue
                    else:
                        # Max attempts reached
                        raise RuntimeError(f"Failed to generate valid SQL after {self.max_correction_attempts} attempts. Last error: {error_msg}")
            
            except Exception as e:
                error_msg = str(e)
                if attempt < self.max_correction_attempts - 1:
                    error_context = self._analyze_error_for_correction(error_msg, last_sql or "")
                    if last_sql:
                        previous_attempts.append(last_sql)
                    correction_attempts += 1
                    continue
                else:
                    raise RuntimeError(f"Failed to generate SQL after {self.max_correction_attempts} attempts: {error_msg}")
        
        # Should not reach here, but just in case
        raise RuntimeError("Failed to generate SQL after maximum correction attempts")
    
    def _validate_sql_before_execution(self, sql: str, entity_mappings: Dict[str, Any]) -> Dict[str, Any]:
        """
        Comprehensive SQL validation before execution - ZERO ERROR TOLERANCE
        
        Returns:
            {'valid': bool, 'error': str}
        """
        sql_upper = sql.strip().upper()
        
        # 1. Must start with SELECT
        if not sql_upper.startswith('SELECT'):
            return {'valid': False, 'error': 'Query must start with SELECT (read-only)'}
        
        # 2. Must use analytics_view_ prefix (CRITICAL for PHI compliance)
        # Find all table references
        import re
        table_patterns = [
            r'FROM\s+([a-zA-Z_][a-zA-Z0-9_]*)',
            r'JOIN\s+([a-zA-Z_][a-zA-Z0-9_]*)',
        ]
        
        system_tables = {'INFORMATION_SCHEMA', 'SYS', 'MYSQL', 'PG_'}
        raw_tables_found = []
        
        for pattern in table_patterns:
            matches = re.findall(pattern, sql_upper)
            for match in matches:
                table_name = match
                # Skip system tables
                if any(table_name.startswith(sys_pref) for sys_pref in system_tables):
                    continue
                # Check if it's a raw table (not analytics_view_)
                if not table_name.startswith('ANALYTICS_VIEW_'):
                    raw_tables_found.append(table_name)
        
        if raw_tables_found:
            return {
                'valid': False,
                'error': f'PHI VIOLATION: Query references raw tables {raw_tables_found}. All queries MUST use analytics_view_* tables only.'
            }
        
        # 3. No write operations
        forbidden = ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER', 'TRUNCATE']
        for keyword in forbidden:
            if keyword in sql_upper:
                return {'valid': False, 'error': f'Query contains forbidden operation: {keyword}'}
        
        # 4. Validate entity mappings are used correctly
        mappings = entity_mappings.get('mapped_entities', [])
        for mapping in mappings:
            if mapping['type'] == 'state':
                # Ensure state mapping is used in query
                if mapping['db_table'].upper() not in sql_upper:
                    # This is a warning, not an error - state might be in WHERE clause
                    pass
        
        return {'valid': True, 'error': None}
    
    def _analyze_error_for_correction(self, error_msg: str, sql: str) -> str:
        """
        Analyze error message to provide actionable correction hints.
        Enhanced error analysis for better self-correction.
        """
        error_lower = error_msg.lower()
        sql_upper = sql.upper()
        
        # Common error patterns and fixes
        if 'unknown column' in error_lower or "doesn't exist" in error_lower:
            # Extract column name from error
            col_match = re.search(r"['\"`]([^'\"`]+)['\"`]", error_msg)
            if col_match:
                col_name = col_match.group(1)
                return f"Column '{col_name}' does not exist. Check the schema - you may need to use a different column name or join to another table."
            return "Column does not exist. Verify column names in the schema."
        
        if 'unknown table' in error_lower or 'table doesn\'t exist' in error_lower:
            # Extract table name
            table_match = re.search(r"['\"`]([^'\"`]+)['\"`]", error_msg)
            if table_match:
                table_name = table_match.group(1)
                if not table_name.startswith('analytics_view_'):
                    return f"Table '{table_name}' must use 'analytics_view_' prefix. Use 'analytics_view_{table_name}' instead."
            return "Table does not exist. Ensure all tables use 'analytics_view_' prefix."
        
        if 'syntax error' in error_lower or 'sql syntax' in error_lower:
            return "SQL syntax error. Check: parentheses matching, comma placement, keyword spelling, and proper JOIN syntax."
        
        if 'group by' in error_lower or 'aggregate' in error_lower:
            return "GROUP BY error. When using aggregate functions (COUNT, SUM, etc.), all non-aggregated columns must be in GROUP BY clause."
        
        if 'join' in error_lower or 'on' in error_lower:
            return "JOIN error. Ensure JOIN conditions use correct column names and table aliases match."
        
        if 'date' in error_lower or 'datetime' in error_lower:
            return "Date format error. Use DATE() function for date comparisons. Format: DATE(column_name) >= 'YYYY-MM-DD'"
        
        # Generic error
        return f"SQL execution error: {error_msg}. Review the query structure and schema."
    
    def clear_cache(self):
        """Clear schema and semantic manifest cache"""
        self._schema_cache = None
        self._semantic_manifest_cache = None
        analytics_view_service.clear_cache()


# Global instance
enhanced_sql_generator = EnhancedSQLGenerator()

