"""
Domain 3.3: Explainability & Trust Layer
Makes outputs understandable and defensible
"""

from typing import Dict, List, Optional, Any
import re
from datetime import datetime


class ExplainabilityEngine:
    """
    SQL Explanation Engine and Result Provenance
    """
    
    def explain_sql(self, sql: str, query: str) -> Dict[str, Any]:
        """
        Translate SQL → plain English explanation
        
        Returns:
            Explanation dictionary with:
            - tables_used
            - join_logic
            - filters_applied
            - aggregations_computed
            - plain_english
        """
        if not sql:
            return {'tables_used': [], 'join_logic': '', 'filters_applied': [], 'aggregations_computed': [], 'plain_english': 'No SQL query provided'}
        sql_upper = sql.upper()
        
        # Extract tables used
        tables_used = self._extract_tables(sql)
        
        # Extract join logic
        join_logic = self._extract_joins(sql)
        
        # Extract filters
        filters_applied = self._extract_filters(sql)
        
        # Extract aggregations
        aggregations_computed = self._extract_aggregations(sql)
        
        # Generate plain English explanation
        plain_english = self._generate_plain_english(
            query, tables_used, join_logic, filters_applied, aggregations_computed
        )
        
        return {
            'tables_used': tables_used,
            'join_logic': join_logic,
            'filters_applied': filters_applied,
            'aggregations_computed': aggregations_computed,
            'plain_english': plain_english
        }
    
    def create_result_provenance(self, query: str, sql: str, results: List[Dict], 
                                execution_time: float, confidence: float) -> Dict[str, Any]:
        """
        Attach metadata for result provenance
        
        Returns:
            Provenance dictionary with:
            - query_timestamp
            - tables_involved
            - row_counts_scanned
            - confidence_score
            - execution_time_ms
        """
        tables_involved = self._extract_tables(sql)
        
        return {
            'query_timestamp': datetime.now().isoformat(),
            'user_question': query,
            'sql_generated': sql,
            'tables_involved': tables_involved,
            'row_counts_scanned': len(results),
            'confidence_score': confidence,
            'execution_time_ms': execution_time * 1000 if execution_time else None
        }
    
    def generate_user_facing_justification(self, explanation: Dict[str, Any]) -> str:
        """
        Generate user-facing justification
        
        Example:
        "This answer is based on claims, users, and providers tables 
        filtered by approved claims in 2024."
        """
        tables = explanation.get('tables_used', [])
        filters = explanation.get('filters_applied', [])
        aggregations = explanation.get('aggregations_computed', [])
        
        # Build justification
        parts = []
        
        # Tables
        if tables:
            if len(tables) == 1:
                parts.append(f"the {tables[0]} table")
            else:
                parts.append(f"the {', '.join(tables[:-1])}, and {tables[-1]} tables")
        
        # Filters
        if filters:
            filter_descriptions = []
            for filter_info in filters:
                if filter_info.get('type') == 'time':
                    filter_descriptions.append(filter_info.get('value', '').replace('_', ' '))
                elif filter_info.get('type') == 'status':
                    filter_descriptions.append(f"{filter_info.get('value', '')} status")
            
            if filter_descriptions:
                parts.append(f"filtered by {', '.join(filter_descriptions)}")
        
        # Aggregations
        if aggregations:
            agg_descriptions = []
            for agg in aggregations:
                if agg.get('type') == 'COUNT':
                    agg_descriptions.append("count")
                elif agg.get('type') == 'AVG':
                    agg_descriptions.append("average")
                elif agg.get('type') == 'SUM':
                    agg_descriptions.append("sum")
            
            if agg_descriptions:
                parts.append(f"with {', '.join(agg_descriptions)} calculations")
        
        if parts:
            justification = f"This answer is based on {', '.join(parts)}."
        else:
            justification = "This answer is based on the database query results."
        
        return justification
    
    def _extract_tables(self, sql: str) -> List[str]:
        """Extract table names from SQL"""
        tables = []
        sql_upper = sql.upper()
        
        # Find FROM clause
        from_match = re.search(r'FROM\s+(\w+)', sql_upper)
        if from_match:
            tables.append(from_match.group(1).lower())
        
        # Find JOIN clauses
        join_matches = re.findall(r'JOIN\s+(\w+)', sql_upper)
        for match in join_matches:
            tables.append(match.lower())
        
        return list(set(tables))  # Remove duplicates
    
    def _extract_joins(self, sql: str) -> List[Dict[str, str]]:
        """Extract join logic from SQL"""
        joins = []
        sql_upper = sql.upper()
        
        # Find JOIN ... ON patterns (more flexible pattern)
        join_pattern = r'JOIN\s+(\w+)\s+(?:\w+\s+)?ON\s+([^\s=]+)\s*=\s*([^\s,;\)]+)'
        join_matches = re.finditer(join_pattern, sql_upper, re.IGNORECASE | re.DOTALL)
        
        for match in join_matches:
            joins.append({
                'table': match.group(1).lower(),
                'left_column': match.group(2).strip().lower(),
                'right_column': match.group(3).strip().lower()
            })
        
        # Also try simpler pattern if no joins found
        if not joins:
            # Look for JOIN table_name patterns
            simple_join_pattern = r'JOIN\s+(\w+)'
            simple_matches = re.finditer(simple_join_pattern, sql_upper, re.IGNORECASE)
            for match in simple_matches:
                joins.append({
                    'table': match.group(1).lower(),
                    'left_column': 'unknown',
                    'right_column': 'unknown'
                })
        
        return joins
    
    def _extract_filters(self, sql: str) -> List[Dict[str, Any]]:
        """Extract filter conditions from SQL"""
        filters = []
        sql_upper = sql.upper()
        
        # Find WHERE clause
        where_match = re.search(r'WHERE\s+(.*?)(?:\s+GROUP|\s+ORDER|\s+LIMIT|$)', sql_upper, re.IGNORECASE | re.DOTALL)
        if where_match:
            where_clause = where_match.group(1)
            
            # Extract time filters
            if 'YEAR' in where_clause:
                filters.append({'type': 'time', 'value': 'year_filter'})
            if 'DATE' in where_clause:
                filters.append({'type': 'time', 'value': 'date_filter'})
            
            # Extract status filters
            if 'STATUS' in where_clause:
                if '= 1' in where_clause or '= 0' in where_clause:
                    filters.append({'type': 'status', 'value': 'status_filter'})
        
        return filters
    
    def _extract_aggregations(self, sql: str) -> List[Dict[str, str]]:
        """Extract aggregation functions from SQL"""
        aggregations = []
        sql_upper = sql.upper()
        
        # Find aggregation functions
        agg_patterns = {
            'COUNT': r'COUNT\s*\([^)]+\)',
            'AVG': r'AVG\s*\([^)]+\)',
            'SUM': r'SUM\s*\([^)]+\)',
            'MAX': r'MAX\s*\([^)]+\)',
            'MIN': r'MIN\s*\([^)]+\)'
        }
        
        for agg_type, pattern in agg_patterns.items():
            if re.search(pattern, sql_upper):
                aggregations.append({'type': agg_type})
        
        return aggregations
    
    def _generate_plain_english(self, query: str, tables: List[str], 
                               joins: List[Dict], filters: List[Dict], 
                               aggregations: List[Dict]) -> str:
        """Generate plain English explanation"""
        parts = []
        
        # Start with query
        parts.append(f"To answer: '{query}'")
        
        # Tables
        if tables:
            parts.append(f"we queried the {', '.join(tables)} table(s)")
        
        # Joins
        if joins:
            join_descriptions = []
            for join in joins:
                join_descriptions.append(
                    f"{join['left_column']} = {join['right_column']}"
                )
            parts.append(f"by joining on {', '.join(join_descriptions)}")
        
        # Filters
        if filters:
            parts.append("with filters applied")
        
        # Aggregations
        if aggregations:
            agg_types = [agg['type'] for agg in aggregations]
            parts.append(f"and computed {', '.join(agg_types)}")
        
        return ". ".join(parts) + "."


# Global instance
explainability_engine = ExplainabilityEngine()


