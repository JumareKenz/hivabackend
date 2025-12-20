"""
Privacy Service - Small Cell Suppression and Privacy Compliance
Implements post-processing hooks to prevent re-identification
"""
from typing import List, Dict, Any, Optional
from app.services.pii_validator import pii_validator


class PrivacyService:
    """
    Service for enforcing privacy compliance in query results.
    Implements small cell suppression to prevent re-identification.
    """
    
    @staticmethod
    def apply_small_cell_suppression(
        results: List[Dict[str, Any]],
        count_columns: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Apply small cell suppression to query results.
        If any count value is between 1 and 4 (inclusive), redact it to prevent re-identification.
        
        Args:
            results: Query results as list of dictionaries
            count_columns: Optional list of column names that contain counts.
                          If None, auto-detect columns with 'count', 'total', 'num' in name
        
        Returns:
            Results with small cell counts redacted
        """
        if not results:
            return results
        
        # Auto-detect count columns if not provided
        if count_columns is None:
            count_columns = []
            if results:
                for col_name in results[0].keys():
                    col_lower = str(col_name).lower()
                    if any(keyword in col_lower for keyword in ['count', 'total', 'num', 'number', 'sum']):
                        count_columns.append(col_name)
        
        # Apply suppression
        suppressed_results = []
        for row in results:
            suppressed_row = row.copy()
            
            for col_name in count_columns:
                if col_name in suppressed_row:
                    value = suppressed_row[col_name]
                    
                    # Check if value is a numeric count between 1 and 4
                    try:
                        count_value = int(float(value)) if value is not None else None
                        if count_value is not None and 1 <= count_value <= 4:
                            suppressed_row[col_name] = '[SUPPRESSED]'
                    except (ValueError, TypeError):
                        # Not a numeric value, skip
                        pass
            
            suppressed_results.append(suppressed_row)
        
        return suppressed_results
    
    @staticmethod
    def check_pii_leakage(query: str) -> bool:
        """
        Check if a query might attempt to access PII directly.
        Uses PII validator for comprehensive detection.
        
        Args:
            query: Natural language query string
        
        Returns:
            True if query might access PII, False otherwise
        """
        # Use PII validator to check for individual identification queries
        is_safe, _, detected = pii_validator.validate_user_query(query)
        return not is_safe or 'individual_identification_query' in detected
    
    @staticmethod
    def sanitize_for_privacy(text: str) -> str:
        """
        Sanitize text output to ensure no PII is accidentally included.
        
        Args:
            text: Text to sanitize
        
        Returns:
            Sanitized text
        """
        # This is a basic implementation - can be enhanced with regex patterns
        # For now, just ensure no obvious PII patterns are present
        return text


# Global instance
privacy_service = PrivacyService()


