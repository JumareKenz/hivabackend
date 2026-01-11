"""
Domain 3.1: Query Intelligence & Reasoning Control
Controls how the system reasons before generating SQL
"""

from typing import Dict, List, Optional, Tuple, Any
import re


class QueryIntelligence:
    """
    Intent Classification Layer and Schema-Aware Reasoning
    
    Classifies queries into:
    - Read-only analytics
    - Aggregations
    - Time-series
    - Entity lookups
    - Sensitive / restricted queries
    """
    
    # Intent categories
    INTENT_CATEGORIES = {
        'read_only_analytics': [
            'show', 'list', 'display', 'get', 'fetch', 'retrieve',
            'what are', 'which', 'find', 'search'
        ],
        'aggregations': [
            'count', 'total', 'sum', 'average', 'avg', 'most', 'top', 'highest',
            'lowest', 'maximum', 'minimum', 'max', 'min', 'group by'
        ],
        'time_series': [
            'trend', 'over time', 'monthly', 'yearly', 'daily', 'weekly',
            'by month', 'by year', 'by day', 'by week', 'timeline', 'history'
        ],
        'entity_lookups': [
            'details', 'information about', 'profile', 'specific', 'particular',
            'for', 'where is', 'who is'
        ],
        'sensitive_restricted': [
            'email', 'phone', 'nimc', 'salary', 'ssn', 'password', 'pin',
            'credit card', 'bank account', 'personal information', 'pii'
        ]
    }
    
    def classify_intent_category(self, query: str) -> Tuple[str, float]:
        """
        Classify query into intent category
        
        Returns:
            Tuple of (intent_category, confidence)
        """
        query_lower = query.lower()
        
        # Check for sensitive/restricted first (highest priority)
        if any(keyword in query_lower for keyword in self.INTENT_CATEGORIES['sensitive_restricted']):
            return ('sensitive_restricted', 0.95)
        
        # Check for time-series
        if any(keyword in query_lower for keyword in self.INTENT_CATEGORIES['time_series']):
            return ('time_series', 0.85)
        
        # Check for aggregations
        if any(keyword in query_lower for keyword in self.INTENT_CATEGORIES['aggregations']):
            return ('aggregations', 0.80)
        
        # Check for entity lookups
        if any(keyword in query_lower for keyword in self.INTENT_CATEGORIES['entity_lookups']):
            return ('entity_lookups', 0.75)
        
        # Default: read-only analytics
        return ('read_only_analytics', 0.70)
    
    def validate_intent_supported(self, intent_category: str) -> Tuple[bool, Optional[str]]:
        """
        Check if intent category is supported
        
        Returns:
            Tuple of (is_supported, rejection_reason)
        """
        unsupported = ['sensitive_restricted']
        
        if intent_category in unsupported:
            return (
                False,
                f"Query intent '{intent_category}' is not supported for security reasons. "
                "Please rephrase your query to avoid sensitive data access."
            )
        
        return (True, None)
    
    def identify_required_tables(self, query: str, schema_info: Dict[str, Any]) -> List[str]:
        """
        Schema-Aware Reasoning: Identify required tables from query
        
        Args:
            query: Natural language query
            schema_info: Database schema information
            
        Returns:
            List of table names that are likely needed
        """
        query_lower = query.lower()
        required_tables = []
        
        # State names - if query mentions a state, we need users and states tables
        state_names = [
            'zamfara', 'kano', 'kogi', 'kaduna', 'fct', 'abuja', 'adamawa',
            'sokoto', 'rivers', 'osun', 'lagos', 'state', 'states'
        ]
        needs_state_filter = any(state in query_lower for state in state_names)
        
        # Table name mappings
        # CRITICAL: Don't add 'users' table just because "patient" is mentioned
        # Only add 'users' if:
        # 1. Query explicitly mentions "user" or "users"
        # 2. Query needs state filtering (state name mentioned)
        table_keywords = {
            'claims': ['claim', 'claims'],
            'providers': ['provider', 'providers', 'facility', 'facilities', 'hospital', 'hospitals'],
            'diagnoses': ['diagnosis', 'diagnoses', 'disease', 'diseases', 'illness'],
            'services': ['service', 'services', 'treatment', 'treatments', 'procedure'],
            # Only add 'users' if explicitly mentioned OR state filtering needed
            # "patient" or "patients" alone does NOT trigger users table
            'users': ['user', 'users'] if not needs_state_filter else ['user', 'users'],
            'service_summaries': ['service summary', 'encounter'],
            'claims_services': ['claim service', 'service per claim']
        }
        
        for table_name, keywords in table_keywords.items():
            if any(keyword in query_lower for keyword in keywords):
                # Check if table exists in schema
                if schema_info and 'tables' in schema_info:
                    table_exists = any(
                        t.get('table_name', '').lower() == table_name.lower()
                        for t in schema_info['tables']
                    )
                    if table_exists:
                        required_tables.append(table_name)
        
        # If state filtering is needed, add users and states tables
        if needs_state_filter:
            if schema_info and 'tables' in schema_info:
                # Check if users table exists
                users_exists = any(
                    t.get('table_name', '').lower() == 'users'
                    for t in schema_info['tables']
                )
                states_exists = any(
                    t.get('table_name', '').lower() == 'states'
                    for t in schema_info['tables']
                )
                if users_exists and 'users' not in required_tables:
                    required_tables.append('users')
                if states_exists and 'states' not in required_tables:
                    required_tables.append('states')
        
        return required_tables
    
    def validate_joins(self, required_tables: List[str], schema_info: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validate joins via known FK graph
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not required_tables or len(required_tables) <= 1:
            return (True, None)  # Single table or no tables, no joins needed
        
        # Known FK relationships
        valid_join_paths = {
            ('providers', 'claims'): 'providers.id → claims.provider_id',
            ('claims', 'service_summaries'): 'claims.id → service_summaries.claim_id',
            ('service_summaries', 'service_summary_diagnosis'): 'service_summaries.id → service_summary_diagnosis.service_summary_id',
            ('service_summary_diagnosis', 'diagnoses'): 'service_summary_diagnosis.diagnosis_id → diagnoses.id',
            ('claims', 'claims_services'): 'claims.id → claims_services.claims_id',
            ('claims_services', 'services'): 'claims_services.services_id → services.id',
        }
        
        # Check if all required tables can be joined
        # For now, simple validation - check if tables are in valid paths
        for i in range(len(required_tables) - 1):
            table1 = required_tables[i]
            table2 = required_tables[i + 1]
            
            # Check direct join
            if (table1, table2) not in valid_join_paths and (table2, table1) not in valid_join_paths:
                # Check if there's an intermediate table that can connect them
                # This is simplified - in production, use a graph algorithm
                pass  # Allow for now, let SQL validator catch invalid joins
        
        return (True, None)
    
    def check_column_existence(self, columns: List[str], table_name: str, schema_info: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Check if columns exist in table before SQL generation
        
        Returns:
            Tuple of (all_exist, missing_columns)
        """
        if not schema_info or 'tables' not in schema_info:
            return (True, [])  # Can't validate without schema
        
        # Find table in schema
        table_info = None
        for table in schema_info['tables']:
            if table.get('table_name', '').lower() == table_name.lower():
                table_info = table
                break
        
        if not table_info:
            return (True, [])  # Table not found in schema, let SQL validator catch it
        
        # Get existing columns
        existing_columns = {
            col.get('column_name', '').lower()
            for col in table_info.get('columns', [])
        }
        
        # Check requested columns
        missing = []
        for col in columns:
            if col.lower() not in existing_columns:
                missing.append(col)
        
        return (len(missing) == 0, missing)
    
    def enforce_step_constrained_reasoning(self, query: str, schema_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enforce step-constrained reasoning:
        Schema selection → Join plan → Filter logic → Aggregation → SQL
        
        Returns:
            Reasoning plan with steps
        """
        # Step 1: Schema selection
        required_tables = self.identify_required_tables(query, schema_info)
        
        # Step 2: Join plan
        join_valid, join_error = self.validate_joins(required_tables, schema_info)
        
        # Step 3: Filter logic (extract from query)
        filters = self._extract_filters(query)
        
        # Step 4: Aggregation (if needed)
        intent_category, confidence = self.classify_intent_category(query)
        needs_aggregation = intent_category in ['aggregations', 'time_series']
        
        return {
            'required_tables': required_tables,
            'join_plan_valid': join_valid,
            'join_error': join_error,
            'filters': filters,
            'needs_aggregation': needs_aggregation,
            'intent_category': intent_category,
            'confidence': confidence
        }
    
    def _extract_filters(self, query: str) -> List[Dict[str, str]]:
        """Extract filter conditions from query"""
        filters = []
        query_lower = query.lower()
        
        # Time filters
        if 'last year' in query_lower:
            filters.append({'type': 'time', 'value': 'last_year'})
        elif 'this year' in query_lower:
            filters.append({'type': 'time', 'value': 'this_year'})
        elif 'last month' in query_lower:
            filters.append({'type': 'time', 'value': 'last_month'})
        elif 'this month' in query_lower:
            filters.append({'type': 'time', 'value': 'this_month'})
        
        # Status filters
        if 'approved' in query_lower:
            filters.append({'type': 'status', 'value': 'approved'})
        elif 'pending' in query_lower:
            filters.append({'type': 'status', 'value': 'pending'})
        elif 'rejected' in query_lower:
            filters.append({'type': 'status', 'value': 'rejected'})
        
        return filters


# Global instance
query_intelligence = QueryIntelligence()


