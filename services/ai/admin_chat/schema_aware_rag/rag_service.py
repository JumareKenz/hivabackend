#!/usr/bin/env python3
"""
Schema-Aware RAG Service - Main service for intelligent SQL generation
Part of Schema-Aware RAG System for Admin Chatbot

This module provides:
1. Schema-aware SQL generation with dynamic table selection
2. Vanna AI training with DDL and documentation
3. Self-correction loop for failed SQL queries
4. Read-only query execution for safety
"""

import asyncio
import re
import json
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime

# Import components
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings
from app.services.database_service import database_service
from app.services.llm_client import llm_client

from .schema_extractor import schema_extractor
from .table_selector import table_selector


@dataclass
class SQLResult:
    """Result of SQL generation and execution"""
    success: bool
    sql: str
    data: List[Dict[str, Any]]
    row_count: int
    error: Optional[str] = None
    correction_attempts: int = 0
    tables_used: List[str] = None
    execution_time_ms: float = 0


@dataclass
class TrainingExample:
    """Training example for Vanna AI"""
    question: str
    sql: str
    tag: str
    domain: str = "general"


class SchemaAwareRAGService:
    """
    Schema-Aware RAG Service for SQL Generation
    
    Features:
    - Dynamic table selection based on query analysis
    - Minimal schema context for faster, more accurate generation
    - Self-correction loop (retries with error feedback)
    - Vanna AI training integration
    - Read-only query execution
    """
    
    MAX_CORRECTION_ATTEMPTS = 3
    SQL_TIMEOUT_SECONDS = 60
    
    def __init__(self):
        self._initialized = False
        self._training_data: List[TrainingExample] = []
        self._data_dir = Path(__file__).parent / "data"
        self._data_dir.mkdir(exist_ok=True)
    
    async def initialize(self) -> bool:
        """Initialize the RAG service"""
        if self._initialized:
            return True
        
        print("🔄 Initializing Schema-Aware RAG Service...")
        
        # Initialize database connection
        if not database_service.pool:
            await database_service.initialize()
        
        if not database_service.pool:
            print("❌ Failed to initialize database connection")
            return False
        
        # Initialize schema extractor
        if not await schema_extractor.initialize():
            print("❌ Failed to initialize schema extractor")
            return False
        
        # Extract schema if not already done
        if not schema_extractor.tables:
            await schema_extractor.extract_top_tables(n=20)
        
        # Load training data
        await self._load_training_data()
        
        self._initialized = True
        print("✅ Schema-Aware RAG Service initialized")
        return True
    
    async def _load_training_data(self):
        """Load training examples from file"""
        training_file = self._data_dir / "training_examples.json"
        if training_file.exists():
            with open(training_file, 'r') as f:
                data = json.load(f)
                self._training_data = [
                    TrainingExample(**ex) for ex in data
                ]
            print(f"✅ Loaded {len(self._training_data)} training examples")
    
    async def _save_training_data(self):
        """Save training examples to file"""
        training_file = self._data_dir / "training_examples.json"
        data = [
            {
                'question': ex.question,
                'sql': ex.sql,
                'tag': ex.tag,
                'domain': ex.domain
            }
            for ex in self._training_data
        ]
        with open(training_file, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"✅ Saved {len(self._training_data)} training examples")
    
    # ========== TRAINING METHODS ==========
    
    async def train_ddl(self, ddl: str, table_name: Optional[str] = None) -> bool:
        """
        Train on DDL (CREATE TABLE statement)
        
        Args:
            ddl: The CREATE TABLE statement
            table_name: Optional table name for logging
            
        Returns:
            True if training successful
        """
        # Store in schema extractor's cache
        if table_name:
            schema_extractor.ddl_cache[table_name] = ddl
            print(f"✅ Trained on DDL for table: {table_name}")
        else:
            # Extract table name from DDL
            match = re.search(r'CREATE TABLE\s+[`"]?(\w+)[`"]?', ddl, re.IGNORECASE)
            if match:
                table_name = match.group(1)
                schema_extractor.ddl_cache[table_name] = ddl
                print(f"✅ Trained on DDL for table: {table_name}")
            else:
                print("⚠️ Could not extract table name from DDL")
        
        return True
    
    async def train_documentation(self, documentation: str, topic: Optional[str] = None) -> bool:
        """
        Train on documentation (business logic, relationships, etc.)
        
        Args:
            documentation: The documentation text
            topic: Optional topic for organization
            
        Returns:
            True if training successful
        """
        # Store documentation
        doc_file = self._data_dir / "documentation.txt"
        with open(doc_file, 'a') as f:
            f.write(f"\n\n=== {topic or 'Documentation'} ===\n")
            f.write(documentation)
        
        print(f"✅ Trained on documentation: {topic or 'general'}")
        return True
    
    async def train_question_sql(self, question: str, sql: str, tag: str = "", domain: str = "general") -> bool:
        """
        Train on question-SQL pair
        
        Args:
            question: Natural language question
            sql: Corresponding SQL query
            tag: Tag for organization
            domain: Domain (clinical, providers, financial, etc.)
            
        Returns:
            True if training successful
        """
        example = TrainingExample(
            question=question,
            sql=sql,
            tag=tag or f"example_{len(self._training_data) + 1}",
            domain=domain
        )
        self._training_data.append(example)
        await self._save_training_data()
        
        print(f"✅ Trained on Q&A pair: {question[:50]}...")
        return True
    
    async def train_on_database_schema(self) -> bool:
        """
        Automatically train on database schema
        Extracts and trains on DDL for top 20 tables
        """
        print("🔄 Training on database schema...")
        
        # Extract schema
        tables = await schema_extractor.extract_top_tables(n=20)
        
        # Train on each table's DDL
        for table_name, table_info in tables.items():
            ddl = schema_extractor.get_ddl(table_name)
            if ddl:
                await self.train_ddl(ddl, table_name)
        
        # Train on canonical joins documentation
        joins_doc = []
        for name, info in schema_extractor.get_canonical_joins().items():
            joins_doc.append(f"Join: {name}")
            joins_doc.append(f"  Path: {info['path']}")
            joins_doc.append(f"  SQL: {info['sql']}")
            joins_doc.append(f"  Description: {info['description']}")
            joins_doc.append("")
        
        await self.train_documentation(
            "\n".join(joins_doc),
            topic="Canonical Join Paths"
        )
        
        # Save schema files
        await schema_extractor.save_schema()
        await schema_extractor.save_ddl()
        await schema_extractor.save_documentation()
        
        print(f"✅ Trained on {len(tables)} table schemas")
        return True
    
    # ========== SQL GENERATION ==========
    
    def _build_prompt(self, question: str, selected_tables: List[str], relevant_joins: List[Dict]) -> str:
        """Build the SQL generation prompt with selected schema context"""
        
        # Get DDL for selected tables only
        ddl_parts = []
        for table_name in selected_tables:
            ddl = schema_extractor.get_ddl(table_name)
            if ddl:
                ddl_parts.append(ddl)
        
        # Get relevant training examples
        relevant_examples = self._find_relevant_examples(question)
        
        prompt = f"""You are an expert SQL query generator for a MySQL healthcare database.

=== DATABASE SCHEMA (Selected Tables) ===
{chr(10).join(ddl_parts)}

=== CANONICAL JOIN PATHS (MUST USE) ===
"""
        
        for join in relevant_joins:
            prompt += f"""
• {join['path']}:
  SQL: {join['sql']}
  Description: {join['description']}
"""
        
        prompt += """
=== CRITICAL RULES ===
1. ALWAYS use the canonical join paths shown above - DO NOT invent your own joins
2. For diagnosis queries: JOIN claims → service_summaries → diagnoses (via ss.diagnosis = d.id)
3. For state filtering: JOIN users → states (via u.state = s.id)
4. Use GROUP BY and COUNT for aggregation queries (highest, most, top)
5. Use DISTINCT when counting unique entities
6. NEVER use SELECT * - always specify column names
7. ALWAYS add ORDER BY for ranking queries
8. Use LIMIT for "top N" queries
9. Handle NULL values appropriately
10. Return ONLY the SQL query, no explanations

=== EXAMPLE QUERIES ===
"""
        
        for ex in relevant_examples[:3]:
            prompt += f"""
Question: {ex.question}
SQL:
{ex.sql}
"""
        
        prompt += f"""
=== YOUR TASK ===
Generate a SQL query for this question:
{question}

Return ONLY the SQL query:"""
        
        return prompt
    
    def _find_relevant_examples(self, question: str, max_examples: int = 3) -> List[TrainingExample]:
        """Find training examples most relevant to the question"""
        question_lower = question.lower()
        
        scored_examples = []
        for ex in self._training_data:
            score = 0
            ex_lower = ex.question.lower()
            
            # Keyword overlap scoring
            question_words = set(re.findall(r'\b\w+\b', question_lower))
            example_words = set(re.findall(r'\b\w+\b', ex_lower))
            overlap = question_words & example_words
            score += len(overlap) * 10
            
            # Boost for key domain terms
            key_terms = ['disease', 'diagnosis', 'patient', 'claim', 'provider', 'state', 'highest', 'most', 'top']
            for term in key_terms:
                if term in question_lower and term in ex_lower:
                    score += 20
            
            scored_examples.append((score, ex))
        
        # Sort by score and return top N
        scored_examples.sort(key=lambda x: -x[0])
        return [ex for _, ex in scored_examples[:max_examples]]
    
    async def generate_sql(self, question: str) -> Tuple[str, List[str]]:
        """
        Generate SQL for a question using schema-aware RAG
        
        Args:
            question: Natural language question
            
        Returns:
            Tuple of (generated SQL, list of tables used)
        """
        # Select relevant tables
        selected = table_selector.select_tables(question)
        selected_tables = [t.table_name for t in selected]
        
        # Get relevant joins
        relevant_joins = table_selector.get_relevant_joins(question)
        
        # Build prompt
        prompt = self._build_prompt(question, selected_tables, relevant_joins)
        
        # Generate SQL using LLM
        try:
            response = await llm_client.generate(
                prompt=prompt,
                max_tokens=1000,
                temperature=0.1
            )
            
            # Extract SQL from response
            sql = self._extract_sql(response)
            
            return sql, selected_tables
            
        except Exception as e:
            print(f"❌ SQL generation error: {e}")
            raise
    
    def _extract_sql(self, response: str) -> str:
        """Extract SQL query from LLM response"""
        # Remove markdown code blocks
        sql = re.sub(r'```sql\s*', '', response)
        sql = re.sub(r'```\s*', '', sql)
        
        # Remove any explanation text before SELECT
        match = re.search(r'(SELECT\s+.+)', sql, re.IGNORECASE | re.DOTALL)
        if match:
            sql = match.group(1)
        
        # Clean up
        sql = sql.strip()
        
        # Remove trailing semicolon for consistency
        sql = re.sub(r';\s*$', '', sql)
        
        return sql
    
    # ========== SELF-CORRECTION LOOP ==========
    
    async def execute_with_correction(self, question: str) -> SQLResult:
        """
        Execute SQL with self-correction loop
        
        If SQL execution fails, passes the error back to the model
        for correction (up to MAX_CORRECTION_ATTEMPTS times)
        
        Args:
            question: Natural language question
            
        Returns:
            SQLResult with data or error information
        """
        if not self._initialized:
            await self.initialize()
        
        start_time = datetime.now()
        last_sql = ""
        last_error = ""
        tables_used = []
        
        for attempt in range(self.MAX_CORRECTION_ATTEMPTS):
            try:
                if attempt == 0:
                    # First attempt: generate SQL normally
                    sql, tables_used = await self.generate_sql(question)
                else:
                    # Correction attempt: include error in prompt
                    sql, tables_used = await self._generate_corrected_sql(
                        question, last_sql, last_error, tables_used
                    )
                
                last_sql = sql
                
                # Validate SQL is read-only
                if not self._is_read_only(sql):
                    last_error = "Query must be read-only (SELECT only). No INSERT, UPDATE, DELETE, DROP allowed."
                    continue
                
                # Execute SQL
                data = await database_service.execute_query(sql)
                
                execution_time = (datetime.now() - start_time).total_seconds() * 1000
                
                return SQLResult(
                    success=True,
                    sql=sql,
                    data=data,
                    row_count=len(data),
                    correction_attempts=attempt,
                    tables_used=tables_used,
                    execution_time_ms=execution_time
                )
                
            except Exception as e:
                last_error = str(e)
                print(f"⚠️ Attempt {attempt + 1} failed: {last_error}")
                
                # If this was the last attempt, return error
                if attempt == self.MAX_CORRECTION_ATTEMPTS - 1:
                    execution_time = (datetime.now() - start_time).total_seconds() * 1000
                    return SQLResult(
                        success=False,
                        sql=last_sql,
                        data=[],
                        row_count=0,
                        error=f"Failed after {self.MAX_CORRECTION_ATTEMPTS} attempts. Last error: {last_error}",
                        correction_attempts=attempt + 1,
                        tables_used=tables_used,
                        execution_time_ms=execution_time
                    )
        
        # Should not reach here
        return SQLResult(
            success=False,
            sql=last_sql,
            data=[],
            row_count=0,
            error="Unknown error in correction loop",
            correction_attempts=self.MAX_CORRECTION_ATTEMPTS,
            tables_used=tables_used,
            execution_time_ms=0
        )
    
    async def _generate_corrected_sql(
        self,
        question: str,
        failed_sql: str,
        error: str,
        tables: List[str]
    ) -> Tuple[str, List[str]]:
        """Generate corrected SQL based on error feedback"""
        
        # Get relevant joins
        relevant_joins = table_selector.get_relevant_joins(question)
        
        prompt = f"""You are an expert SQL query generator for a MySQL healthcare database.

The previous SQL query failed. Please fix it based on the error.

=== PREVIOUS SQL (FAILED) ===
{failed_sql}

=== ERROR MESSAGE ===
{error}

=== CANONICAL JOIN PATHS (MUST USE) ===
"""
        
        for join in relevant_joins:
            prompt += f"""
• {join['path']}:
  SQL: {join['sql']}
"""
        
        prompt += f"""
=== ORIGINAL QUESTION ===
{question}

=== INSTRUCTIONS ===
1. Fix the SQL query based on the error message
2. Use the canonical join paths shown above
3. Return ONLY the corrected SQL query, no explanations

Corrected SQL:"""
        
        try:
            response = await llm_client.generate(
                prompt=prompt,
                max_tokens=1000,
                temperature=0.1
            )
            
            sql = self._extract_sql(response)
            return sql, tables
            
        except Exception as e:
            print(f"❌ Correction generation error: {e}")
            raise
    
    def _is_read_only(self, sql: str) -> bool:
        """Check if SQL is read-only (SELECT only)"""
        sql_upper = sql.upper().strip()
        
        # Must start with SELECT
        if not sql_upper.startswith('SELECT'):
            return False
        
        # Must not contain dangerous keywords
        dangerous = ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'TRUNCATE', 'ALTER', 'CREATE', 'GRANT', 'REVOKE']
        for keyword in dangerous:
            if re.search(rf'\b{keyword}\b', sql_upper):
                return False
        
        return True
    
    # ========== QUERY EXECUTION ==========
    
    async def ask(self, question: str) -> SQLResult:
        """
        Main entry point: Ask a question and get results
        
        This is the primary method for using the Schema-Aware RAG system.
        It handles table selection, SQL generation, execution, and self-correction.
        
        Args:
            question: Natural language question
            
        Returns:
            SQLResult with query results or error
        """
        print(f"📝 Question: {question}")
        
        # Use correction loop for robustness
        result = await self.execute_with_correction(question)
        
        if result.success:
            print(f"✅ Success: {result.row_count} rows in {result.execution_time_ms:.0f}ms")
            if result.correction_attempts > 0:
                print(f"   (Required {result.correction_attempts} correction attempts)")
        else:
            print(f"❌ Failed: {result.error}")
        
        return result


# Singleton instance
schema_aware_rag = SchemaAwareRAGService()


async def main():
    """Test the Schema-Aware RAG Service"""
    print("=" * 60)
    print("Schema-Aware RAG Service Test")
    print("=" * 60)
    
    # Initialize
    if not await schema_aware_rag.initialize():
        print("❌ Failed to initialize")
        return
    
    # Train on database schema
    await schema_aware_rag.train_on_database_schema()
    
    # Add core training examples with CORRECT join paths
    training_examples = [
        {
            "question": "show me the disease with highest patients",
            "sql": """SELECT
    d.name AS disease,
    COUNT(DISTINCT c.id) AS patient_count
FROM claims c
JOIN diagnoses d ON d.id = CAST(c.diagnosis AS UNSIGNED)
WHERE c.diagnosis REGEXP '^[0-9]+$'
GROUP BY d.name
ORDER BY patient_count DESC
LIMIT 1""",
            "tag": "disease_highest_patients",
            "domain": "clinical"
        },
        {
            "question": "which disease has the most claims in Kogi state",
            "sql": """SELECT
    d.name AS disease,
    COUNT(DISTINCT c.id) AS claim_count
FROM claims c
JOIN users u ON c.user_id = u.id
JOIN states s ON u.state = s.id
JOIN diagnoses d ON d.id = CAST(c.diagnosis AS UNSIGNED)
WHERE s.name LIKE '%Kogi%'
AND c.diagnosis REGEXP '^[0-9]+$'
GROUP BY d.name
ORDER BY claim_count DESC
LIMIT 1""",
            "tag": "disease_by_state",
            "domain": "clinical"
        },
        {
            "question": "top 5 diagnoses by patient count",
            "sql": """SELECT
    d.name AS diagnosis,
    COUNT(DISTINCT c.id) AS patient_count
FROM claims c
JOIN diagnoses d ON d.id = CAST(c.diagnosis AS UNSIGNED)
WHERE c.diagnosis REGEXP '^[0-9]+$'
GROUP BY d.name
ORDER BY patient_count DESC
LIMIT 5""",
            "tag": "top_diagnoses",
            "domain": "clinical"
        },
        {
            "question": "how many claims were processed",
            "sql": "SELECT COUNT(*) AS total_claims FROM claims",
            "tag": "total_claims",
            "domain": "clinical"
        },
        {
            "question": "which provider handled the most claims",
            "sql": """SELECT
    p.name AS provider,
    COUNT(c.id) AS claim_count
FROM claims c
JOIN providers p ON c.provider_id = p.id
GROUP BY p.id, p.name
ORDER BY claim_count DESC
LIMIT 1""",
            "tag": "top_provider",
            "domain": "providers"
        },
    ]
    
    for ex in training_examples:
        await schema_aware_rag.train_question_sql(
            question=ex['question'],
            sql=ex['sql'],
            tag=ex['tag'],
            domain=ex['domain']
        )
    
    # Test queries
    test_questions = [
        "show me the disease with highest patients",
        "which disease has the most claims in Kogi state",
        "how many claims are there in total",
    ]
    
    print("\n" + "=" * 60)
    print("Running Test Queries")
    print("=" * 60)
    
    for question in test_questions:
        print(f"\n{'-' * 60}")
        result = await schema_aware_rag.ask(question)
        print(f"SQL: {result.sql}")
        print(f"Tables: {result.tables_used}")
        if result.success and result.data:
            print(f"Sample data: {result.data[:3]}")


if __name__ == "__main__":
    asyncio.run(main())

