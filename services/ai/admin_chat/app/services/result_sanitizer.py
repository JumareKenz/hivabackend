"""
Phase 4: Result Sanitizer
Mandatory post-processing to hide IDs, foreign keys, and rename columns
"""

from typing import List, Dict, Any, Optional


class ResultSanitizer:
    """
    Sanitizes SQL query results to ensure human-readable output.
    
    Always:
    - Hides numeric IDs
    - Hides foreign keys
    - Renames columns to business labels
    """
    
    # Columns to hide (IDs and foreign keys)
    HIDDEN_COLUMNS = [
        'id', 'diagnosis_id', 'service_summary_id', 'claim_id',
        'user_id', 'state_id', 'diagnosis_code',
        'service_id', 'services_id', 'claims_id'
        # Note: provider_id is NOT hidden (it's a business label, not a foreign key)
    ]
    
    # Column rename mappings (to business labels)
    COLUMN_RENAMES = {
        # Domain 1: Clinical Claims & Diagnosis
        'diagnosis': 'Diagnosis',
        'disease_name': 'Diagnosis',
        'total_claims': 'Total Claims',
        'claim_count': 'Claim Count',
        'avg_claim_cost': 'Average Claim Cost',
        'total_cost': 'Total Cost',
        'usage_count': 'Usage Count',
        'service': 'Service',
        'service_description': 'Service',
        'month': 'Month',
        'year': 'Year',
        # Domain 2: Providers & Facilities Performance
        'provider': 'Provider',
        'provider_id': 'Provider ID',  # Business label, not hidden
        'facility': 'Facility',
        'hospital': 'Hospital',
    }
    
    def sanitize(self, results: List[Dict[str, Any]], sql: str) -> List[Dict[str, Any]]:
        """
        Sanitize query results to hide IDs and rename columns.
        
        Args:
            results: Raw SQL query results
            sql: Original SQL query (for context)
            
        Returns:
            Sanitized results with IDs hidden and columns renamed
        """
        if not results:
            return results
        
        # Get column names from first row
        if not results:
            return results
        
        first_row = results[0]
        columns = list(first_row.keys())
        
        # Build sanitized results
        sanitized = []
        for row in results:
            sanitized_row = {}
            for col, value in row.items():
                # Skip hidden columns
                if self._should_hide_column(col):
                    continue
                
                # Rename column to business label
                new_col_name = self._rename_column(col)
                sanitized_row[new_col_name] = value
            
            sanitized.append(sanitized_row)
        
        return sanitized
    
    def _should_hide_column(self, column_name: str) -> bool:
        """
        Check if column should be hidden.
        
        Hides:
        - Columns ending in _id
        - Columns named 'id'
        - diagnosis_code
        """
        col_lower = column_name.lower()
        
        # Check exact matches
        if col_lower in self.HIDDEN_COLUMNS:
            return True
        
        # Check patterns
        if col_lower.endswith('_id'):
            return True
        
        if col_lower == 'id':
            return True
        
        if 'diagnosis_code' in col_lower:
            return True
        
        return False
    
    def _rename_column(self, column_name: str) -> str:
        """
        Rename column to business label.
        
        Examples:
        - diagnosis -> Diagnosis
        - total_claims -> Total Claims
        - avg_claim_cost -> Average Claim Cost
        """
        col_lower = column_name.lower()
        
        # Check exact matches first
        if column_name in self.COLUMN_RENAMES:
            return self.COLUMN_RENAMES[column_name]
        
        # Check lowercase matches
        if col_lower in self.COLUMN_RENAMES:
            return self.COLUMN_RENAMES[col_lower]
        
        # Default: capitalize and replace underscores
        return column_name.replace('_', ' ').title()


# Global instance
result_sanitizer = ResultSanitizer()

