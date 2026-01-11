"""
Phase 4: Confidence Scorer
Calculates confidence scores and triggers clarification requests
"""

import re
from typing import Dict, Any, Optional, Tuple, List


class ConfidenceScorer:
    """
    Calculates confidence scores for generated SQL queries.
    
    Low confidence triggers clarification requests when:
    - Joins > expected
    - Tables outside domain used
    - Aggregation unclear
    """
    
    # Expected join count for Clinical Claims & Diagnosis domain
    EXPECTED_JOIN_COUNT_DOMAIN1 = {
        'frequency': 3,  # claims → service_summaries → service_summary_diagnosis → diagnoses
        'trend': 3,      # Same as frequency
        'cost': 3,       # Same as frequency
        'service': 5,    # Adds claims_services → services
    }
    
    # Expected join count for Providers & Facilities Performance domain
    EXPECTED_JOIN_COUNT_DOMAIN2 = {
        'provider_volume': 1,  # providers → claims
        'provider_diagnosis': 4,  # providers → claims → service_summaries → service_summary_diagnosis → diagnoses
        'provider_service': 3,  # providers → claims → claims_services → services
        'provider_trend': 1,  # providers → claims
    }
    
    # Domain 1 tables (allowed)
    DOMAIN1_TABLES = [
        'claims', 'service_summaries', 'service_summary_diagnosis',
        'diagnoses', 'claims_services', 'services'
    ]
    
    # Domain 2 tables (allowed)
    DOMAIN2_TABLES = [
        'providers', 'claims', 'service_summaries', 'service_summary_diagnosis',
        'diagnoses', 'claims_services', 'services'
    ]
    
    # Out-of-domain tables (not allowed)
    OUT_OF_DOMAIN_TABLES = [
        'users', 'payments', 'roles', 'permissions',
        'accreditation', 'telescope', 'admin', 'metadata', 'wallets', 'ratings'
    ]
    
    def score(self, sql: str, query: str, intent: str, domain: str = 'clinical_claims_diagnosis') -> Tuple[float, Optional[str]]:
        """
        Calculate confidence score for SQL query.
        
        Args:
            sql: Generated SQL query
            query: Original natural language query
            intent: Classified intent (FREQUENCY_VOLUME, TREND_TIME_SERIES, etc.)
            domain: Domain the query belongs to ('clinical_claims_diagnosis' or 'providers_facilities')
            
        Returns:
            Tuple of (confidence_score, clarification_message)
            - confidence_score: 0.0 to 1.0
            - clarification_message: None if confident, message if clarification needed
        """
        if not sql:
            return (0.0, "No SQL query generated. Please try rephrasing your question.")
        sql_upper = sql.upper()
        query_lower = query.lower()
        
        # Start with base confidence
        confidence = 0.8

        # Detect disease aggregation structure (non-state)
        is_disease_query = any(keyword in query_lower for keyword in [
            'disease', 'diagnosis', 'diagnoses'
        ])
        has_disease_structure = (
            'GROUP BY' in sql_upper and
            'COUNT' in sql_upper and
            ('D.NAME' in sql_upper or 'DIAGNOSES.NAME' in sql_upper) and
            'STATENAME' not in sql_upper
        )
        
        # Determine expected joins and allowed tables based on domain
        if domain == 'providers_facilities':
            expected_joins_map = self.EXPECTED_JOIN_COUNT_DOMAIN2
            allowed_tables = self.DOMAIN2_TABLES
            domain_name = "providers & facilities performance"
        else:
            expected_joins_map = self.EXPECTED_JOIN_COUNT_DOMAIN1
            allowed_tables = self.DOMAIN1_TABLES
            domain_name = "clinical claims analysis"
        
        # Check 1: Join count
        # Allow users/states tables for state filtering queries
        is_state_query = any(state in query_lower for state in [
            'zamfara', 'kano', 'kogi', 'kaduna', 'fct', 'abuja', 'adamawa',
            'sokoto', 'rivers', 'osun', 'lagos', 'state', 'states'
        ])
        
        join_count = self._count_joins(sql_upper)
        # Map intent to expected joins
        intent_lower = intent.lower()
        expected_joins = expected_joins_map.get(intent_lower, 3)
        
        # State queries need 2 extra joins (users + states), so add 2 to expected count
        if is_state_query:
            expected_joins += 2
        
        if join_count > expected_joins + 1:
            # For state queries, be more lenient - they need extra joins
            if is_state_query:
                # State queries need users + states joins, so allow 2 extra joins
                if join_count > expected_joins + 3:
                    confidence -= 0.2
                    return (
                        confidence,
                        f"This query requires clarification to ensure accurate {domain_name} interpretation. "
                        "The query involves more relationships than expected. "
                        "Please specify exactly what you want to analyze."
                    )
                else:
                    # Within acceptable range for state queries, just reduce confidence slightly
                    confidence -= 0.05
            else:
                # For disease queries with correct aggregation, don't block—just reduce confidence
                if is_disease_query and has_disease_structure and join_count <= expected_joins + 3:
                    confidence -= 0.05
                else:
                    confidence -= 0.2
                    return (
                        confidence,
                        f"This query requires clarification to ensure accurate {domain_name} interpretation. "
                        "The query involves more relationships than expected. "
                        "Please specify exactly what you want to analyze."
                    )
        
        # Check 2: Out-of-domain tables
        # is_state_query already defined above
        out_of_domain_tables = self._find_out_of_domain_tables(sql_upper, allowed_tables)
        # Filter out users/states if it's a state query
        if is_state_query:
            out_of_domain_tables = [t for t in out_of_domain_tables if t.lower() not in ['users', 'states']]
        
        if out_of_domain_tables:
            confidence -= 0.3
            return (
                confidence,
                f"This question requires clarification to ensure accurate {domain_name} interpretation. "
                f"The query references tables ({', '.join(out_of_domain_tables)}) that are outside "
                f"the {domain_name} scope."
            )
        
        # Check 3: Unclear aggregation
        # For state queries, be more lenient - they often need complex joins
        if not self._has_clear_aggregation(sql_upper, intent):
            if is_state_query:
                # State queries are complex - just reduce confidence slightly, don't block
                confidence -= 0.05
            else:
                # For non-state queries, reduce confidence but don't block unless very low
                confidence -= 0.1
                # Only block if confidence is already very low
                if confidence < 0.3:
                    return (
                        confidence,
                        "This question requires clarification to ensure accurate clinical interpretation. "
                        "The aggregation method is unclear. Please specify if you want counts, averages, totals, or trends."
                    )
        
        # Check 4: Missing required joins for intent
        if not self._has_required_joins(sql_upper, intent):
            confidence -= 0.1
        
        # Normalize confidence to 0.0-1.0
        confidence = max(0.0, min(1.0, confidence))
        
        # For state queries, be much more lenient - they're complex but valid
        if is_state_query:
            # State queries are inherently complex - only block if confidence is extremely low
            # Lowered threshold from 0.2 to 0.1 for state queries
            if confidence < 0.1:
                return (
                    confidence,
                    "This question requires clarification to ensure accurate clinical interpretation. "
                    "Please rephrase your question to be more specific about what you want to analyze."
                )
        else:
            # For non-state queries, use standard threshold with leniency for well-formed disease aggregations
            if is_disease_query and has_disease_structure and confidence >= 0.3:
                # Allow through
                return (confidence, None)
            # Lowered from 0.6 to 0.4 to reduce false positives
            if confidence < 0.4:
                return (
                    confidence,
                    "This question requires clarification to ensure accurate clinical interpretation. "
                    "Please rephrase your question to be more specific about what you want to analyze."
                )
        
        return (confidence, None)
    
    def _count_joins(self, sql: str) -> int:
        """Count number of JOINs in SQL"""
        return len(re.findall(r'\bJOIN\b', sql, re.IGNORECASE))
    
    def _find_out_of_domain_tables(self, sql: str, allowed_tables: List[str]) -> List[str]:
        """Find tables that are outside the domain"""
        found = []
        for table in self.OUT_OF_DOMAIN_TABLES:
            # Check for table name in SQL (as whole word)
            pattern = rf'\b{table}\b'
            if re.search(pattern, sql, re.IGNORECASE):
                found.append(table)
        return found
    
    def _has_clear_aggregation(self, sql: str, intent: str) -> bool:
        """Check if SQL has clear aggregation for the intent"""
        if intent == 'FREQUENCY_VOLUME':
            return 'COUNT' in sql
        elif intent == 'TREND_TIME_SERIES':
            return 'COUNT' in sql and ('DATE_FORMAT' in sql or 'DATE(' in sql)
        elif intent == 'COST_FINANCIAL':
            return 'AVG' in sql or 'SUM' in sql
        elif intent == 'SERVICE_UTILIZATION':
            return 'COUNT' in sql
        return True  # Default: assume clear
    
    def _has_required_joins(self, sql: str, intent: str) -> bool:
        """Check if SQL has required joins for the intent"""
        if intent in ['FREQUENCY_VOLUME', 'TREND_TIME_SERIES', 'COST_FINANCIAL']:
            # Must have: claims → service_summaries → service_summary_diagnosis → diagnoses
            return (
                'SERVICE_SUMMARIES' in sql and
                'SERVICE_SUMMARY_DIAGNOSIS' in sql and
                'DIAGNOSES' in sql
            )
        elif intent == 'SERVICE_UTILIZATION':
            # Must also have: claims_services → services
            return (
                'SERVICE_SUMMARIES' in sql and
                'SERVICE_SUMMARY_DIAGNOSIS' in sql and
                'DIAGNOSES' in sql and
                'CLAIMS_SERVICES' in sql and
                'SERVICES' in sql
            )
        return True  # Default: assume OK


# Global instance
confidence_scorer = ConfidenceScorer()

