"""
Domain 3.5: Performance, Cost & Reliability Controls
Ensure production readiness at scale
"""

from typing import Dict, Optional, Tuple, Any
import re
import time


class PerformanceControls:
    """
    Query Cost Estimation, Caching, and Fallback Handling
    """
    
    def estimate_query_cost(self, sql: str) -> Dict[str, Any]:
        """
        Predict scan size and execution time
        
        Returns:
            Dictionary with:
            - estimated_rows_scanned
            - estimated_execution_time_ms
            - complexity_score
            - warning_message (if any)
        """
        if not sql:
            return {'estimated_rows_scanned': 0, 'estimated_execution_time_ms': 0, 'complexity_score': 0, 'warning_message': None}
        sql_upper = sql.upper()
        
        # Count tables involved
        table_count = len(re.findall(r'\bFROM\s+(\w+)', sql_upper)) + len(re.findall(r'\bJOIN\s+(\w+)', sql_upper))
        
        # Count joins
        join_count = len(re.findall(r'\bJOIN\b', sql_upper))
        
        # Check for aggregations
        has_aggregation = bool(re.search(r'\b(COUNT|SUM|AVG|MAX|MIN)\s*\(', sql_upper))
        
        # Check for GROUP BY
        has_group_by = 'GROUP BY' in sql_upper
        
        # Estimate complexity
        complexity_score = table_count * 2 + join_count * 3
        if has_aggregation:
            complexity_score += 2
        if has_group_by:
            complexity_score += 2
        
        # Estimate rows scanned (simplified heuristic)
        # In production, use EXPLAIN or query planner
        estimated_rows = 1000 * table_count * (join_count + 1)
        
        # Estimate execution time (simplified)
        # Base time: 50ms per table, 30ms per join, 20ms per aggregation
        base_time = 50 * table_count
        join_time = 30 * join_count
        agg_time = 20 if has_aggregation else 0
        estimated_time_ms = base_time + join_time + agg_time
        
        # Generate warnings
        warnings = []
        if estimated_rows > 100000:
            warnings.append("Large scan detected - query may be slow")
        if join_count > 5:
            warnings.append("Complex join pattern - consider optimizing")
        if not re.search(r'\bWHERE\b', sql_upper) and not has_aggregation:
            warnings.append("No WHERE clause - may scan entire table")
        
        return {
            'estimated_rows_scanned': estimated_rows,
            'estimated_execution_time_ms': estimated_time_ms,
            'complexity_score': complexity_score,
            'warning_message': '; '.join(warnings) if warnings else None
        }
    
    def should_cache_query(self, query: str, sql: str) -> Tuple[bool, str]:
        """
        Determine if query should be cached
        
        Returns:
            Tuple of (should_cache, cache_key)
        """
        # Cache frequently asked questions
        cacheable_patterns = [
            r'\btotal\b.*\bclaims\b',
            r'\bcount\b.*\bclaims\b',
            r'\bmost common\b.*\bdiagnosis\b',
            r'\btop\s+\d+\b.*\bdiagnos\w+\b'
        ]
        
        query_lower = query.lower()
        for pattern in cacheable_patterns:
            if re.search(pattern, query_lower):
                # Generate cache key from normalized query
                cache_key = self._generate_cache_key(query, sql)
                return (True, cache_key)
        
        return (False, '')
    
    def _generate_cache_key(self, query: str, sql: str) -> str:
        """Generate cache key from query"""
        import hashlib
        # Normalize query (lowercase, remove extra spaces)
        normalized = ' '.join(query.lower().split())
        return hashlib.md5(normalized.encode()).hexdigest()
    
    # Fix 4: Error type classification for targeted recovery
    ERROR_TYPES = {
        'SCHEMA_ERROR': {
            'patterns': ['unknown column', "doesn't exist", 'no such table', 'table.*not found'],
            'recovery_strategy': 'regenerate_with_schema_hint',
            'max_retries': 2
        },
        'SYNTAX_ERROR': {
            'patterns': ['syntax error', 'sql syntax', 'parse error', 'unexpected token'],
            'recovery_strategy': 'regenerate_simplified',
            'max_retries': 2
        },
        'TYPE_ERROR': {
            'patterns': ['type mismatch', 'cannot cast', 'invalid type', 'conversion failed', 'truncated'],
            'recovery_strategy': 'regenerate_with_cast_hint',
            'max_retries': 1
        },
        'TIMEOUT_ERROR': {
            'patterns': ['timeout', 'too long', 'exceeded', 'killed'],
            'recovery_strategy': 'add_limit',
            'max_retries': 1
        },
        'VALIDATION_ERROR': {
            'patterns': ['phase 4 violation', 'select *', 'forbidden'],
            'recovery_strategy': 'regenerate_explicit_columns',
            'max_retries': 2
        }
    }
    
    def classify_error(self, error: str) -> dict:
        """
        Fix 4: Classify SQL execution error into categories for targeted recovery.
        
        Returns:
            dict with 'type', 'recovery_strategy', 'max_retries', 'details'
        """
        error_lower = error.lower()
        
        for error_type, config in self.ERROR_TYPES.items():
            for pattern in config['patterns']:
                if re.search(pattern, error_lower, re.IGNORECASE):
                    return {
                        'type': error_type,
                        'recovery_strategy': config['recovery_strategy'],
                        'max_retries': config['max_retries'],
                        'details': f"Matched pattern: {pattern}"
                    }
        
        # Unknown error type
        return {
            'type': 'UNKNOWN_ERROR',
            'recovery_strategy': 'refuse_safely',
            'max_retries': 0,
            'details': 'No known error pattern matched'
        }
    
    def get_recovery_hint(self, error_classification: dict, original_sql: str) -> str:
        """
        Generate a recovery hint for the LLM based on error type.
        """
        strategy = error_classification['recovery_strategy']
        
        hints = {
            'regenerate_with_schema_hint': (
                "PREVIOUS SQL FAILED: Column or table not found. "
                "Use ONLY these tables: claims, diagnoses, users, states, services. "
                "Verify all column names exist in schema before using."
            ),
            'regenerate_simplified': (
                "PREVIOUS SQL FAILED: Syntax error. "
                "Generate simpler SQL without subqueries. Use basic SELECT...FROM...WHERE...GROUP BY."
            ),
            'regenerate_with_cast_hint': (
                "PREVIOUS SQL FAILED: Type conversion error. "
                "For diagnosis joins, use: CAST(c.diagnosis AS UNSIGNED). "
                "Ensure all type conversions are explicit."
            ),
            'add_limit': (
                "PREVIOUS SQL FAILED: Query too slow. "
                "Add LIMIT 100 and appropriate WHERE filters to reduce result set."
            ),
            'regenerate_explicit_columns': (
                "PREVIOUS SQL FAILED: SELECT * is forbidden. "
                "List ALL columns explicitly: SELECT col1, col2, col3 FROM..."
            ),
            'refuse_safely': (
                "Cannot recover from this error. Please rephrase your question."
            )
        }
        
        return hints.get(strategy, hints['refuse_safely'])

    def handle_query_failure(self, sql: str, error: str, query: str) -> Dict[str, Any]:
        """
        Fallback & Failure Handling with error classification.
        
        Returns:
            Dictionary with:
            - explanation: Why SQL failed
            - clarifying_question: Suggested clarifying question
            - alternative_suggestion: Alternative query suggestion
            - error_classification: Fix 4 - Error type and recovery info
        """
        error_lower = error.lower()
        
        # Fix 4: Classify error for targeted recovery
        error_classification = self.classify_error(error)
        print(f"🔍 [ERROR_CLASSIFIER] Type: {error_classification['type']}, Strategy: {error_classification['recovery_strategy']}")
        
        # Analyze error type
        if 'unknown column' in error_lower or 'column' in error_lower:
            explanation = "The query references a column that doesn't exist in the database schema."
            clarifying_question = "Please check the column names and try again. Would you like to see the available columns?"
            alternative = "Try rephrasing your query with different column names."
        
        elif 'table' in error_lower and 'doesn\'t exist' in error_lower:
            explanation = "The query references a table that doesn't exist in the database."
            clarifying_question = "Please check the table names. Would you like to see the available tables?"
            alternative = "Try rephrasing your query to use existing tables."
        
        elif 'syntax' in error_lower:
            explanation = "The generated SQL has a syntax error."
            clarifying_question = "Please try rephrasing your question more clearly."
            alternative = "Try breaking your question into smaller parts."
        
        elif 'timeout' in error_lower:
            explanation = "The query took too long to execute."
            clarifying_question = "Would you like to add filters to reduce the data scanned?"
            alternative = "Try adding date filters or limiting the number of results."
        
        elif 'select *' in error_lower or 'forbidden' in error_lower:
            explanation = "The generated SQL used forbidden patterns (SELECT *)."
            clarifying_question = "The system will regenerate with explicit columns."
            alternative = "Automatic retry with explicit column selection."
        
        else:
            explanation = f"The query failed with error: {error[:200]}"
            clarifying_question = "Please try rephrasing your question or adding more specific details."
            alternative = "Try simplifying your question or breaking it into smaller parts."
        
        return {
            'explanation': explanation,
            'clarifying_question': clarifying_question,
            'alternative_suggestion': alternative,
            'original_error': error,
            'error_classification': error_classification,
            'recovery_hint': self.get_recovery_hint(error_classification, sql)
        }


# Global instance
performance_controls = PerformanceControls()


