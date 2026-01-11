"""
Schema Mapper Service
Maps database tables and columns to domains for intelligent routing
"""
from typing import Dict, List, Set, Optional, Tuple
from app.services.database_service import database_service


class SchemaMapper:
    """
    Maps database schema to domains for intelligent query routing.
    This ensures the domain router understands what tables belong to which domains.
    """
    
    # Domain 1: Clinical Claims & Diagnosis
    DOMAIN1_TABLES = {
        'claims', 'diagnoses', 'health_records', 'services', 
        'claims_services', 'diagnosis_codes', 'icd_codes'
    }
    
    # Domain 2: Providers & Facilities Performance  
    DOMAIN2_TABLES = {
        'providers', 'facilities', 'provider_performance', 
        'facility_metrics', 'provider_activity'
    }
    
    # Supporting tables (used across domains)
    SUPPORTING_TABLES = {
        'users', 'states', 'lgas', 'zones', 'branches'
    }
    
    # Table keywords mapping (for natural language matching)
    TABLE_KEYWORDS = {
        'claims': ['claim', 'claims', 'clinical claim', 'medical claim'],
        'diagnoses': ['diagnosis', 'diagnoses', 'disease', 'diseases', 'illness', 'condition'],
        'providers': ['provider', 'providers', 'facility', 'facilities', 'hospital', 'hospitals', 'clinic', 'clinics'],
        'users': ['user', 'users', 'patient', 'patients', 'beneficiary', 'beneficiaries'],
        'states': ['state', 'states', 'geography', 'geographic', 'location'],
        'services': ['service', 'services', 'treatment', 'treatments', 'procedure', 'procedures'],
    }
    
    def __init__(self):
        self._schema_cache: Optional[Dict] = None
        self._table_to_domain: Dict[str, str] = {}
        self._initialized = False
    
    async def initialize(self):
        """Initialize schema mapping by fetching actual database schema"""
        if self._initialized:
            return
        
        try:
            schema_info = await database_service.get_schema_info()
            if schema_info and 'tables' in schema_info:
                # Build table-to-domain mapping from actual schema
                for table_info in schema_info['tables']:
                    table_name = table_info.get('table_name', '').lower()
                    self._map_table_to_domain(table_name)
            
            self._initialized = True
        except Exception as e:
            print(f"⚠️  Schema mapper initialization error: {e}")
            # Fallback to default mappings
            self._initialize_default_mappings()
    
    def _map_table_to_domain(self, table_name: str):
        """Map a table to its domain based on name and keywords"""
        table_lower = table_name.lower()
        
        # Check Domain 1 tables
        if any(domain_table in table_lower for domain_table in self.DOMAIN1_TABLES):
            self._table_to_domain[table_name] = 'clinical_claims_diagnosis'
            return
        
        # Check Domain 2 tables
        if any(domain_table in table_lower for domain_table in self.DOMAIN2_TABLES):
            self._table_to_domain[table_name] = 'providers_facilities'
            return
        
        # Supporting tables can be used with either domain
        if any(support_table in table_lower for support_table in self.SUPPORTING_TABLES):
            self._table_to_domain[table_name] = 'supporting'  # Can be used with either
            return
        
        # Default: assume it's part of clinical claims if unknown
        self._table_to_domain[table_name] = 'clinical_claims_diagnosis'
    
    def _initialize_default_mappings(self):
        """Initialize default table-to-domain mappings"""
        for table in self.DOMAIN1_TABLES:
            self._table_to_domain[table] = 'clinical_claims_diagnosis'
        
        for table in self.DOMAIN2_TABLES:
            self._table_to_domain[table] = 'providers_facilities'
        
        for table in self.SUPPORTING_TABLES:
            self._table_to_domain[table] = 'supporting'
    
    def get_domain_for_table(self, table_name: str) -> Optional[str]:
        """Get the domain for a specific table"""
        return self._table_to_domain.get(table_name.lower())
    
    def get_tables_for_domain(self, domain: str) -> List[str]:
        """Get all tables that belong to a domain"""
        return [table for table, dom in self._table_to_domain.items() if dom == domain]
    
    def detect_tables_from_query(self, query: str) -> Set[str]:
        """Detect which tables are likely needed for a query based on keywords"""
        query_lower = query.lower()
        detected_tables = set()
        
        # Check each table's keywords
        for table_name, keywords in self.TABLE_KEYWORDS.items():
            if any(keyword in query_lower for keyword in keywords):
                detected_tables.add(table_name)
        
        # Also check for state/geography queries
        state_keywords = ['state', 'states', 'kogi', 'zamfara', 'kano', 'kaduna', 
                         'fct', 'abuja', 'adamawa', 'sokoto', 'rivers', 'osun', 'lagos']
        if any(keyword in query_lower for keyword in state_keywords):
            detected_tables.add('states')
            detected_tables.add('users')  # Users table links to states
        
        return detected_tables
    
    def get_domain_for_query(self, query: str) -> Tuple[Optional[str], Set[str]]:
        """
        Determine the domain for a query based on detected tables.
        
        Returns:
            Tuple of (domain, detected_tables)
        """
        detected_tables = self.detect_tables_from_query(query)
        
        if not detected_tables:
            return None, detected_tables
        
        # Check which domain the tables belong to
        domain1_count = 0
        domain2_count = 0
        
        for table in detected_tables:
            domain = self.get_domain_for_table(table)
            if domain == 'clinical_claims_diagnosis':
                domain1_count += 1
            elif domain == 'providers_facilities':
                domain2_count += 1
        
        # If query mentions providers/facilities, prioritize Domain 2
        query_lower = query.lower()
        has_provider_keywords = any(kw in query_lower for kw in [
            'provider', 'providers', 'facility', 'facilities', 'hospital', 'clinic'
        ])
        
        if has_provider_keywords and domain2_count > 0:
            return 'providers_facilities', detected_tables
        
        # If query mentions claims/diagnoses, prioritize Domain 1
        has_claims_keywords = any(kw in query_lower for kw in [
            'claim', 'claims', 'diagnosis', 'diagnoses', 'disease', 'diseases'
        ])
        
        if has_claims_keywords and domain1_count > 0:
            return 'clinical_claims_diagnosis', detected_tables
        
        # Default based on table counts
        if domain2_count > domain1_count:
            return 'providers_facilities', detected_tables
        elif domain1_count > 0:
            return 'clinical_claims_diagnosis', detected_tables
        
        # If only supporting tables, check query context
        if has_provider_keywords:
            return 'providers_facilities', detected_tables
        elif has_claims_keywords:
            return 'clinical_claims_diagnosis', detected_tables
        
        # Default to clinical claims (most common)
        return 'clinical_claims_diagnosis', detected_tables


# Global instance
schema_mapper = SchemaMapper()
