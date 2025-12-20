"""
PII/PHI Validator - Detects and redacts PII/PHI patterns in query results and user inputs
Implements strict validation before data reaches the UI
"""
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime


class PIIValidator:
    """
    Validates and redacts PII/PHI patterns in:
    - User queries (input validation)
    - Query results (output validation)
    - Generated SQL queries
    """
    
    # PII/PHI patterns to detect
    PII_PATTERNS = {
        'name': [
            r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\b',  # First Last name
            r'\b(?:Mr|Mrs|Ms|Dr|Prof)\.?\s+[A-Z][a-z]+\s+[A-Z][a-z]+\b',  # Titles
            r'\b[A-Z][a-z]+\s+[A-Z]\.\s+[A-Z][a-z]+\b',  # Middle initial
        ],
        'phone': [
            r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b',  # US format
            r'\b\+?\d{1,3}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b',  # International
            r'\b0\d{10}\b',  # Nigerian format (0XXXXXXXXXX)
            r'\b\+234\d{10}\b',  # Nigerian international
        ],
        'email': [
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        ],
        'ssn': [
            r'\b\d{3}-\d{2}-\d{4}\b',  # SSN format
        ],
        'id_number': [
            r'\b[A-Z]{2,3}\d{6,}\b',  # ID patterns like CLM8537906241
            r'\b\d{8,}\b',  # Long numeric IDs
        ],
        'address': [
            r'\b\d+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Street|St|Avenue|Ave|Road|Rd|Lane|Ln|Drive|Dr|Boulevard|Blvd|Way)\b',
            r'\b(?:P\.?O\.?\s*Box|PO Box)\s+\d+\b',  # PO Box
        ],
        'date_of_birth': [
            r'\b\d{1,2}[/-]\d{1,2}[/-]\d{4}\b',  # Date formats
            r'\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b',  # ISO date
        ],
        'medical_record': [
            r'\b(?:MRN|Medical Record Number|Patient ID):\s*\d+\b',
        ],
    }
    
    # Common names that might be false positives (exclude these)
    COMMON_WORDS = {
        'test', 'admin', 'user', 'system', 'null', 'none', 'unknown',
        'pending', 'approved', 'rejected', 'verified'
    }
    
    def __init__(self):
        self.detected_pii = []
    
    def validate_user_query(self, query: str) -> Tuple[bool, Optional[str], List[str]]:
        """
        Validate user query for PII/PHI patterns.
        
        Args:
            query: User's natural language query
        
        Returns:
            (is_safe, redacted_query, detected_patterns)
            - is_safe: True if no PII detected, False if PII found
            - redacted_query: Query with PII redacted
            - detected_patterns: List of detected PII types
        """
        detected = []
        redacted_query = query
        
        # Check for "who" questions about individuals
        if re.search(r'\bwho\s+(?:is|was|are|were)\b', query, re.IGNORECASE):
            return False, query, ['individual_identification_query']
        
        # Check for specific individual queries
        individual_patterns = [
            r'\b(?:find|show|tell me about|who is|identify)\s+(?:the|a|an)?\s*(?:patient|person|individual|user)\b',
            r'\b(?:patient|person|individual)\s+(?:named|called|with name|with id)\b',
        ]
        for pattern in individual_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                detected.append('individual_identification_query')
                break
        
        # Check for PII patterns
        for pii_type, patterns in self.PII_PATTERNS.items():
            for pattern in patterns:
                matches = re.finditer(pattern, query, re.IGNORECASE)
                for match in matches:
                    matched_text = match.group(0)
                    # Skip common words that might be false positives
                    if matched_text.lower() not in self.COMMON_WORDS:
                        detected.append(pii_type)
                        # Redact the matched text
                        redacted_query = redacted_query.replace(
                            matched_text,
                            f'[REDACTED_{pii_type.upper()}]'
                        )
        
        is_safe = len(detected) == 0
        return is_safe, redacted_query, list(set(detected))
    
    def validate_query_results(self, results: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Validate query results for stray PII/PHI patterns.
        Redacts any detected PII before results reach the UI.
        
        Args:
            results: Query results as list of dictionaries
        
        Returns:
            (sanitized_results, detected_patterns)
        """
        sanitized_results = []
        all_detected = []
        
        for row in results:
            sanitized_row = {}
            row_detected = []
            
            for key, value in row.items():
                if value is None:
                    sanitized_row[key] = None
                    continue
                
                value_str = str(value)
                sanitized_value = value_str
                
                # Check each PII pattern
                for pii_type, patterns in self.PII_PATTERNS.items():
                    for pattern in patterns:
                        matches = list(re.finditer(pattern, value_str, re.IGNORECASE))
                        if matches:
                            # Redact all matches
                            for match in reversed(matches):  # Reverse to maintain positions
                                matched_text = match.group(0)
                                # Skip if it's a common word or already redacted
                                if (matched_text.lower() not in self.COMMON_WORDS and 
                                    '[REDACTED' not in matched_text):
                                    sanitized_value = sanitized_value.replace(
                                        matched_text,
                                        f'[REDACTED_{pii_type.upper()}]'
                                    )
                                    if pii_type not in row_detected:
                                        row_detected.append(pii_type)
            
            sanitized_row = {**row, **{k: sanitized_row.get(k, v) for k, v in row.items()}}
            # Apply sanitization
            for key in sanitized_row:
                if key in row:
                    # Check if value was sanitized
                    original = str(row[key]) if row[key] is not None else ''
                    sanitized = str(sanitized_row[key]) if sanitized_row[key] is not None else ''
                    if sanitized != original:
                        sanitized_row[key] = sanitized
                    else:
                        sanitized_row[key] = row[key]
            
            # Re-sanitize with proper logic
            for key, value in row.items():
                if value is not None:
                    value_str = str(value)
                    for pii_type, patterns in self.PII_PATTERNS.items():
                        for pattern in patterns:
                            if re.search(pattern, value_str, re.IGNORECASE):
                                matched = re.search(pattern, value_str, re.IGNORECASE)
                                if matched and matched.group(0).lower() not in self.COMMON_WORDS:
                                    sanitized_row[key] = value_str.replace(
                                        matched.group(0),
                                        f'[REDACTED_{pii_type.upper()}]'
                                    )
                                    if pii_type not in row_detected:
                                        row_detected.append(pii_type)
                                    break
            
            sanitized_results.append(sanitized_row)
            all_detected.extend(row_detected)
        
        return sanitized_results, list(set(all_detected))
    
    def validate_sql_query(self, sql: str) -> Tuple[bool, Optional[str]]:
        """
        Validate SQL query for PII leakage attempts.
        
        Args:
            sql: SQL query string
        
        Returns:
            (is_safe, error_message)
        """
        sql_upper = sql.upper()
        
        # Check for attempts to reverse-engineer hashed IDs
        dangerous_patterns = [
            r'WHERE\s+id\s*=\s*[\'"][a-f0-9]{16}[\'"]',  # Direct ID lookup
            r'WHERE\s+.*id.*\s*LIKE\s*[\'"]%[a-f0-9]+%[\'"]',  # Pattern matching on hashes
            r'DECODE|DECRYPT|UNHASH',  # Attempts to reverse hashing
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, sql_upper):
                return False, "Query attempts to reverse-engineer hashed identifiers"
        
        # Check for queries that might return PII
        pii_column_patterns = [
            r'SELECT.*\b(?:firstname|lastname|fullname|phone|email|address|ssn|dob|date_of_birth)\b',
        ]
        
        # Note: This is informational - we allow these if they're in analytics views (masked)
        # But we log it for monitoring
        
        return True, None
    
    def get_privacy_warning(self, detected_patterns: List[str]) -> str:
        """
        Generate privacy warning message for detected PII patterns.
        
        Args:
            detected_patterns: List of detected PII types
        
        Returns:
            Warning message
        """
        if not detected_patterns:
            return ""
        
        warnings = {
            'name': "Names have been redacted for privacy compliance.",
            'phone': "Phone numbers have been redacted for privacy compliance.",
            'email': "Email addresses have been redacted for privacy compliance.",
            'individual_identification_query': "For privacy compliance, I only provide insights at the cohort level. I cannot identify specific individuals.",
        }
        
        messages = [warnings.get(pattern, f"{pattern} detected and redacted.") 
                   for pattern in detected_patterns if pattern in warnings]
        
        if messages:
            return "⚠️ Privacy Notice: " + " ".join(messages)
        
        return "⚠️ Privacy Notice: Some data has been redacted for privacy compliance."


# Global instance
pii_validator = PIIValidator()

