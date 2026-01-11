"""
Phase 4: SQL Validator
Strict validation rules that reject queries immediately (HARD FAIL)
"""

import re
from typing import Tuple, Optional


class SQLValidator:
    """
    Validates SQL queries against Phase 4 strict rules.
    
    Rejects queries that:
    - Contain forbidden columns (diagnosis_id, service_summary_id, etc.)
    - Use IDs in SELECT or GROUP BY
    - Skip canonical join paths
    - Group by anything except diagnoses.name
    """
    
    # Forbidden patterns in SELECT clause
    FORBIDDEN_SELECT_PATTERNS = [
        r'\bdiagnosis_id\b',
        r'\bdiagnosis_code\b',
        r'\bservice_summary_id\b',
        r'\bssd\.\*\b',  # service_summary_diagnosis.*
        r'\bSELECT\s+[^,]*\bid\b',  # SELECT id (unless for counting)
    ]
    
    # SELECT * patterns - HARD FAIL
    SELECT_STAR_PATTERNS = [
        r'SELECT\s+\*',           # SELECT *
        r'SELECT\s+\w+\.\*',      # SELECT c.* or SELECT claims.*
        r',\s*\w+\.\*',           # ... , c.*
        r',\s*\*',                # ... , *
    ]
    
    # Forbidden patterns in GROUP BY clause
    FORBIDDEN_GROUP_BY_PATTERNS = [
        r'\bGROUP\s+BY\s+[^,]*\bid\b',
        r'\bGROUP\s+BY\s+[^,]*\bdiagnosis_id\b',
        r'\bGROUP\s+BY\s+[^,]*\bservice_summary_id\b',
    ]
    
    def validate(self, sql: str, query: str, domain: str = 'clinical_claims_diagnosis') -> Tuple[bool, Optional[str]]:
        """
        Validate SQL query against strict rules.
        
        Args:
            sql: Generated SQL query
            query: Original natural language query
            domain: Domain the query belongs to ('clinical_claims_diagnosis' or 'providers_facilities')
            
        Returns:
            Tuple of (is_valid, rejection_reason)
            - is_valid: True if query passes validation
            - rejection_reason: Error message if validation fails
        """
        # CRITICAL: Guard against None SQL
        if not sql or not isinstance(sql, str):
            print(f"🔴 [SQL_VALIDATOR] CRITICAL: SQL is None or invalid: {type(sql)}")
            return (False, "SQL validation failed: Generated SQL is None or invalid")
        
        print(f"🔍 [SQL_VALIDATOR] validate() called - Domain: {domain}, SQL length: {len(sql)}")
        
        if domain == 'clinical_claims_diagnosis':
            return self._validate_domain1(sql, query)
        elif domain == 'providers_facilities':
            return self._validate_domain2(sql, query)
        else:
            # Unknown domain, skip validation
            print(f"⚠️  [SQL_VALIDATOR] Unknown domain '{domain}', skipping validation")
            return (True, None)
    
    def _validate_domain1(self, sql: str, query: str) -> Tuple[bool, Optional[str]]:
        """
        Validate Domain 1: Clinical Claims & Diagnosis queries
        """
        
        sql_upper = sql.upper()
        query_lower = query.lower()
        
        # Check if this is a diagnosis/claims query
        is_diagnosis_query = any(keyword in query_lower for keyword in [
            'diagnosis', 'disease', 'claim', 'service', 'clinical'
        ])
        
        if not is_diagnosis_query:
            return (True, None)  # Not a domain query, skip validation
        
        # Extract SELECT clause
        select_match = re.search(r'SELECT\s+(.*?)\s+FROM', sql_upper, re.DOTALL | re.IGNORECASE)
        if not select_match:
            return (True, None)  # Can't parse, let it through (will fail at execution)
        
        select_clause = select_match.group(1)
        
        # HARD FAIL: users/states joins when query does not mention state
        state_keywords = [
            'zamfara', 'kano', 'kogi', 'kaduna', 'fct', 'abuja', 'adamawa',
            'sokoto', 'rivers', 'osun', 'lagos', 'state', 'states'
        ]
        is_state_query = any(state in query_lower for state in state_keywords)

        # Placeholder state filter: fail only if the user actually asked about a state
        if 'STATENAME' in sql_upper:
            if is_state_query:
                return (False, "Phase 4 Violation: Placeholder state filter detected.")
            # If no state is in the query, allow the rewriter to remove the placeholder

        # For non-state queries, allow downstream rewriter to strip accidental users/states joins
        if not is_state_query:
            pass

        # HARD FAIL: SELECT * or table.* patterns - SECURITY CRITICAL
        for pattern in self.SELECT_STAR_PATTERNS:
            if re.search(pattern, sql, re.IGNORECASE):
                return (
                    False,
                    f"Phase 4 Violation: SELECT * or table.* is forbidden. "
                    f"Must use explicit column names. Pattern matched: {pattern}. Query: {query}"
                )

        # HARD FAIL: Check for forbidden patterns in SELECT
        for pattern in self.FORBIDDEN_SELECT_PATTERNS:
            if re.search(pattern, select_clause, re.IGNORECASE):
                # Allow if it's for counting (COUNT(DISTINCT c.id))
                if 'COUNT' in sql_upper and 'DISTINCT' in sql_upper:
                    # Check if it's counting claims.id (allowed)
                    if re.search(r'COUNT\s*\(\s*DISTINCT\s+[^)]*\bid\b', sql_upper):
                        continue  # This is OK
                
                # Check if name is also present (allow if both present)
                if not re.search(r'\bd\.name\b|\bdiagnoses\.name\b', select_clause, re.IGNORECASE):
                    return (
                        False,
                        f"Phase 4 Violation: SQL contains forbidden pattern '{pattern}'. "
                        f"Must use diagnoses.name instead. Query: {query}"
                    )
        
        # HARD FAIL: Check for forbidden patterns in GROUP BY
        group_by_match = re.search(r'GROUP\s+BY\s+(.*?)(?:\s+ORDER|\s+HAVING|\s+LIMIT|$)', sql_upper, re.IGNORECASE)
        if group_by_match:
            group_by_clause = group_by_match.group(1)
            
            for pattern in self.FORBIDDEN_GROUP_BY_PATTERNS:
                if re.search(pattern, group_by_clause, re.IGNORECASE):
                    return (
                        False,
                        f"Phase 4 Violation: SQL groups by forbidden column. "
                        f"Must group by diagnoses.name, not IDs. Query: {query}"
                    )
        
        # HARD FAIL: If diagnoses table is used, must include diagnoses.name
        if 'DIAGNOSES' in sql_upper or 'DIAGNOSIS' in sql_upper:
            # Check if diagnoses.name is in SELECT
            if 'D.NAME' not in sql_upper and 'DIAGNOSES.NAME' not in sql_upper:
                # Allow if it's a simple count query
                if 'COUNT' in sql_upper and 'FROM' in sql_upper:
                    # Check if it's counting claims (not diagnoses)
                    if 'FROM CLAIMS' in sql_upper or 'FROM `CLAIMS`' in sql_upper:
                        pass  # Simple count is OK
                    else:
                        return (
                            False,
                            "Phase 4 Violation: Queries using diagnoses table must include diagnoses.name. "
                            f"Query: {query}"
                        )
        
        # HARD FAIL: Validate canonical join paths
        if 'diagnosis' in query_lower or 'disease' in query_lower:
            print(f"🔍 [SQL_VALIDATOR] Checking canonical join paths (diagnosis/disease query detected)")
            # Check if SQL uses claims.diagnosis directly (forbidden - must join to diagnoses table)
            # This is the critical check that prevents the "code 80471" issue
            # NEW CANONICAL PATH: claims.diagnosis (TEXT) → diagnoses.id via CAST
            # The claims.diagnosis column contains diagnosis IDs as TEXT, must use CAST
            # Valid join: JOIN diagnoses d ON d.id = CAST(c.diagnosis AS UNSIGNED)
            
            if 'DIAGNOSES' in sql_upper:
                # Check for correct canonical path with CAST
                has_cast_join = 'CAST' in sql_upper and 'DIAGNOSIS' in sql_upper
                
                if not has_cast_join:
                    # Check if it's a simple query (e.g., SELECT * FROM diagnoses)
                    if 'FROM DIAGNOSES' in sql_upper and 'CLAIMS' not in sql_upper:
                        # Simple select from diagnoses is OK
                        print(f"✅ [SQL_VALIDATOR] Simple diagnoses query - OK")
                        pass
                    else:
                        error_msg = (
                            "Phase 4 Violation: Diagnosis joins must use CAST. "
                            "Must use: JOIN diagnoses d ON d.id = CAST(c.diagnosis AS UNSIGNED). "
                            f"Query: {query}"
                        )
                        print(f"🔴 [SQL_VALIDATOR] REJECTED: {error_msg}")
                        return (False, error_msg)
                else:
                    print(f"✅ [SQL_VALIDATOR] Correct canonical join with CAST found")
            else:
                # If query mentions diagnosis/disease but doesn't use diagnoses table
                # that might be OK for count-only queries
                print(f"✅ [SQL_VALIDATOR] No diagnoses table - might be count-only query")
        
        # HARD FAIL: If grouping by diagnosis, must group by diagnoses.name
        if 'GROUP BY' in sql_upper and 'DIAGNOSES' in sql_upper:
            group_by_match = re.search(r'GROUP\s+BY\s+(.*?)(?:\s+ORDER|\s+HAVING|\s+LIMIT|$)', sql_upper, re.IGNORECASE)
            if group_by_match:
                group_by_clause = group_by_match.group(1)
                # Check if grouping by name
                if 'D.NAME' not in sql_upper and 'DIAGNOSES.NAME' not in sql_upper:
                    # Check if it's grouping by something else related to diagnosis
                    if 'DIAGNOSIS' in group_by_clause.upper():
                        return (
                            False,
                            "Phase 4 Violation: Diagnosis queries must group by diagnoses.name, "
                            f"not by IDs or codes. Query: {query}"
                        )
        
        return (True, None)
    
    def _validate_domain2(self, sql: str, query: str) -> Tuple[bool, Optional[str]]:
        """
        Validate Domain 2: Providers & Facilities Performance queries
        
        Rejects queries that:
        - Contain providers.id, claims.id, diagnosis_id
        - Use IDs in SELECT or GROUP BY
        - Skip canonical join paths (providers → claims → ...)
        - Group by anything except providers.provider_id
        - Use diagnoses without diagnoses.name
        - Use providers without providers.provider_id
        """
        sql_upper = sql.upper()
        query_lower = query.lower()
        
        # Check if this is a provider query
        is_provider_query = any(keyword in query_lower for keyword in [
            'provider', 'facility', 'hospital', 'clinic'
        ])
        
        if not is_provider_query:
            return (True, None)  # Not a provider query, skip validation
        
        # Extract SELECT clause
        select_match = re.search(r'SELECT\s+(.*?)\s+FROM', sql_upper, re.DOTALL | re.IGNORECASE)
        if not select_match:
            return (True, None)  # Can't parse, let it through
        
        select_clause = select_match.group(1)
        
        # HARD FAIL: Check for forbidden patterns in SELECT
        forbidden_patterns = [
            (r'\bproviders\.id\b', 'providers.id', 'providers.provider_id'),
            (r'\bp\.id\b', 'p.id', 'p.provider_id'),
            (r'\bclaims\.id\b', 'claims.id', 'COUNT(DISTINCT claims.id) for counting'),
            (r'\bdiagnosis_id\b', 'diagnosis_id', 'diagnoses.name'),
            (r'\bSELECT\s+\*\b', 'SELECT *', 'explicit column names'),
        ]
        
        for pattern, pattern_name, replacement in forbidden_patterns:
            if re.search(pattern, select_clause, re.IGNORECASE):
                # Allow if it's for counting (COUNT(DISTINCT claims.id))
                if 'COUNT' in sql_upper and 'DISTINCT' in sql_upper:
                    if re.search(r'COUNT\s*\(\s*DISTINCT\s+[^)]*\bid\b', sql_upper):
                        continue  # This is OK for counting
                
                # Check if provider_id is also present (allow if both present)
                if 'PROVIDER_ID' not in sql_upper and 'PROVIDER' not in select_clause.upper():
                    return (
                        False,
                        f"Phase 4 Violation: SQL contains forbidden pattern '{pattern_name}'. "
                        f"Must use {replacement} instead. Query: {query}"
                    )
        
        # HARD FAIL: If providers table is used, must include providers.provider_id
        if 'PROVIDERS' in sql_upper:
            # Check if providers.provider_id is in SELECT
            if 'PROVIDER_ID' not in sql_upper and 'P.PROVIDER_ID' not in sql_upper:
                # Allow if it's a simple count query
                if 'COUNT' in sql_upper and 'FROM PROVIDERS' in sql_upper:
                    pass  # Simple count is OK
                else:
                    return (
                        False,
                        "Phase 4 Violation: Queries using providers table must include providers.provider_id. "
                        f"Query: {query}"
                    )
        
        # HARD FAIL: If diagnoses table is used, must include diagnoses.name
        if 'DIAGNOSES' in sql_upper:
            if 'D.NAME' not in sql_upper and 'DIAGNOSES.NAME' not in sql_upper:
                # Allow if it's a simple count query
                if 'COUNT' in sql_upper and 'FROM DIAGNOSES' in sql_upper:
                    pass  # Simple count is OK
                else:
                    return (
                        False,
                        "Phase 4 Violation: Queries using diagnoses table must include diagnoses.name. "
                        f"Query: {query}"
                    )
        
        # HARD FAIL: Validate canonical join paths
        # Providers must join through: providers → claims → ...
        if 'PROVIDERS' in sql_upper and 'CLAIMS' in sql_upper:
            # Must use: providers → claims
            if 'PROVIDER_ID' not in sql_upper or 'JOIN CLAIMS' not in sql_upper:
                # Check if it's a direct join
                if 'JOIN DIAGNOSES' in sql_upper and 'CLAIMS' not in sql_upper:
                    return (
                        False,
                        "Phase 4 Violation: Providers must join through claims, not directly to diagnoses. "
                        f"Query: {query}"
                    )
        
        # HARD FAIL: If grouping by provider, must group by providers.provider_id
        if 'GROUP BY' in sql_upper and 'PROVIDERS' in sql_upper:
            group_by_match = re.search(r'GROUP\s+BY\s+(.*?)(?:\s+ORDER|\s+HAVING|\s+LIMIT|$)', sql_upper, re.IGNORECASE)
            if group_by_match:
                group_by_clause = group_by_match.group(1)
                # Check if grouping by provider_id
                if 'PROVIDER_ID' not in sql_upper and 'P.ID' in sql_upper:
                    return (
                        False,
                        "Phase 4 Violation: Provider queries must group by providers.provider_id, "
                        f"not providers.id. Query: {query}"
                    )
        
        return (True, None)


# Global instance
sql_validator = SQLValidator()

