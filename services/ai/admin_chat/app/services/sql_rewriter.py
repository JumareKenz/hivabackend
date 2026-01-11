"""
Phase 4: SQL Rewriter
Soft correction rules that auto-fix safe errors
"""

import re
from typing import Tuple, Optional


class SQLRewriter:
    """
    Rewrites SQL queries to fix safe errors.
    
    Rewrites:
    - GROUP BY diagnoses.id → GROUP BY diagnoses.name
    - Missing DISTINCT claims.id in counts
    - Ordering by alias not in SELECT
    """
    
    def rewrite(self, sql: str, query: str) -> Tuple[str, bool, Optional[str]]:
        """
        Rewrite SQL query to fix safe errors.
        
        Args:
            sql: Original SQL query
            query: Original natural language query
            
        Returns:
            Tuple of (rewritten_sql, was_rewritten, error_message)
            - rewritten_sql: SQL after rewriting (or original if no changes)
            - was_rewritten: True if SQL was modified
            - error_message: Error if rewrite is not safe
        """
        if not sql:
            return (sql, False, "No SQL query provided")
        original_sql = sql
        sql_upper = sql.upper()
        rewritten = False
        query_lower = query.lower()

        # Helper: detect if query explicitly mentions a state
        state_keywords = [
            'zamfara', 'kano', 'kogi', 'kaduna', 'fct', 'abuja', 'adamawa',
            'sokoto', 'rivers', 'osun', 'lagos', 'state', 'states'
        ]
        is_state_query = any(state in query_lower for state in state_keywords)

        # REWRITE 0: Fix duplicate DISTINCT (e.g., COUNT(DISTINCT DISTINCT c.id))
        new_sql = re.sub(
            r'COUNT\s*\(\s*DISTINCT\s+DISTINCT\s+',
            'COUNT(DISTINCT ',
            sql,
            flags=re.IGNORECASE
        )
        if new_sql != sql:
            sql = new_sql
            rewritten = True

        # REWRITE 0b: Remove placeholder state filter and joins when no state is mentioned
        if not is_state_query:
            # Drop placeholder WHERE s.name LIKE '%StateName%'
            new_sql = re.sub(r"WHERE\s+s\.name\s+LIKE\s+'%STATENAME%'", '', sql, flags=re.IGNORECASE)
            if new_sql != sql:
                sql = new_sql
                rewritten = True

            # Remove non-state user/state joins safely when no state is requested
            new_sql = re.sub(
                r'\s+JOIN\s+users\s+u\s+ON\s+c\.user_id\s*=\s*u\.id',
                '',
                sql,
                flags=re.IGNORECASE
            )
            new_sql = re.sub(
                r'\s+JOIN\s+states\s+s\s+ON\s+u\.state\s*=\s*s\.id',
                '',
                new_sql,
                flags=re.IGNORECASE
            )
            if new_sql != sql:
                sql = new_sql
                rewritten = True

        
        # REWRITE 1: GROUP BY diagnoses.id → GROUP BY diagnoses.name
        if 'GROUP BY' in sql_upper and 'DIAGNOSES' in sql_upper:
            # Pattern: GROUP BY d.id or GROUP BY diagnoses.id
            pattern1 = re.compile(
                r'GROUP\s+BY\s+([^,\s]+)\.id',
                re.IGNORECASE
            )
            
            def replace_group_by_id(match):
                alias = match.group(1)
                # Check if this is the diagnoses table alias
                # Look for JOIN diagnoses d or JOIN diagnoses AS d
                diagnoses_alias_pattern = re.compile(
                    rf'JOIN\s+diagnoses\s+(?:AS\s+)?{re.escape(alias)}\b',
                    re.IGNORECASE
                )
                if diagnoses_alias_pattern.search(sql):
                    return f'GROUP BY {alias}.name'
                return match.group(0)  # Don't change if not diagnoses table
            
            new_sql = pattern1.sub(replace_group_by_id, sql)
            if new_sql != sql:
                sql = new_sql
                rewritten = True
        
        # REWRITE 1b: GROUP BY providers.id → GROUP BY providers.provider_id
        if 'GROUP BY' in sql_upper and 'PROVIDERS' in sql_upper:
            # Pattern: GROUP BY p.id or GROUP BY providers.id
            pattern1b = re.compile(
                r'GROUP\s+BY\s+([^,\s]+)\.id',
                re.IGNORECASE
            )
            
            def replace_provider_group_by_id(match):
                alias = match.group(1)
                # Check if this is the providers table alias
                providers_alias_pattern = re.compile(
                    rf'JOIN\s+providers\s+(?:AS\s+)?{re.escape(alias)}\b',
                    re.IGNORECASE
                )
                if providers_alias_pattern.search(sql):
                    return f'GROUP BY {alias}.provider_id'
                return match.group(0)  # Don't change if not providers table
            
            new_sql = pattern1b.sub(replace_provider_group_by_id, sql)
            if new_sql != sql:
                sql = new_sql
                rewritten = True
        
        # REWRITE 2: Missing DISTINCT claims.id in counts
        if 'COUNT' in sql_upper and 'CLAIMS' in sql_upper:
            # Pattern: COUNT(c.id) without DISTINCT in frequency queries
            query_lower = query.lower()
            is_frequency_query = any(keyword in query_lower for keyword in [
                'most common', 'top', 'highest', 'count', 'number of'
            ])
            
            if is_frequency_query:
                # Check if COUNT(c.id) exists without DISTINCT
                pattern = re.compile(
                    r'COUNT\s*\(\s*([^)]+\.id)\s*\)',
                    re.IGNORECASE
                )
                
                def add_distinct(match):
                    col = match.group(1)
                    # Only add DISTINCT if it's claims.id
                    if 'c.id' in match.group(0).lower() or 'claims.id' in match.group(0).lower():
                        return f'COUNT(DISTINCT {col})'
                    return match.group(0)
                
                new_sql = pattern.sub(add_distinct, sql)
                if new_sql != sql:
                    sql = new_sql
                    rewritten = True
        
        # REWRITE 3: Ordering by alias not in SELECT (add alias to SELECT)
        if 'ORDER BY' in sql_upper:
            order_by_match = re.search(
                r'ORDER\s+BY\s+([^\s]+)',
                sql_upper,
                re.IGNORECASE
            )
            if order_by_match:
                order_by_col = order_by_match.group(1).lower()
                # Check if it's an alias (not a column reference)
                if '.' not in order_by_col:
                    # Check if this alias is in SELECT
                    select_match = re.search(
                        r'SELECT\s+(.*?)\s+FROM',
                        sql,
                        re.IGNORECASE | re.DOTALL
                    )
                    if select_match:
                        select_clause = select_match.group(1)
                        # Check if alias is in SELECT
                        if order_by_col not in select_clause.lower():
                            # Try to add it (this is complex, so we'll skip for now)
                            # Just log that it might be an issue
                            pass
        
        # Validate that rewrite is safe
        if rewritten:
            # Check that rewritten SQL is still valid
            if not sql.strip():
                return (original_sql, False, "Rewrite resulted in empty SQL")
            
            # Basic validation: must still have SELECT
            if 'SELECT' not in sql_upper:
                return (original_sql, False, "Rewrite removed SELECT clause")

        # Final cleanup: ensure no stray duplicate DISTINCT remains
        final_sql = re.sub(r'DISTINCT\s+DISTINCT', 'DISTINCT', sql, flags=re.IGNORECASE)
        if final_sql != sql:
            sql = final_sql
            rewritten = True
        
        return (sql, rewritten, None)


# Global instance
sql_rewriter = SQLRewriter()

