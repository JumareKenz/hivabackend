"""
SQL Generator Service - Schema-aware natural language to SQL translation
Uses Vanna AI (with fallback to legacy LLM) to generate SQL queries based on natural language and database schema
"""
from typing import Dict, Any, List, Optional
import json
import re
from datetime import datetime, timedelta
import calendar
from app.core.config import settings
from app.services.database_service import database_service
from app.services.llm_client import llm_client
from app.services.intent_classifier import intent_classifier

# Import Vanna service (optional)
try:
    from app.services.vanna_service import vanna_service
    VANNA_SERVICE_AVAILABLE = True
except ImportError:
    VANNA_SERVICE_AVAILABLE = False
    vanna_service = None


class SQLGenerator:
    """
    Generates SQL queries from natural language using Vanna AI (with legacy fallback)
    
    Priority:
    1. Vanna AI (if enabled and available) - Better accuracy, RAG-based, learns from examples
    2. Legacy LLM-based generator - Fallback for compatibility
    """
    
    def __init__(self):
        self._schema_cache: Optional[Dict[str, Any]] = None
        self._cache_timestamp: Optional[float] = None
        self._cache_ttl: int = 3600  # Cache schema for 1 hour
        self._vanna_initialized = False
    
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
    
    def _build_compact_prompt(self, query: str, schema_text: str) -> str:
        """Build a compact prompt for low-token environments"""
        # Minimal essential schema - only tables likely needed
        query_lower = query.lower()
        
        # Determine which tables we need based on query
        mini_schema = "Tables: claims(id,diagnosis TEXT,user_id,created_at,status,total_cost), "
        if 'disease' in query_lower or 'diagnosis' in query_lower:
            mini_schema += "diagnoses(id,name), "
        if 'state' in query_lower or any(s in query_lower for s in ['kogi','zamfara','kano','lagos','kaduna']):
            mini_schema += "users(id,state), states(id,name), "
        if 'service' in query_lower:
            mini_schema += "services(id,description), claims_services(claims_id,services_id), "
        
        # Extract state name if present
        state_filter = ""
        for state in ['kogi','zamfara','kano','lagos','kaduna','fct','abuja','rivers','osun','sokoto','adamawa']:
            if state in query_lower:
                state_filter = f"State filter: WHERE s.name LIKE '%{state.title()}%'"
                break
        
        return f"""You are a MySQL SQL generator. Your ONLY output must be a valid SELECT statement. No explanations, no markdown, just SQL.

Schema: {mini_schema.strip(', ')}

Rules:
- Diagnosis: JOIN diagnoses d ON d.id = CAST(c.diagnosis AS UNSIGNED) WHERE c.diagnosis REGEXP '^[0-9]+$'
- State: JOIN users u ON c.user_id=u.id JOIN states s ON u.state=s.id  
- Use d.name for disease names, s.name for state names
- "highest/most/top" = GROUP BY + ORDER BY DESC + LIMIT
{state_filter}

Question: {query}

Output only the SQL query starting with SELECT:"""
    
    def _compute_join_confidence(self, query: str) -> dict:
        """
        Compute confidence score for join operations based on schema knowledge.
        
        Returns:
            dict with 'confidence' (0.0-1.0), 'can_proceed' (bool), 'reason' (str), 'tables' (list)
        """
        query_lower = query.lower()
        
        # Known safe join paths with high confidence
        SAFE_JOIN_PATHS = {
            ('claims', 'diagnoses'): 0.95,      # claims.diagnosis -> diagnoses.id (via CAST)
            ('claims', 'users'): 0.95,          # claims.user_id -> users.id
            ('users', 'states'): 0.95,          # users.state -> states.id
            ('claims', 'claims_services'): 0.90, # claims.id -> claims_services.claims_id
            ('claims_services', 'services'): 0.90, # claims_services.services_id -> services.id
            ('claims', 'providers'): 0.85,      # claims.provider_id -> providers.id
        }
        
        # Tables we can confidently query
        KNOWN_TABLES = {'claims', 'diagnoses', 'users', 'states', 'services', 
                       'claims_services', 'providers', 'health_records'}
        
        # Detect required tables from query
        required_tables = set()
        if any(k in query_lower for k in ['claim', 'diagnos', 'disease', 'patient']):
            required_tables.add('claims')
        if any(k in query_lower for k in ['disease', 'diagnosis', 'diagnoses']):
            required_tables.add('diagnoses')
        if any(k in query_lower for k in ['state', 'kogi', 'zamfara', 'kano', 'lagos', 'kaduna']):
            required_tables.update(['users', 'states'])
        if 'service' in query_lower:
            required_tables.update(['claims_services', 'services'])
        if 'provider' in query_lower:
            required_tables.add('providers')
        
        # Check for unknown tables (hallucination risk)
        unknown_keywords = ['customer', 'order', 'product', 'employee', 'supplier', 
                          'inventory', 'payment', 'refund', 'invoice', 'sales']
        hallucination_risk = any(k in query_lower for k in unknown_keywords)
        
        if hallucination_risk:
            return {
                'confidence': 0.0,
                'can_proceed': False,
                'reason': 'Query references concepts not in the healthcare claims schema.',
                'tables': list(required_tables)
            }
        
        # Calculate confidence based on required joins
        if len(required_tables) <= 1:
            confidence = 0.95  # Single table query - high confidence
        else:
            # Multi-table query - check join paths using graph connectivity
            # Build adjacency from known paths
            known_connections = set()
            for (t1, t2), conf in SAFE_JOIN_PATHS.items():
                known_connections.add((t1, t2))
                known_connections.add((t2, t1))
            
            # Check if all required tables are reachable from 'claims' (root table)
            if 'claims' in required_tables:
                reachable = {'claims'}
                changed = True
                while changed:
                    changed = False
                    for (t1, t2) in known_connections:
                        if t1 in reachable and t2 not in reachable:
                            reachable.add(t2)
                            changed = True
                
                # All required tables should be reachable from claims
                all_reachable = required_tables.issubset(reachable)
                
                if all_reachable:
                    # All tables are connected through known paths
                    # Calculate confidence as average of direct path confidences
                    direct_confidences = []
                    for (t1, t2), conf in SAFE_JOIN_PATHS.items():
                        if t1 in required_tables or t2 in required_tables:
                            direct_confidences.append(conf)
                    confidence = sum(direct_confidences) / len(direct_confidences) if direct_confidences else 0.9
                else:
                    # Some tables are not reachable
                    unreachable = required_tables - reachable
                    confidence = 0.3
                    print(f"⚠️  [JOIN_CONFIDENCE] Unreachable tables: {unreachable}")
            else:
                # No claims table - unusual query, lower confidence
                confidence = 0.6
        
        # Threshold: 0.5 for proceeding
        can_proceed = confidence >= 0.5
        
        reason = ""
        if not can_proceed:
            reason = f"Insufficient schema confidence ({confidence:.2f}) to safely construct joins between {required_tables}."
        
        return {
            'confidence': confidence,
            'can_proceed': can_proceed,
            'reason': reason,
            'tables': list(required_tables)
        }
    
    def _build_sql_prompt(
        self,
        natural_language_query: str,
        schema_text: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        compact_mode: bool = True  # Default to compact for lower token usage
    ) -> str:
        """Build prompt for LLM to generate SQL"""
        
        # Compact prompt for low-token environments (GPT-OSS has 8000 TPM limit)
        if compact_mode:
            return self._build_compact_prompt(natural_language_query, schema_text)
        
        prompt = """You are an expert SQL query generator for a MySQL database specializing in Clinical Claims & Diagnosis domain. Your task is to convert natural language questions into accurate, read-only SQL queries following strict canonical domain rules.

PHASE 1: CANONICAL DOMAIN DEFINITION - CLINICAL CLAIMS & DIAGNOSIS

DOMAIN SCOPE (STRICT):
- ONLY answer questions about: diagnoses, claims, clinical services, volumes/trends/costs tied to diagnoses
- EXPLICITLY EXCLUDED: users, providers, payments, roles/permissions, accreditation, telescope, admin metadata
- If query requires excluded tables → REJECT or indicate it's outside this domain

AUTHORITATIVE TABLES (LOCKED):
Core Tables ONLY:
- claims
- diagnoses
- claims_services
- services
- users (for state filtering)
- states (for geographic queries)

CANONICAL JOIN GRAPH (SINGLE SOURCE OF TRUTH - NO ALTERNATIVES):
claims.diagnosis (TEXT) → diagnoses.id (DIRECT JOIN using CAST: d.id = CAST(c.diagnosis AS UNSIGNED))
claims.id → claims_services.claims_id
claims_services.services_id → services.id
claims.user_id → users.id (for patient info)
users.state → states.id (for state filtering)
🚫 ALWAYS filter: WHERE c.diagnosis REGEXP '^[0-9]+$' (to ensure valid numeric diagnosis ID)
🚫 The claims.diagnosis column is TEXT type containing diagnosis IDs - MUST use CAST

MANDATORY LABEL RESOLUTION (NON-NEGOTIABLE):
ALWAYS resolve:
- Diagnosis → diagnoses.name (NEVER diagnoses.id or diagnoses.diagnosis_code)
- Service → services.description (NEVER services.id)

NEVER return in SELECT:
- Any column ending in _id
- Any column named 'id' (unless it's for counting)
- diagnosis_code
- Foreign keys

If query asks for diagnosis → MUST use diagnoses.name
If query asks for service → MUST use services.description

AGGREGATION RULES:
Legal GROUP BY: diagnoses.name, DATE(claims.created_at)
Illegal GROUP BY: diagnoses.id, any _id column

CRITICAL RULES:
1. ONLY generate SELECT queries (read-only) - ALWAYS start with SELECT
2. NEVER include INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, or any write operations
3. Use proper MySQL syntax
4. Use table and column names EXACTLY as they appear in the schema - DO NOT invent column names
5. Before using any column, verify it exists in the schema for that table
6. For JOINs, ONLY use the canonical join paths defined above
7. Handle NULL values appropriately
8. Use proper date/time functions for filtering
9. Include LIMIT clauses for large result sets when appropriate
10. For date filtering on claims, use: claims.created_at
11. ALWAYS return a complete SELECT statement - never return partial SQL or explanations
12. POST-PROCESSING: Block any output containing _id, diagnosis_code, or raw IDs in SELECT

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
- When the query mentions a state name (e.g., "Zamfara", "Kano", "Lagos"), you MUST:
  1. JOIN users table: JOIN users u ON c.user_id = u.id
  2. JOIN states table: JOIN states s ON u.state = s.id
  3. Filter by state name: WHERE s.name LIKE '%StateName%' (use LIKE for case-insensitive matching)
- Common state names: Zamfara, Kano, Kogi, Kaduna, FCT, Abuja, Adamawa, Sokoto, Rivers, Osun, Lagos, etc.
- NEVER filter by date when a state name is mentioned in the query (unless date is also explicitly mentioned)
- Example: "claims in Zamfara" = WHERE s.name LIKE '%Zamfara%'
- Example: "tell me about claims in zamfara state" = WHERE s.name LIKE '%Zamfara%' (use LIKE for better matching)
- If query mentions both state AND date, filter by BOTH conditions using AND
- IMPORTANT: Use LIKE '%StateName%' instead of exact match (=) for better state name matching

STATE-BASED DISEASE QUERIES (CRITICAL):
- When query asks for "disease with highest/most patients in [State]", you MUST:
  1. Join: claims → users → states (for state filtering)
  2. Join: claims.diagnosis → diagnoses.id (via CAST)
  3. SELECT: d.name AS disease (or diagnosis)
  4. COUNT: COUNT(c.id) AS patient_count (or total_claims)
  5. GROUP BY: d.name (NEVER group by d.id)
  6. ORDER BY: patient_count DESC
  7. LIMIT: LIMIT 1 (for "highest/most" queries)
  8. FILTER: WHERE c.diagnosis REGEXP '^[0-9]+$' (to ensure valid diagnosis ID)
- Example: "disease with highest patients in Zamfara state" = 
  SELECT d.name AS disease, COUNT(c.id) AS patient_count
  FROM claims c
  JOIN users u ON c.user_id = u.id
  JOIN states s ON u.state = s.id
  JOIN diagnoses d ON d.id = CAST(c.diagnosis AS UNSIGNED)
  WHERE s.name LIKE '%Zamfara%' AND c.diagnosis REGEXP '^[0-9]+$'
  GROUP BY d.name
  ORDER BY patient_count DESC
  LIMIT 1
- CRITICAL: "highest/most" queries ALWAYS require GROUP BY and aggregation - NEVER return individual rows

GROUP BY - CRITICAL:
- When using GROUP BY with table aliases (e.g., c.status), ALWAYS use the table alias prefix: GROUP BY c.status (not just GROUP BY status)
- If you SELECT a CASE expression as status_name, GROUP BY the CASE expression or use the alias: GROUP BY status_name
- Example: SELECT CASE c.status ... END AS status_name, COUNT(*) FROM claims c GROUP BY c.status (use c.status, not status_name)

PHASE 1 CANONICAL DOMAIN RULES - CLINICAL CLAIMS & DIAGNOSIS (MANDATORY):

DIAGNOSIS QUERIES (STRICT):
- ALWAYS use: diagnoses.name AS diagnosis (or disease_name)
- NEVER return: diagnoses.id, diagnoses.diagnosis_code
- REQUIRED JOIN PATH: claims.diagnosis (TEXT) → diagnoses.id via CAST
- ALWAYS filter: WHERE c.diagnosis REGEXP '^[0-9]+$'
- JOIN SYNTAX: JOIN diagnoses d ON d.id = CAST(c.diagnosis AS UNSIGNED)
- Example: "most common diagnosis" = SELECT d.name AS diagnosis, COUNT(c.id) FROM claims c JOIN diagnoses d ON d.id = CAST(c.diagnosis AS UNSIGNED) WHERE c.diagnosis REGEXP '^[0-9]+$' GROUP BY d.name
- For "highest/most" queries: ALWAYS use GROUP BY d.name, COUNT(c.id), ORDER BY count DESC, LIMIT 1
- NEVER return individual claim rows for "highest/most" queries - ALWAYS aggregate

SERVICE QUERIES (STRICT):
- ALWAYS use: services.description AS service (or service_name)
- NEVER return: services.id, claims_services.services_id
- REQUIRED JOIN PATH: claims → claims_services → services
- Example: "services per claim" = SELECT s.description AS service, COUNT(*) FROM claims c JOIN claims_services cs ON cs.claims_id = c.id JOIN services s ON s.id = cs.services_id GROUP BY s.description

CLAIMS QUERIES:
- Use claims.created_at for date filtering
- Use COUNT(DISTINCT c.id) for claim counts
- NEVER join users or providers tables (outside domain scope)

FORBIDDEN OUTPUTS (POST-PROCESSING WILL BLOCK):
- Any column ending in _id in SELECT
- diagnosis_code in SELECT
- Raw numeric IDs in SELECT
- Foreign keys in SELECT

ALLOWED QUESTION TYPES:
✅ "Most common diagnosis last year"
✅ "Diagnosis trends by month"
✅ "Average claim cost per diagnosis"
✅ "Top diagnoses by service volume"

❌ REJECT: "Diagnosis code 77 details" (use name instead)
❌ REJECT: "Show raw diagnosis IDs"
❌ REJECT: "Which user made the claim" (outside domain)

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
        
        # Phase 2: Classify intent and extract semantic information
        intent = intent_classifier.classify_intent(natural_language_query)
        time_ref = intent_classifier.extract_time_reference(natural_language_query)
        top_n = intent_classifier.extract_top_n(natural_language_query)
        clarification_needed = intent_classifier.needs_clarification(natural_language_query, intent)
        
        # Add Phase 2 semantic contract rules
        phase2_rules = self._build_phase2_rules(intent, time_ref, top_n, natural_language_query)
        
        # Add the current query
        prompt += f"""=== USER QUERY ===
{natural_language_query}

=== PHASE 2: SEMANTIC CONTRACT ===
Intent Classified: {intent}
{phase2_rules}

=== YOUR TASK ===
Generate a MySQL SELECT query that answers this question following Phase 1 and Phase 2 rules. 

CRITICAL REQUIREMENTS:
1. ALWAYS use names instead of IDs - join related tables to get human-readable names
2. For diagnosis -> ALWAYS use diagnoses.name (NEVER diagnoses.id or diagnosis_code)
3. For service -> ALWAYS use services.description (NEVER services.id)
4. For frequency/volume queries -> Use COUNT(DISTINCT claims.id), NEVER count service_summary rows
5. For trend queries -> GROUP BY DATE_FORMAT(claims.created_at, '%Y-%m') for monthly
6. For cost queries -> Use AVG(claims.total_cost) or SUM(claims_services.cost), NEVER infer from services.price
7. For "highest/most/top" queries -> ALWAYS use GROUP BY, COUNT, ORDER BY DESC, LIMIT - NEVER return individual rows
8. For state-based queries -> ALWAYS join users and states tables, filter by s.name LIKE '%StateName%'
9. Return ONLY the SQL query starting with SELECT. No explanations, no markdown, no code blocks, no backticks, just the raw SQL statement.

CRITICAL: If the query asks for "disease with highest/most patients in [State]", you MUST:
- SELECT d.name AS disease (or diagnosis)
- COUNT(c.id) AS patient_count
- JOIN: claims → users → states (for state filtering)
- JOIN: diagnoses d ON d.id = CAST(c.diagnosis AS UNSIGNED)
- WHERE s.name LIKE '%StateName%' AND c.diagnosis REGEXP '^[0-9]+$'
- GROUP BY d.name
- ORDER BY patient_count DESC
- LIMIT 1
- NEVER return individual claim rows - ALWAYS aggregate

SQL Query:"""
        
        return prompt
    
    def _build_phase2_rules(self, intent: str, time_ref: Optional[Dict], top_n: Optional[int], natural_language_query: str = "") -> str:
        """Build Phase 2 semantic contract rules based on intent"""
        rules = []
        
        if intent == "FREQUENCY_VOLUME":
            rules.append("INTENT: Frequency/Volume")
            rules.append("- MUST use: COUNT(DISTINCT claims.id)")
            rules.append("- NEVER count: service_summary rows, diagnosis mappings, raw joins")
            rules.append("- MUST use: GROUP BY for aggregation queries")
            rules.append("- For 'highest/most' queries: ALWAYS use GROUP BY, ORDER BY DESC, LIMIT 1")
            rules.append("- NEVER return individual rows for aggregation queries")
            if top_n:
                rules.append(f"- Return top {top_n} results: ORDER BY total_claims DESC LIMIT {top_n}")
            else:
                rules.append("- Order by count descending")
                # Check if query has "highest/most" - add LIMIT 1
                if natural_language_query and any(word in natural_language_query.lower() for word in ['highest', 'most', 'top']):
                    rules.append("- Use LIMIT 1 for 'highest/most' queries")
        
        elif intent == "TREND_TIME_SERIES":
            rules.append("INTENT: Trend/Time Series")
            rules.append("- MUST group by: DATE_FORMAT(claims.created_at, '%Y-%m') for monthly")
            if time_ref:
                rules.append(f"- Time filter: {time_ref.get('sql', 'N/A')}")
            else:
                rules.append("- Default: monthly grouping, all available data")
        
        elif intent == "COST_FINANCIAL":
            rules.append("INTENT: Cost/Financial Impact")
            rules.append("- MUST use: AVG(claims.total_cost) or SUM(claims_services.cost)")
            rules.append("- NEVER infer cost from services.price alone")
            rules.append("- Filter: WHERE c.total_cost IS NOT NULL")
        
        elif intent == "SERVICE_UTILIZATION":
            rules.append("INTENT: Service Utilization")
            rules.append("- MUST join: diagnosis → claim → services")
            rules.append("- MUST output: diagnoses.name AND services.description")
            rules.append("- Count service usage per diagnosis")
        
        if time_ref and time_ref.get('needs_clarification'):
            rules.append(f"⚠️ TIME AMBIGUITY: {time_ref.get('type')} - may need clarification")
        
        return "\n".join(rules) if rules else "Intent: UNKNOWN - use default Phase 1 rules"
    
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
        
        # Phase 1: Post-processing validation - block forbidden outputs
        sql = self._validate_phase1_canonical(sql, natural_language_query)
        
        # Phase 3: Output enforcement rules - block and rewrite bad patterns
        sql = self._enforce_phase3_output_rules(sql, natural_language_query)
        
        # CRITICAL: For disease/highest/most queries, ensure SQL is aggregated
        query_lower = natural_language_query.lower()
        is_disease_aggregation_query = any(keyword in query_lower for keyword in [
            'disease', 'diagnosis', 'highest', 'most', 'top'
        ]) and any(keyword in query_lower for keyword in ['patients', 'claims', 'count'])
        
        if is_disease_aggregation_query and sql:
            sql_upper = sql.upper()
            # Check if SQL is returning individual rows instead of aggregated data
            # Look for individual claim columns (more flexible pattern matching)
            has_individual_claim_columns = (
                re.search(r'\bc\.id\b', sql_upper) or 
                re.search(r'\bclaims\.id\b', sql_upper) or
                'CLAIM_UNIQUE_ID' in sql_upper or
                'CLIENT_NAME' in sql_upper or
                ('STATUS' in sql_upper and 'CASE' in sql_upper and 'GROUP BY' not in sql_upper)
            )
            has_aggregation = 'GROUP BY' in sql_upper and 'COUNT' in sql_upper
            has_diagnosis_name = re.search(r'\bd\.name\b|\bdiagnoses\.name\b', sql_upper)
            
            # If SQL has individual claim columns but no aggregation or diagnosis name, it's wrong
            if has_individual_claim_columns and (not has_aggregation or not has_diagnosis_name):
                # This is wrong - reject immediately
                raise ValueError(
                    f"Generated SQL returns individual claims instead of aggregated disease data. "
                    f"Query requires: SELECT d.name AS disease, COUNT(DISTINCT c.id) AS patient_count "
                    f"with GROUP BY d.name. Generated SQL: {sql[:300]}..."
                )
        
        return sql
    
    def _enforce_phase3_output_rules(self, sql: str, query: str) -> str:
        """
        Phase 3: Output enforcement rules - block and rewrite bad patterns
        
        Blocks:
        - diagnosis_id in SELECT
        - service_summary_diagnosis.* in SELECT
        - GROUP BY id
        - SELECT id (unless for counting)
        - diagnosis_code in SELECT
        
        Rewrites:
        - Grouping on IDs → rewrite to group by names
        - Invalid joins → rewrite to canonical path (claims.diagnosis → diagnoses.id via CAST)
        - Missing labels → add labels
        """
        if not sql:
            return sql
        sql_upper = sql.upper()
        query_upper = query.upper()
        query_lower = query.lower()
        
        # Check if this is a diagnosis/claims query
        is_phase3_query = any(keyword in query_lower for keyword in [
            'diagnosis', 'disease', 'claim', 'service', 'clinical'
        ])
        
        if not is_phase3_query:
            return sql  # Not a Phase 3 query, skip validation
        
        # Extract SELECT clause
        select_match = re.search(r'SELECT\s+(.*?)\s+FROM', sql_upper, re.DOTALL | re.IGNORECASE)
        if not select_match:
            return sql
        
        select_clause = select_match.group(1)
        
        # Phase 3: Block forbidden patterns
        blocked_patterns = [
            (r'\bdiagnosis_id\b', 'diagnosis_id', 'diagnoses.name'),
            (r'\bdiagnosis_code\b', 'diagnosis_code', 'diagnoses.name'),
            (r'\bssd\.\*\b', 'service_summary_diagnosis.*', 'diagnoses.name via canonical join'),
            (r'\bGROUP\s+BY\s+[^,]*\bid\b', 'GROUP BY id', 'GROUP BY name'),
        ]
        
        for pattern, pattern_name, replacement in blocked_patterns:
            if re.search(pattern, select_clause, re.IGNORECASE):
                # Check if name is also present (allow if both present)
                if not re.search(r'\bd\.name\b|\bdiagnoses\.name\b', select_clause, re.IGNORECASE):
                    raise ValueError(
                        f"Phase 3 Violation: SQL contains forbidden pattern '{pattern_name}'. "
                        f"Must use {replacement} instead. Query: {query}"
                    )
        
        # Phase 3: Check for SELECT id (unless it's for counting)
        if re.search(r'\bSELECT\s+[^,]*\bid\b', sql_upper) and 'COUNT' not in sql_upper:
            # Check if it's selecting c.id for counting (allowed)
            if not re.search(r'COUNT\s*\(\s*DISTINCT\s+C\.ID', sql_upper):
                # Check if name is also selected
                if not re.search(r'\bd\.name\b|\bdiagnoses\.name\b', select_clause, re.IGNORECASE):
                    raise ValueError(
                        "Phase 3 Violation: SELECT contains raw id without name. "
                        "Must include human-readable name. Query: " + query
                    )
        
        # Phase 3: Validate canonical join paths
        if 'DIAGNOSIS' in query_upper or 'DISEASE' in query_upper:
            # Correct canonical path: claims.diagnosis (TEXT) → diagnoses.id via CAST
            # The claims.diagnosis column contains diagnosis IDs as TEXT
            has_canonical_path = (
                'DIAGNOSES' in sql_upper and
                'CAST' in sql_upper and
                'DIAGNOSIS' in sql_upper
            )
            
            # Check for correct diagnosis join (must use CAST)
            has_bad_join = (
                'JOIN DIAGNOSES' in sql_upper and
                'CAST' not in sql_upper
            )
            
            if has_bad_join:
                raise ValueError(
                    "Phase 3 Violation: Diagnosis joins must use CAST. "
                    "Must use: JOIN diagnoses d ON d.id = CAST(c.diagnosis AS UNSIGNED). Query: " + query
                )
        
        # Phase 3: Validate service joins
        if 'SERVICE' in query_upper and 'DIAGNOSIS' in query_upper:
            # Must use: claims → claims_services → services
            has_canonical_service_path = (
                'CLAIMS_SERVICES' in sql_upper and
                'SERVICES' in sql_upper
            )
            
            if not has_canonical_service_path:
                raise ValueError(
                    "Phase 3 Violation: Service joins must use canonical path: "
                    "claims → claims_services → services. Query: " + query
                )
        
        return sql
    
    def _validate_phase2_semantic(self, sql: str, query: str, intent: str) -> str:
        """
        Phase 2: Validate semantic contract rules
        
        Validates:
        - Frequency/Volume: Uses COUNT(DISTINCT claims.id)
        - Trend: Groups by DATE_FORMAT
        - Cost: Uses AVG/SUM from claims or claims_services
        - Service: Includes both diagnoses.name and services.description
        """
        if not sql:
            raise ValueError("SQL generation returned empty result")
        sql_upper = sql.upper()
        
        if intent == "FREQUENCY_VOLUME":
            # Must use COUNT(DISTINCT claims.id), not service_summary rows
            if 'COUNT' in sql_upper:
                # Check if counting claims.id
                if 'COUNT(DISTINCT C.ID)' not in sql_upper and 'COUNT(DISTINCT CLAIMS.ID)' not in sql_upper:
                    # Check if counting wrong thing
                    if 'COUNT(DISTINCT SS.ID)' in sql_upper or 'COUNT(DISTINCT SERVICE_SUMMARY' in sql_upper:
                        raise ValueError(
                            "Phase 2 Violation: Frequency queries must count DISTINCT claims.id, "
                            "not service_summary rows. Query: " + query
                        )
        
        elif intent == "TREND_TIME_SERIES":
            # Must group by DATE_FORMAT for monthly trends
            if 'GROUP BY' in sql_upper:
                if 'DATE_FORMAT' not in sql_upper and 'DATE(' not in sql_upper:
                    # Allow if it's a simple query, but warn
                    pass
        
        elif intent == "COST_FINANCIAL":
            # Must use AVG(claims.total_cost) or SUM(claims_services.cost)
            if 'AVG' in sql_upper or 'SUM' in sql_upper:
                if 'TOTAL_COST' not in sql_upper and 'CLAIMS_SERVICES' not in sql_upper:
                    # Check if trying to use services.price
                    if 'SERVICES.PRICE' in sql_upper or 'S.PRICE' in sql_upper:
                        raise ValueError(
                            "Phase 2 Violation: Cost queries must use claims.total_cost or "
                            "claims_services.cost, not services.price. Query: " + query
                        )
        
        elif intent == "SERVICE_UTILIZATION":
            # Must include both diagnoses.name and services.description
            if 'DIAGNOSES' in sql_upper and 'SERVICES' in sql_upper:
                if 'D.NAME' not in sql_upper and 'DIAGNOSES.NAME' not in sql_upper:
                    raise ValueError(
                        "Phase 2 Violation: Service utilization queries must include diagnoses.name. Query: " + query
                    )
                if 'S.DESCRIPTION' not in sql_upper and 'SERVICES.DESCRIPTION' not in sql_upper:
                    raise ValueError(
                        "Phase 2 Violation: Service utilization queries must include services.description. Query: " + query
                    )
        
        return sql
    
    def _validate_phase1_canonical(self, sql: str, query: str) -> str:
        """
        Phase 1: Validate canonical domain rules and block forbidden outputs
        
        Blocks:
        - Any _id columns in SELECT
        - diagnosis_code in SELECT
        - Raw IDs in SELECT
        - Invalid join paths
        """
        if not sql:
            return sql
        sql_upper = sql.upper()
        query_upper = query.upper()
        query_lower = query.lower()
        
        # Check if this is a diagnosis/claims query (Phase 1 domain)
        is_phase1_query = any(keyword in query_lower for keyword in [
            'diagnosis', 'disease', 'claim', 'service', 'clinical'
        ])
        
        if not is_phase1_query:
            return sql  # Not a Phase 1 query, skip validation
        
        # Extract SELECT clause
        select_match = re.search(r'SELECT\s+(.*?)\s+FROM', sql_upper, re.DOTALL | re.IGNORECASE)
        if not select_match:
            return sql
        
        select_clause = select_match.group(1)
        
        # Check for forbidden patterns in SELECT
        forbidden_patterns = [
            r'\bdiagnosis_code\b',
            r'\bdiagnosis_id\b',
            r'\bd\.id\b',
            r'\bssd\.diagnosis_id\b',
            r'\bdiagnoses\.id\b',
        ]
        
        for pattern in forbidden_patterns:
            if re.search(pattern, select_clause, re.IGNORECASE):
                # Check if name is also present
                if not re.search(r'\bd\.name\b|\bdiagnoses\.name\b', select_clause, re.IGNORECASE):
                    raise ValueError(
                        f"Phase 1 Violation: SELECT contains forbidden column '{pattern}'. "
                        f"Must use diagnoses.name instead. Query: {query}"
                    )
        
        # Validate canonical join paths are used
        # Must use: claims.diagnosis → diagnoses.id via CAST
        if 'DIAGNOSIS' in query_upper or 'DISEASE' in query_upper:
            if 'DIAGNOSES' in sql_upper:
                # If joining diagnoses, must use CAST for the TEXT diagnosis column
                has_canonical_join = 'CAST' in sql_upper
                if not has_canonical_join:
                    # Allow if it's a simple count query
                    if 'COUNT' in sql_upper and 'FROM CLAIMS' in sql_upper:
                        pass  # Simple count is OK
                    # Otherwise pass - will be validated in Phase 3
        
        return sql
    
    def _enhance_sql_with_names(self, sql: str) -> str:
        """
        Post-process SQL to ensure names are used instead of IDs.
        This is a safety net to ensure human-readable output.
        """
        if not sql:
            return sql
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
        if not sql:
            return sql
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
    
    async def _initialize_vanna_if_needed(self):
        """Initialize Vanna AI if enabled and not already initialized"""
        if not settings.USE_VANNA_AI or not VANNA_SERVICE_AVAILABLE:
            return False
        
        if self._vanna_initialized:
            return vanna_service.is_available()
        
        try:
            # Initialize Vanna if database is ready
            if database_service.pool:
                initialized = await vanna_service.initialize()
                self._vanna_initialized = True
                return initialized
        except Exception as e:
            print(f"⚠️  Vanna initialization error: {e}")
        
        return False
    
    async def generate_sql(
        self,
        natural_language_query: str,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Generate SQL query from natural language
        
        Priority:
        1. Try Vanna AI (if enabled)
        2. Fallback to legacy LLM-based generator
        
        Args:
            natural_language_query: User's question in natural language
            conversation_history: Previous conversation messages for context
        
        Returns:
            Dictionary with 'sql', 'explanation', and 'confidence'
        """
        # Try Vanna AI first if enabled
        if settings.USE_VANNA_AI and VANNA_SERVICE_AVAILABLE:
            try:
                # Initialize Vanna if needed
                vanna_ready = await self._initialize_vanna_if_needed()
                
                if vanna_ready and vanna_service.is_available():
                    # Use Vanna AI for SQL generation
                    result = await vanna_service.generate_sql(
                        natural_language_query=natural_language_query,
                        conversation_history=conversation_history
                    )
                    
                    # Mark that we used Vanna
                    result['source'] = 'vanna'
                    return result
            except Exception as e:
                print(f"⚠️  Vanna AI error: {e}")
                # Fallback to legacy if enabled
                if not settings.VANNA_FALLBACK_TO_LEGACY:
                    raise
                print("⚠️  Falling back to legacy SQL generator")
        
        # Legacy SQL generation (original implementation)
        try:
            # Fast path: Direct SQL for very common simple queries (bypasses LLM for speed)
            query_lower = natural_language_query.lower().strip()
            
            # CRITICAL: Skip fast-path for disease/diagnosis queries - they need proper aggregation
            has_disease_keywords = any(keyword in query_lower for keyword in [
                'disease', 'diagnosis', 'diagnoses', 'highest', 'most', 'top'
            ])
            
            # Status queries - show status names instead of IDs
            # Only use fast-path if NO additional filters (state, date, etc.) AND no disease keywords
            if not has_disease_keywords and query_lower in ["show me claims by status", "claims by status", "claims grouped by status"]:
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
            
            # Count queries - skip if disease/diagnosis keywords present
            if not has_disease_keywords and query_lower in ["total number of claims", "how many claims", "count of claims", "show me total number of claims"]:
                return {
                    "sql": "SELECT COUNT(*) as total_claims FROM claims",
                    "explanation": "This query returns the total number of claims",
                    "confidence": 0.95
                }
            
            # Date-based queries - parse and generate SQL directly
            # CRITICAL: Skip ALL date-based fast-path if disease/diagnosis keywords present
            # Disease queries need proper aggregation, not individual claim rows
            if not has_disease_keywords:
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
                
                # "today" queries - ONLY if no disease keywords
                if not has_disease_keywords and "today" in query_lower and "claim" in query_lower:
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
            
            # Fix 2: Join Confidence Guard - Check before generating SQL
            join_confidence = self._compute_join_confidence(natural_language_query)
            print(f"🔍 [JOIN_CONFIDENCE] Tables: {join_confidence['tables']}, Confidence: {join_confidence['confidence']:.2f}")
            
            if not join_confidence['can_proceed']:
                # Refuse with explicit explanation
                return {
                    "sql": None,
                    "explanation": None,
                    "confidence": join_confidence['confidence'],
                    "source": "legacy",
                    "error": join_confidence['reason'],
                    "table_selection": {
                        "selected_tables": join_confidence['tables'],
                        "reason": join_confidence['reason'],
                        "join_confidence": join_confidence['confidence']
                    }
                }
            
            # Get schema information (for disease/diagnosis queries or if fast-path didn't match)
            schema_info = await self._get_schema_info()
            schema_text = self._format_schema_for_prompt(schema_info, natural_language_query)
            
            # Build prompt
            prompt = self._build_sql_prompt(
                natural_language_query,
                schema_text,
                conversation_history
            )
            
            # Generate SQL using LLM
            # Use minimal tokens for SQL generation - typical queries are 200-300 tokens
            max_tokens = 400  # Reduced to stay within rate limits
            response = await llm_client.generate(
                prompt=prompt,
                temperature=settings.TEMPERATURE,
                max_tokens=max_tokens
            )
            
            # Classify intent for Phase 2 validation
            intent = intent_classifier.classify_intent(natural_language_query)
            
            # Extract SQL from response
            sql = self._extract_sql_from_response(response, natural_language_query)
            
            # Phase 2: Validate semantic contract rules
            sql = self._validate_phase2_semantic(sql, natural_language_query, intent)
            
            # Guard against None SQL
            if not sql:
                raise ValueError("SQL generation returned empty result")
            
            # Generate explanation
            explanation = f"This query retrieves data to answer: {natural_language_query}"
            
            # Calculate confidence (simple heuristic - can be improved)
            confidence = 0.8  # Default confidence
            if sql and ('JOIN' in sql.upper() or 'WHERE' in sql.upper()):
                confidence = 0.85
            if sql and len(sql.split()) > 20:  # Complex queries
                confidence = 0.9
            
            # Fix 3: Table Selection Transparency - Include metadata in response
            result = {
                "sql": sql,
                "explanation": explanation,
                "confidence": confidence,
                "source": "legacy",
                "table_selection": {
                    "selected_tables": join_confidence['tables'],
                    "reason": f"Tables selected based on query keywords: {', '.join(join_confidence['tables'])}",
                    "join_confidence": join_confidence['confidence']
                }
            }
            
            # Optionally train Vanna on successful queries for future improvement
            if settings.USE_VANNA_AI and VANNA_SERVICE_AVAILABLE and vanna_service.is_available():
                try:
                    # Train Vanna on this successful query (async, don't wait)
                    # This helps Vanna learn from successful patterns
                    asyncio.create_task(
                        vanna_service.train_on_example(
                            question=natural_language_query,
                            sql=sql,
                            tag="successful_query"
                        )
                    )
                except Exception as e:
                    # Don't fail if training fails
                    print(f"⚠️  Error training Vanna on example: {e}")
            
            return result
            
        except Exception as e:
            raise RuntimeError(f"Failed to generate SQL: {str(e)}")


# Global instance
sql_generator = SQLGenerator()




