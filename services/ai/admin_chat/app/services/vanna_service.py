"""
Vanna AI Service - Professional SQL generation with RAG and learning capabilities
Integrates Vanna AI for improved SQL generation, analytics, and context awareness
"""
from typing import Dict, Any, List, Optional
import os
from pathlib import Path
import asyncio
import json
from app.core.config import settings
from app.services.database_service import database_service
from app.services.llm_client import llm_client

# Vanna imports
try:
    import vanna as vn
    try:
        from vanna.base import VannaBase
        VANNA_BASE_AVAILABLE = True
    except ImportError:
        VANNA_BASE_AVAILABLE = False
    VANNA_AVAILABLE = True
except ImportError:
    VANNA_AVAILABLE = False
    VANNA_BASE_AVAILABLE = False
    vn = None


class CustomVannaModel:
    """
    Custom Vanna model that uses Groq API for LLM calls
    Simple implementation that doesn't require VannaBase
    """
    
    def __init__(self, config=None):
        self._training_data = {
            'ddl': [],
            'documentation': [],
            'question_sql': []
        }
        self.run_sql = None  # Will be set by VannaService
        self.run_sql_is_set = False
    
    def generate_sql(self, question: str, **kwargs) -> str:
        """Generate SQL using Groq API"""
        # This will be overridden by async version in VannaService
        raise NotImplementedError("Use VannaService.generate_sql instead")
    
    def add_training_data(self, training_type: str, data: str):
        """Add training data"""
        if training_type == 'ddl':
            self._training_data['ddl'].append(data)
        elif training_type == 'documentation':
            self._training_data['documentation'].append(data)
        elif training_type == 'question_sql':
            self._training_data['question_sql'].append(data)
    
    def get_training_data(self) -> Dict[str, List[str]]:
        """Get all training data"""
        return self._training_data


class VannaService:
    """
    Vanna AI service wrapper for enhanced SQL generation
    
    Features:
    - Automatic schema learning from database
    - RAG-based SQL generation with context awareness
    - Learning from example queries
    - Improved accuracy for complex queries
    """
    
    def __init__(self):
        self.vanna_model: Optional[Any] = None
        self._initialized = False
        self._model_name = "hiva_admin_chat"
        self._vanna_dir = Path(__file__).parent.parent.parent / "vanna_data"
        self._vanna_dir.mkdir(exist_ok=True)
        self._training_data_file = self._vanna_dir / "training_data.json"
        
    async def initialize(self) -> bool:
        """
        Initialize Vanna AI model
        
        Returns:
            True if initialized successfully, False otherwise
        """
        if not VANNA_AVAILABLE:
            print("⚠️  Vanna AI not available. Install with: pip install vanna")
            return False
        
        if self._initialized:
            return True
        
        try:
            # Check if database is available
            if not database_service.pool:
                print("⚠️  Database not available for Vanna initialization")
                return False
            
            # Create custom Vanna model
            self.vanna_model = CustomVannaModel()
            self.vanna_model.run_sql = self._run_sql
            
            # Load existing training data
            await self._load_training_data()
            
            # Train on database schema if not already trained
            await self._train_on_schema()
            
            self._initialized = True
            print("✅ Vanna AI initialized successfully")
            return True
            
        except Exception as e:
            print(f"⚠️  Failed to initialize Vanna AI: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def _load_training_data(self):
        """Load training data from file"""
        if self._training_data_file.exists():
            try:
                with open(self._training_data_file, 'r') as f:
                    data = json.load(f)
                    for ddl in data.get('ddl', []):
                        self.vanna_model.add_training_data('ddl', ddl)
                    for doc in data.get('documentation', []):
                        self.vanna_model.add_training_data('documentation', doc)
                    for qs in data.get('question_sql', []):
                        self.vanna_model.add_training_data('question_sql', json.dumps(qs))
                print(f"✅ Loaded {len(data.get('ddl', []))} DDL entries from training data")
            except Exception as e:
                print(f"⚠️  Error loading training data: {e}")
    
    async def _save_training_data(self):
        """Save training data to file"""
        try:
            training_data = self.vanna_model.get_training_data()
            with open(self._training_data_file, 'w') as f:
                json.dump(training_data, f, indent=2)
        except Exception as e:
            print(f"⚠️  Error saving training data: {e}")
    
    async def _train_on_schema(self):
        """
        Phase 3: Train Vanna on minimal schema context (only core tables)
        Only trains on the 6 authoritative tables for Clinical Claims & Diagnosis domain
        """
        if not self.vanna_model or not database_service.pool:
            return
        
        try:
            # Phase 3: Minimal Schema Context - Only Core Tables
            # NOTE: service_summary_diagnosis is deprecated (only 18 rows)
            # Use service_summaries.diagnosis → diagnoses.id direct join instead
            core_tables = [
                'claims',
                'service_summaries',
                'diagnoses',
                'claims_services',
                'services',
                'users',
                'states'
            ]
            
            # Get schema information
            schema_info = await database_service.get_schema_info()
            
            if not schema_info or 'tables' not in schema_info:
                print("⚠️  No schema information available for Vanna training")
                return
            
            # Check existing DDL
            existing_ddl = set()
            training_data = self.vanna_model.get_training_data()
            for ddl in training_data.get('ddl', []):
                if 'CREATE TABLE' in ddl.upper():
                    table_match = ddl.upper().split('CREATE TABLE')[1].split('(')[0].strip()
                    existing_ddl.add(table_match)
            
            # Phase 3: Train ONLY on core tables (minimal schema context)
            new_tables = 0
            for table in schema_info.get('tables', []):
                table_name = table.get('table_name', '').lower()
                
                # Skip if not a core table
                if table_name not in core_tables:
                    continue
                
                # Skip if already trained
                if table_name.upper() in existing_ddl:
                    continue
                
                columns = table.get('columns', [])
                if not columns:
                    continue
                
                # Phase 3: Build minimal DDL (only essential columns)
                essential_columns = self._get_essential_columns(table_name, columns)
                
                ddl_parts = [f"CREATE TABLE {table_name} ("]
                col_defs = []
                for col in essential_columns:
                    col_name = col.get('column_name', '')
                    col_type = col.get('data_type', 'varchar')
                    nullable = col.get('is_nullable', 'YES')
                    null_str = "" if nullable == 'NO' else "NULL"
                    col_defs.append(f"  {col_name} {col_type} {null_str}")
                
                ddl_parts.append(",\n".join(col_defs))
                ddl_parts.append(");")
                ddl = "\n".join(ddl_parts)
                
                # Add to training data
                self.vanna_model.add_training_data('ddl', ddl)
                new_tables += 1
            
            # Phase 3: Add authoritative join rules as documentation
            join_rules = """AUTHORITATIVE JOIN RULES (MANDATORY):

Diagnoses are connected to claims DIRECTLY through:
claims.diagnosis (TEXT) → diagnoses.id (via CAST: d.id = CAST(c.diagnosis AS UNSIGNED))
CRITICAL: ALWAYS add WHERE c.diagnosis REGEXP '^[0-9]+$' to filter valid numeric IDs

State filtering for claims:
claims → users → states (via claims.user_id = users.id, users.state = states.id)

Services are connected ONLY through:
claims → claims_services → services

The claims.diagnosis column is TEXT type containing the diagnosis ID.
Use CAST(c.diagnosis AS UNSIGNED) to convert for JOIN.
ALWAYS use the canonical join paths above."""
            
            self.vanna_model.add_training_data('documentation', join_rules)
            
            if new_tables > 0:
                await self._save_training_data()
                print(f"✅ Phase 3: Vanna trained on {new_tables} core tables (minimal schema)")
            else:
                print(f"✅ Phase 3: Vanna already trained on all {len(core_tables)} core tables")
            
        except Exception as e:
            print(f"⚠️  Error training Vanna on schema: {e}")
            import traceback
            traceback.print_exc()
    
    def _get_essential_columns(self, table_name: str, columns: List[Dict]) -> List[Dict]:
        """
        Phase 3: Get only essential columns for minimal schema context
        """
        table_name_lower = table_name.lower()
        
        # Define essential columns per table
        essential_map = {
            'claims': ['id', 'created_at', 'total_cost', 'user_id', 'provider_id'],
            'service_summaries': ['id', 'claim_id', 'diagnosis'],  # diagnosis is FK to diagnoses.id
            'diagnoses': ['id', 'name'],
            'claims_services': ['claims_id', 'services_id', 'cost'],
            'services': ['id', 'description'],
            'users': ['id', 'state'],  # state is FK to states.id
            'states': ['id', 'name']
        }
        
        essential_cols = essential_map.get(table_name_lower, [])
        if not essential_cols:
            # If not in map, return all columns
            return columns
        
        # Filter to only essential columns
        filtered = []
        col_names = {col.get('column_name', '').lower() for col in columns}
        for col_name in essential_cols:
            # Find matching column
            for col in columns:
                if col.get('column_name', '').lower() == col_name.lower():
                    filtered.append(col)
                    break
        
        return filtered if filtered else columns
    
    def _run_sql(self, sql: str) -> str:
        """
        Execute SQL query (synchronous wrapper for Vanna)
        This is called by Vanna to validate queries
        
        Note: This is a synchronous method that Vanna may call.
        We handle async database calls by creating a new event loop if needed.
        """
        if not database_service.pool:
            return ""
        
        # Run query synchronously (Vanna expects sync)
        try:
            # Try to get existing event loop
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If loop is running, we need to use a thread executor
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(
                            lambda: asyncio.run(database_service.execute_query(sql))
                        )
                        results = future.result(timeout=30)
                else:
                    results = loop.run_until_complete(database_service.execute_query(sql))
            except RuntimeError:
                # No event loop exists, create a new one
                results = asyncio.run(database_service.execute_query(sql))
            
            # Return formatted results (Vanna expects string)
            if results:
                # Return first few rows as string for validation
                return str(results[:5])
            return ""
        except Exception as e:
            print(f"⚠️  Error executing SQL in Vanna: {e}")
            return ""
    
    async def _generate_sql_with_groq(
        self,
        question: str,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        Generate SQL using Groq API with Vanna's RAG approach
        """
        try:
            # Get training data from Vanna
            training_data = self.vanna_model.get_training_data()
            
            # Build context from training data
            context_parts = []
            
            # Add DDL (schema information)
            if training_data.get('ddl'):
                context_parts.append("=== DATABASE SCHEMA ===")
                for ddl in training_data['ddl'][:30]:  # Limit to 30 tables
                    context_parts.append(ddl)
                context_parts.append("")
            
            # Add example question-SQL pairs (RAG)
            if training_data.get('question_sql'):
                context_parts.append("=== EXAMPLE QUERIES ===")
                for qs_pair in training_data['question_sql'][-10:]:  # Last 10 examples
                    if isinstance(qs_pair, dict):
                        context_parts.append(f"Q: {qs_pair.get('question', '')}")
                        context_parts.append(f"SQL: {qs_pair.get('sql', '')}")
                    elif isinstance(qs_pair, str):
                        try:
                            qs_dict = json.loads(qs_pair)
                            context_parts.append(f"Q: {qs_dict.get('question', '')}")
                            context_parts.append(f"SQL: {qs_dict.get('sql', '')}")
                        except:
                            context_parts.append(str(qs_pair))
                    context_parts.append("")
            
            # Add documentation
            if training_data.get('documentation'):
                context_parts.append("=== DOCUMENTATION ===")
                for doc in training_data['documentation'][-5:]:
                    context_parts.append(doc)
                context_parts.append("")
            
            context = "\n".join(context_parts)
            
            # Add conversation history if available
            history_context = ""
            if conversation_history:
                history_parts = []
                for msg in conversation_history[-3:]:
                    role = msg.get('role', '')
                    content = msg.get('content', '')
                    metadata = msg.get('metadata', {})
                    if role == 'user':
                        history_parts.append(f"Previous question: {content}")
                    elif role == 'assistant' and 'sql' in metadata:
                        history_parts.append(f"Previous SQL: {metadata['sql']}")
                if history_parts:
                    history_context = "\n\n=== CONVERSATION CONTEXT ===\n" + "\n".join(history_parts) + "\n"
            
            # Build prompt with Vanna-style RAG + Phase 1 Canonical Domain Rules
            prompt = f"""You are an expert SQL query generator for a MySQL database using RAG (Retrieval-Augmented Generation).

PHASE 1: CANONICAL DOMAIN DEFINITION - CLINICAL CLAIMS & DIAGNOSIS

DOMAIN SCOPE (STRICT):
- ONLY answer: diagnoses, claims, clinical services, volumes/trends/costs tied to diagnoses
- EXCLUDED: users, providers, payments, roles/permissions, accreditation, telescope, admin metadata
- If query requires excluded tables → REJECT or indicate outside domain

AUTHORITATIVE TABLES (LOCKED):
- claims, service_summaries, diagnoses, claims_services, services, users, states

CANONICAL JOIN GRAPH (SINGLE SOURCE OF TRUTH):
claims.diagnosis (TEXT) → diagnoses.id (use CAST: d.id = CAST(c.diagnosis AS UNSIGNED))
claims.id → claims_services.claims_id
claims_services.services_id → services.id
claims.user_id → users.id
users.state → states.id
🚫 claims.diagnosis is TEXT type containing diagnosis IDs - MUST use CAST
🚫 ALWAYS add WHERE c.diagnosis REGEXP '^[0-9]+$' to filter valid IDs

MANDATORY LABEL RESOLUTION:
- Diagnosis → diagnoses.name (NEVER diagnoses.id or diagnosis_code)
- Service → services.description (NEVER services.id)
- NEVER return: _id columns, diagnosis_code, foreign keys in SELECT

AGGREGATION RULES:
- Legal GROUP BY: diagnoses.name, DATE(claims.created_at)
- Illegal GROUP BY: diagnoses.id, any _id column

{context}

STATE-BASED DISEASE QUERIES (CRITICAL):
- When query asks for "disease with highest/most patients in [State]", you MUST:
  1. Join: claims → users → states (for state filtering: JOIN users u ON c.user_id = u.id JOIN states s ON u.state = s.id)
  2. Join: claims.diagnosis → diagnoses (via CAST: JOIN diagnoses d ON d.id = CAST(c.diagnosis AS UNSIGNED))
  3. SELECT: d.name AS disease (or diagnosis)
  4. COUNT: COUNT(c.id) AS patient_count (or total_claims)
  5. GROUP BY: d.name (NEVER group by d.id)
  6. ORDER BY: patient_count DESC
  7. LIMIT: LIMIT 1 (for "highest/most" queries)
  8. WHERE: s.name LIKE '%StateName%' AND c.diagnosis REGEXP '^[0-9]+$'
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

CRITICAL RULES:
1. ONLY generate SELECT queries (read-only) - ALWAYS start with SELECT
2. NEVER include INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, or any write operations
3. Use proper MySQL syntax
4. Use table and column names EXACTLY as they appear in the schema above
5. For JOINs, ONLY use canonical join paths defined above
6. ALWAYS use names instead of IDs - join related tables to get human-readable names
7. For diagnosis queries: MUST use diagnoses.name, NEVER diagnosis_code or diagnoses.id
8. For service queries: MUST use services.description, NEVER services.id
9. For "highest/most/top" queries: ALWAYS use GROUP BY, COUNT, ORDER BY DESC, LIMIT - NEVER return individual rows
10. For state-based queries: ALWAYS join users and states tables, filter by s.name LIKE '%StateName%'
11. Return ONLY the SQL query starting with SELECT. No explanations, no markdown, no code blocks.{history_context}

User Question: {question}

SQL Query:"""
            
            # Use our Groq client
            sql = await llm_client.generate(
                prompt=prompt,
                temperature=0.1,
                max_tokens=1000
            )
            
            # Extract SQL from response
            sql = sql.strip()
            # Remove markdown code blocks
            if sql.startswith("```sql"):
                sql = sql[6:]
            elif sql.startswith("```"):
                sql = sql[3:]
            if sql.endswith("```"):
                sql = sql[:-3]
            sql = sql.strip().rstrip(";")
            
            # Ensure it starts with SELECT
            if not sql.upper().strip().startswith('SELECT'):
                raise ValueError("Generated query is not a SELECT statement")
            
            return sql
            
        except Exception as e:
            print(f"⚠️  Error generating SQL with Groq: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    async def generate_sql(
        self,
        natural_language_query: str,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Generate SQL query using Vanna AI
        
        Args:
            natural_language_query: User's question in natural language
            conversation_history: Previous conversation messages for context
        
        Returns:
            Dictionary with 'sql', 'explanation', and 'confidence'
        """
        if not self._initialized or not self.vanna_model:
            raise RuntimeError("Vanna AI not initialized. Call initialize() first.")
        
        try:
            # Add conversation context to query if available
            query_with_context = natural_language_query
            if conversation_history:
                context_parts = []
                for msg in conversation_history[-3:]:  # Last 3 messages
                    role = msg.get('role', '')
                    content = msg.get('content', '')
                    if role == 'user':
                        context_parts.append(f"Previous question: {content}")
                    elif role == 'assistant':
                        # Extract SQL from previous response if available
                        metadata = msg.get('metadata', {})
                        if 'sql' in metadata:
                            context_parts.append(f"Previous query: {metadata['sql']}")
                
                if context_parts:
                    query_with_context = f"{natural_language_query}\n\nContext: {'; '.join(context_parts)}"
            
            # Generate SQL using our custom Groq-based method
            sql = await self._generate_sql_with_groq(query_with_context, conversation_history)
            
            # Ensure it's a SELECT query (security)
            sql_upper = sql.strip().upper()
            if not sql_upper.startswith('SELECT'):
                raise ValueError("Vanna generated non-SELECT query")
            
            # Check for forbidden operations
            forbidden = ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER', 'TRUNCATE']
            sql_words = set(sql_upper.split())
            for keyword in forbidden:
                if keyword in sql_words:
                    raise ValueError(f"Query contains forbidden operation: {keyword}")
            
            # Generate explanation
            explanation = f"Vanna AI generated SQL to answer: {natural_language_query}"
            
            # Calculate confidence (Vanna provides better confidence)
            confidence = 0.85  # Base confidence for Vanna
            if 'JOIN' in sql_upper:
                confidence = 0.90
            if len(sql.split()) > 30:  # Complex queries
                confidence = 0.95
            
            return {
                "sql": sql.strip(),
                "explanation": explanation,
                "confidence": confidence
            }
            
        except Exception as e:
            raise RuntimeError(f"Vanna AI failed to generate SQL: {str(e)}")
    
    async def train_on_example(
        self,
        question: str,
        sql: str,
        tag: Optional[str] = None
    ):
        """
        Train Vanna on an example question-SQL pair
        
        Args:
            question: Natural language question
            sql: Corresponding SQL query
            tag: Optional tag for categorization
        """
        if not self._initialized or not self.vanna_model:
            return
        
        try:
            # Add to training data
            qs_pair = {
                "question": question,
                "sql": sql,
                "tag": tag
            }
            self.vanna_model.add_training_data('question_sql', json.dumps(qs_pair))
            
            # Save to file
            await self._save_training_data()
            print(f"✅ Trained Vanna on example: {question[:50]}...")
        except Exception as e:
            print(f"⚠️  Error training Vanna on example: {e}")
    
    async def train_on_ddl(self, ddl: str):
        """
        Train Vanna on DDL (Data Definition Language)
        
        Args:
            ddl: DDL statement (CREATE TABLE, etc.)
        """
        if not self._initialized or not self.vanna_model:
            return
        
        try:
            self.vanna_model.add_training_data('ddl', ddl)
            await self._save_training_data()
        except Exception as e:
            print(f"⚠️  Error training Vanna on DDL: {e}")
    
    async def train_on_documentation(self, documentation: str):
        """
        Train Vanna on documentation
        
        Args:
            documentation: Documentation text about the database
        """
        if not self._initialized or not self.vanna_model:
            return
        
        try:
            self.vanna_model.add_training_data('documentation', documentation)
            await self._save_training_data()
        except Exception as e:
            print(f"⚠️  Error training Vanna on documentation: {e}")
    
    def is_available(self) -> bool:
        """Check if Vanna AI is available and initialized"""
        return VANNA_AVAILABLE and self._initialized and self.vanna_model is not None


# Global instance
vanna_service = VannaService()

