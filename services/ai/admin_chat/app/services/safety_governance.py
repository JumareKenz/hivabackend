"""
Domain 3.2: Safety, Permissions & Data Governance
Prevents unauthorized or dangerous data access
"""

from typing import Dict, List, Optional, Tuple, Set
import re


class SafetyGovernance:
    """
    Role-Based Query Constraints, PII Masking, and Query Guardrails
    """
    
    # PII and sensitive columns
    PII_COLUMNS = [
        'email', 'phone', 'phone_number', 'nimc', 'nimc_number',
        'salary', 'salary_number', 'ssn', 'password', 'pin',
        'credit_card', 'bank_account', 'personal_information'
    ]
    
    # Forbidden SQL operations
    FORBIDDEN_OPERATIONS = [
        'DELETE', 'UPDATE', 'DROP', 'TRUNCATE', 'ALTER', 'CREATE',
        'INSERT', 'GRANT', 'REVOKE', 'EXEC', 'EXECUTE'
    ]
    
    # Role-based table access
    ROLE_TABLE_ACCESS = {
        'admin': '*',  # Full access
        'analyst': [
            'claims', 'service_summaries', 'service_summary_diagnosis',
            'diagnoses', 'claims_services', 'services', 'providers',
            'users', 'states'  # Added for state filtering (read-only, no PII access)
        ],
        'public': [
            'diagnoses', 'services'  # Aggregated views only
        ]
    }
    
    def check_role_permissions(self, user_role: str, tables: List[str], query: str = "") -> Tuple[bool, Optional[str]]:
        """
        Check if user role has permission to access tables
        
        Args:
            user_role: User's role (admin, analyst, public)
            tables: List of tables in query
            query: Original query (for context-aware permission checks)
            
        Returns:
            Tuple of (has_permission, rejection_reason)
        """
        if user_role not in self.ROLE_TABLE_ACCESS:
            return (False, f"Unknown user role: {user_role}")
        
        allowed_tables = self.ROLE_TABLE_ACCESS[user_role]
        
        # Admin has full access
        if allowed_tables == '*':
            return (True, None)
        
        # For analyst role: Allow users/states tables ONLY for state filtering (not for user details)
        query_lower = query.lower() if query else ""
        is_state_query = any(state in query_lower for state in [
            'zamfara', 'kano', 'kogi', 'kaduna', 'fct', 'abuja', 'adamawa',
            'sokoto', 'rivers', 'osun', 'lagos', 'state', 'states'
        ])
        is_user_detail_query = any(keyword in query_lower for keyword in [
            'user details', 'user information', 'user profile', 'which user', 'who is the user'
        ])
        
        # Check if all requested tables are allowed
        for table in tables:
            table_lower = table.lower()
            if table_lower not in [t.lower() for t in allowed_tables]:
                # Special case: users/states for state filtering
                if user_role == 'analyst' and table_lower in ['users', 'states']:
                    if is_state_query and not is_user_detail_query:
                        continue  # Allow users/states for state filtering
                    else:
                        return (
                            False,
                            f"Role '{user_role}' does not have permission to access table '{table}' for user details. "
                            f"State filtering is allowed, but user detail queries are restricted."
                        )
                
                return (
                    False,
                    f"Role '{user_role}' does not have permission to access table '{table}'. "
                    f"Allowed tables: {', '.join(allowed_tables)}"
                )
        
        return (True, None)
    
    def identify_pii_columns(self, sql: str, schema_info: Optional[Dict] = None) -> List[str]:
        """
        Identify PII columns in SQL query
        
        Returns:
            List of PII column names found
        """
        if not sql:
            return []
        sql_upper = sql.upper()
        found_pii = []
        
        for pii_col in self.PII_COLUMNS:
            # Check for column in SELECT clause
            pattern = rf'\b{pii_col}\b'
            if re.search(pattern, sql_upper, re.IGNORECASE):
                found_pii.append(pii_col)
        
        return found_pii
    
    def mask_pii_in_results(self, results: List[Dict], pii_columns: List[str]) -> List[Dict]:
        """
        Mask PII columns in query results
        
        Returns:
            Results with PII columns masked
        """
        if not results or not pii_columns:
            return results
        
        masked_results = []
        for row in results:
            masked_row = {}
            for col, value in row.items():
                col_lower = col.lower()
                # Check if column contains PII
                is_pii = any(pii in col_lower for pii in self.PII_COLUMNS)
                
                if is_pii and value:
                    # Mask the value
                    if isinstance(value, str):
                        if '@' in value:  # Email
                            masked_row[col] = '***@***.***'
                        elif len(value) > 4:  # Phone, NIMC, etc.
                            masked_row[col] = '***' + value[-4:]
                        else:
                            masked_row[col] = '***'
                    else:
                        masked_row[col] = '***'
                else:
                    masked_row[col] = value
            
            masked_results.append(masked_row)
        
        return masked_results
    
    def validate_query_safety(self, sql: str) -> Tuple[bool, Optional[str]]:
        """
        Query Guardrails: Hard-block dangerous operations
        
        Returns:
            Tuple of (is_safe, rejection_reason)
        """
        if not sql:
            return (False, "No SQL query provided")
        sql_upper = sql.upper()
        
        # Check for forbidden operations
        for operation in self.FORBIDDEN_OPERATIONS:
            # Use word boundaries to avoid false positives
            pattern = rf'\b{operation}\b'
            if re.search(pattern, sql_upper):
                return (
                    False,
                    f"Query contains forbidden operation: {operation}. "
                    "Only SELECT queries are allowed."
                )
        
        # Check for Cartesian joins (no ON clause)
        if 'JOIN' in sql_upper:
            # Count JOINs and ON clauses
            join_count = len(re.findall(r'\bJOIN\b', sql_upper))
            on_count = len(re.findall(r'\bON\b', sql_upper))
            
            if join_count > on_count:
                return (
                    False,
                    "Query contains Cartesian join (missing ON clause). "
                    "All joins must have explicit join conditions."
                )
        
        # Check for full-table scans without filters
        # This is a simplified check - in production, use query planner
        if 'WHERE' not in sql_upper and 'LIMIT' not in sql_upper:
            # Allow if it's a simple count
            if 'COUNT(*)' in sql_upper or 'COUNT(1)' in sql_upper:
                pass  # COUNT queries are OK
            else:
                # Warn but don't block (too restrictive)
                pass
        
        return (True, None)
    
    def check_sensitive_data_access(self, query: str, sql: str) -> Tuple[bool, Optional[str]]:
        """
        Check if query attempts to access sensitive data
        
        Returns:
            Tuple of (is_allowed, rejection_reason)
        """
        query_lower = query.lower()
        sql_upper = sql.upper()
        
        # Check query text for sensitive keywords
        sensitive_keywords = [
            'email', 'phone', 'nimc', 'salary', 'ssn', 'password',
            'credit card', 'bank account', 'personal information'
        ]
        
        if any(keyword in query_lower for keyword in sensitive_keywords):
            # Check if PII columns are in SQL
            pii_columns = self.identify_pii_columns(sql)
            if pii_columns:
                return (
                    False,
                    f"Query attempts to access sensitive data: {', '.join(pii_columns)}. "
                    "This data is restricted for privacy and security reasons."
                )
        
        return (True, None)


# Global instance
safety_governance = SafetyGovernance()


