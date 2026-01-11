"""
Phase 4: Domain Router (Schema-Aware)
Routes questions to appropriate domains using schema mapping for intelligent routing
"""

from typing import Dict, Optional, Tuple
from app.services.schema_mapper import schema_mapper


class DomainRouter:
    """
    Schema-aware domain router that maps questions to domains based on:
    1. Database schema (tables and their domains)
    2. Natural language keywords
    3. Query context
    
    This ensures valid healthcare queries are never falsely rejected.
    """
    
    # Healthcare domain keywords (expanded and more permissive)
    HEALTHCARE_KEYWORDS = {
        # Claims & Diagnosis
        'claims': ['claim', 'claims', 'clinical claim', 'medical claim'],
        'diagnosis': ['diagnosis', 'diagnoses', 'disease', 'diseases', 'illness', 'condition', 'conditions', 'malaria', 'typhoid'],
        'services': ['service', 'services', 'treatment', 'treatments', 'procedure', 'procedures'],
        'cost': ['cost', 'costs', 'price', 'prices', 'expense', 'expenses', 'financial', 'revenue', 'amount', 'total cost'],
        
        # Providers & Facilities
        'provider': ['provider', 'providers', 'facility', 'facilities', 'hospital', 'hospitals', 'clinic', 'clinics'],
        'performance': ['performance', 'activity', 'operational', 'utilization', 'volume', 'capacity'],
        
        # Geography
        'geography': ['state', 'states', 'lga', 'lgas', 'zone', 'zones', 'location', 'region', 'kogi', 'zamfara', 
                     'kano', 'kaduna', 'fct', 'abuja', 'adamawa', 'sokoto', 'rivers', 'osun', 'lagos'],
        
        # Time
        'time': ['month', 'months', 'year', 'years', 'quarter', 'quarterly', 'monthly', 'yearly', 'trend', 'trends', 
                'over time', 'this month', 'this year', 'last month', 'last year'],
        
        # Analytics
        'analytics': ['count', 'total', 'number', 'how many', 'show', 'list', 'top', 'bottom', 'highest', 'lowest', 
                     'most', 'least', 'breakdown', 'break down', 'by', 'grouped by']
    }
    
    # Out-of-scope keywords (explicitly excluded - HR, payroll, credentials)
    OUT_OF_SCOPE_KEYWORDS = [
        'password', 'passwords', 'credential', 'credentials', 'login', 'logins',
        'payroll', 'salary', 'salaries', 'wage', 'wages', 'employee', 'employees',
        'hr', 'human resources', 'telescope', 'admin user', 'user account', 'user accounts',
        'permission', 'permissions', 'role assignment', 'wallet balance', 'rating', 'ratings'
    ]
    
    def __init__(self):
        self._initialized = False
    
    async def initialize(self):
        """Initialize schema mapper for intelligent routing"""
        if not self._initialized:
            await schema_mapper.initialize()
            self._initialized = True
    
    def route(self, question: str) -> Tuple[str, Optional[str]]:
        """
        Route a question to the appropriate domain using schema-aware logic.
        
        Args:
            question: Natural language question
            
        Returns:
            Tuple of (domain, rejection_reason)
            - domain: 'clinical_claims_diagnosis', 'providers_facilities', or 'rejected'
            - rejection_reason: None if routed, error message if rejected
        """
        question_lower = question.lower()
        
        # Check for out-of-scope keywords (HR, payroll, credentials)
        # Only reject if it's clearly NOT about healthcare data
        if any(keyword in question_lower for keyword in self.OUT_OF_SCOPE_KEYWORDS):
            # Allow if it's in a healthcare context (e.g., "provider credentials" in healthcare context)
            if not self._is_healthcare_context(question_lower):
                return (
                    'rejected',
                    "This question is outside the supported analysis scope. "
                    "Supported domains: Clinical Claims & Diagnosis, Providers & Facilities Performance."
                )
        
        # Use schema mapper to detect domain
        domain, detected_tables = schema_mapper.get_domain_for_query(question)
        
        # If schema mapper found a domain, use it
        if domain:
            return (domain, None)
        
        # Fallback to keyword-based routing (more permissive)
        if self._has_healthcare_keywords(question_lower):
            # Determine domain based on keywords
            if self._has_provider_keywords(question_lower):
                return ('providers_facilities', None)
            elif self._has_claims_keywords(question_lower):
                return ('clinical_claims_diagnosis', None)
            else:
                # Default to clinical claims (most common)
                return ('clinical_claims_diagnosis', None)
        
        # Very permissive: if question has analytics keywords, assume it's valid
        if self._has_analytics_keywords(question_lower):
            return ('clinical_claims_diagnosis', None)
        
        # Only reject if truly unclear
        return (
            'rejected',
            "This question requires clarification. "
            "Please specify what healthcare data you'd like to analyze (e.g., claims, diagnoses, providers, facilities)."
        )
    
    def _has_healthcare_keywords(self, question: str) -> bool:
        """Check if question has any healthcare-related keywords"""
        for category, keywords in self.HEALTHCARE_KEYWORDS.items():
            if any(keyword in question for keyword in keywords):
                return True
        return False
    
    def _has_provider_keywords(self, question: str) -> bool:
        """Check if question mentions providers/facilities"""
        provider_keywords = self.HEALTHCARE_KEYWORDS.get('provider', [])
        return any(keyword in question for keyword in provider_keywords)
    
    def _has_claims_keywords(self, question: str) -> bool:
        """Check if question mentions claims/diagnoses"""
        claims_keywords = self.HEALTHCARE_KEYWORDS.get('claims', [])
        diagnosis_keywords = self.HEALTHCARE_KEYWORDS.get('diagnosis', [])
        return any(keyword in question for keyword in claims_keywords + diagnosis_keywords)
    
    def _has_analytics_keywords(self, question: str) -> bool:
        """Check if question has analytics/query keywords"""
        analytics_keywords = self.HEALTHCARE_KEYWORDS.get('analytics', [])
        return any(keyword in question for keyword in analytics_keywords)
    
    def _is_healthcare_context(self, question: str) -> bool:
        """
        Check if question is in healthcare context even if it mentions out-of-scope keywords.
        This prevents false rejections for valid healthcare queries.
        """
        # If it has healthcare keywords, it's in healthcare context
        return self._has_healthcare_keywords(question)


# Global instance
domain_router = DomainRouter()

