"""
Analytics View Service - Privacy-by-Design Data Masking Layer
Generates and manages analytics views with PII masking for NLP-to-SQL queries
"""
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime
from app.services.database_service import database_service


class AnalyticsViewService:
    """
    Service for creating and managing privacy-compliant analytics views.
    Implements the "Masked Schema" pattern with:
    - SHA-256 hashing for IDs
    - Age-bucketing for DOBs
    - PII removal (names, phone numbers)
    """
    
    def __init__(self):
        self._view_cache: Optional[Dict[str, Any]] = None
        self._schema_manifest: Optional[Dict[str, Any]] = None
    
    def _hash_id(self, id_value: Any) -> str:
        """Hash an ID using SHA-256"""
        if id_value is None:
            return None
        return hashlib.sha256(str(id_value).encode()).hexdigest()[:16]  # First 16 chars for readability
    
    def _age_bucket(self, dob: Optional[str]) -> Optional[str]:
        """
        Convert date of birth to age bucket for privacy compliance.
        Returns age ranges: '0-17', '18-24', '25-34', '35-44', '45-54', '55-64', '65+'
        """
        if not dob:
            return None
        
        try:
            # Parse date (assuming YYYY-MM-DD format)
            birth_date = datetime.strptime(str(dob)[:10], '%Y-%m-%d')
            today = datetime.now()
            age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
            
            # Age bucketing
            if age < 18:
                return '0-17'
            elif age < 25:
                return '18-24'
            elif age < 35:
                return '25-34'
            elif age < 45:
                return '35-44'
            elif age < 55:
                return '45-54'
            elif age < 65:
                return '55-64'
            else:
                return '65+'
        except (ValueError, TypeError):
            return None
    
    async def generate_analytics_views_ddl(self) -> List[str]:
        """
        Generate DDL statements to create analytics views with PII masking.
        This should be run once to set up the view layer.
        
        Returns:
            List of SQL DDL statements to create views
        """
        if not database_service.pool:
            return []
        
        # Get base schema to understand table structure
        schema_info = await database_service.get_schema_info()
        if not schema_info or 'tables' not in schema_info:
            return []
        
        ddl_statements = []
        db_type = database_service.db_type or "mysql"
        
        # Common PII column patterns
        pii_patterns = {
            'name': ['name', 'firstname', 'lastname', 'fullname', 'client_name', 'patient_name'],
            'phone': ['phone', 'phone_number', 'mobile', 'telephone'],
            'email': ['email', 'email_address'],
            'id': ['id', '_id'],  # Will be hashed
            'dob': ['dob', 'date_of_birth', 'birth_date', 'birthdate']
        }
        
        for table in schema_info.get('tables', []):
            table_name = table.get('table_name', '')
            columns = table.get('columns', [])
            
            if not table_name:
                continue
            
            # Build view columns with masking
            view_columns = []
            column_mappings = {}
            
            for col in columns:
                col_name = col.get('column_name', '')
                col_type = col.get('data_type', '').lower()
                col_lower = col_name.lower()
                
                # Skip if column doesn't exist
                if not col_name:
                    continue
                
                # Hash IDs
                if any(pattern in col_lower for pattern in pii_patterns['id']) and col_lower in ['id', 'user_id', 'provider_id', 'patient_id', 'claim_id']:
                    if db_type == "mysql":
                        view_columns.append(f"SUBSTRING(SHA2(CONCAT('{table_name}_', {col_name}), 256), 1, 16) AS {col_name}")
                    else:  # PostgreSQL
                        view_columns.append(f"SUBSTRING(ENCODE(DIGEST(CONCAT('{table_name}_', {col_name}::text), 'sha256'), 'hex'), 1, 16) AS {col_name}")
                    column_mappings[col_name] = 'hashed_id'
                
                # Mask names
                elif any(pattern in col_lower for pattern in pii_patterns['name']):
                    # Replace with generic placeholder
                    if db_type == "mysql":
                        view_columns.append(f"'[REDACTED]' AS {col_name}")
                    else:
                        view_columns.append(f"'[REDACTED]' AS {col_name}")
                    column_mappings[col_name] = 'redacted'
                
                # Mask phone numbers
                elif any(pattern in col_lower for pattern in pii_patterns['phone']):
                    if db_type == "mysql":
                        view_columns.append(f"CONCAT('***-***-', RIGHT({col_name}, 4)) AS {col_name}")
                    else:
                        view_columns.append(f"'***-***-' || RIGHT({col_name}::text, 4) AS {col_name}")
                    column_mappings[col_name] = 'masked_phone'
                
                # Mask emails
                elif any(pattern in col_lower for pattern in pii_patterns['email']):
                    if db_type == "mysql":
                        view_columns.append(f"CONCAT(LEFT({col_name}, 2), '***@***') AS {col_name}")
                    else:
                        view_columns.append(f"LEFT({col_name}::text, 2) || '***@***' AS {col_name}")
                    column_mappings[col_name] = 'masked_email'
                
                # Age-bucket DOBs
                elif any(pattern in col_lower for pattern in pii_patterns['dob']):
                    # For MySQL, use a CASE statement for age bucketing
                    if db_type == "mysql":
                        view_columns.append(f"""CASE 
                            WHEN TIMESTAMPDIFF(YEAR, {col_name}, CURDATE()) < 18 THEN '0-17'
                            WHEN TIMESTAMPDIFF(YEAR, {col_name}, CURDATE()) < 25 THEN '18-24'
                            WHEN TIMESTAMPDIFF(YEAR, {col_name}, CURDATE()) < 35 THEN '25-34'
                            WHEN TIMESTAMPDIFF(YEAR, {col_name}, CURDATE()) < 45 THEN '35-44'
                            WHEN TIMESTAMPDIFF(YEAR, {col_name}, CURDATE()) < 55 THEN '45-54'
                            WHEN TIMESTAMPDIFF(YEAR, {col_name}, CURDATE()) < 65 THEN '55-64'
                            ELSE '65+'
                        END AS {col_name}""")
                    else:  # PostgreSQL
                        view_columns.append(f"""CASE 
                            WHEN EXTRACT(YEAR FROM AGE({col_name})) < 18 THEN '0-17'
                            WHEN EXTRACT(YEAR FROM AGE({col_name})) < 25 THEN '18-24'
                            WHEN EXTRACT(YEAR FROM AGE({col_name})) < 35 THEN '25-34'
                            WHEN EXTRACT(YEAR FROM AGE({col_name})) < 45 THEN '35-44'
                            WHEN EXTRACT(YEAR FROM AGE({col_name})) < 55 THEN '45-54'
                            WHEN EXTRACT(YEAR FROM AGE({col_name})) < 65 THEN '55-64'
                            ELSE '65+'
                        END AS {col_name}""")
                    column_mappings[col_name] = 'age_bucket'
                
                # Keep non-PII columns as-is
                else:
                    view_columns.append(col_name)
                    column_mappings[col_name] = 'original'
            
            if not view_columns:
                continue
            
            # Generate CREATE VIEW statement
            view_name = f"analytics_view_{table_name}"
            columns_sql = ",\n    ".join(view_columns)
            
            if db_type == "mysql":
                ddl = f"""CREATE OR REPLACE VIEW {view_name} AS
SELECT
    {columns_sql}
FROM {table_name};"""
            else:  # PostgreSQL
                ddl = f"""CREATE OR REPLACE VIEW {view_name} AS
SELECT
    {columns_sql}
FROM {table_name};"""
            
            ddl_statements.append(ddl)
        
        return ddl_statements
    
    async def get_semantic_manifest(self) -> Dict[str, Any]:
        """
        Generate a semantic manifest describing what each column represents.
        This provides context to the LLM for better SQL generation.
        
        Returns:
            Dictionary mapping table names to column descriptions
        """
        if self._schema_manifest:
            return self._schema_manifest
        
        schema_info = await database_service.get_schema_info()
        if not schema_info or 'tables' not in schema_info:
            return {}
        
        manifest = {}
        
        # Semantic descriptions for common columns
        semantic_descriptions = {
            'claims': {
                'id': 'Unique claim identifier (hashed for privacy)',
                'claim_unique_id': 'Claim reference number',
                'status': 'Claim status: 0=Pending, 1=Approved, 2=Rejected, 3=Verified',
                'total_cost': 'Total cost of the claim in local currency',
                'created_at': 'Timestamp when claim was created',
                'verified_by_id': 'ID of staff who verified the claim (NULL if not verified)',
                'approved_by_id': 'ID of staff who approved the claim (NULL if not approved)',
                'user_id': 'Reference to user who submitted the claim (hashed)',
                'provider_id': 'Reference to healthcare provider (hashed)',
                'client_name': '[REDACTED - PII]',
            },
            'users': {
                'id': 'Unique user identifier (hashed for privacy)',
                'firstname': '[REDACTED - PII]',
                'lastname': '[REDACTED - PII]',
                'state': 'State ID where user is located',
                'phone': 'Phone number (masked)',
                'email': 'Email address (masked)',
                'created_at': 'User registration timestamp',
            },
            'providers': {
                'id': 'Unique provider identifier (hashed for privacy)',
                'name': 'Provider/facility name',
                'type': 'Provider type (hospital, clinic, etc.)',
                'state': 'State where provider is located',
            },
            'states': {
                'id': 'State identifier',
                'name': 'State name',
            }
        }
        
        for table in schema_info.get('tables', []):
            table_name = table.get('table_name', '')
            columns = table.get('columns', [])
            
            if not table_name:
                continue
            
            manifest[table_name] = {
                'table_description': self._get_table_description(table_name),
                'columns': {}
            }
            
            # Get semantic descriptions for this table
            table_descriptions = semantic_descriptions.get(table_name.lower(), {})
            
            for col in columns:
                col_name = col.get('column_name', '')
                col_type = col.get('data_type', '')
                
                if not col_name:
                    continue
                
                # Use semantic description if available, otherwise generate generic one
                description = table_descriptions.get(col_name.lower(), 
                    f"{col_name} ({col_type}) - {self._infer_column_meaning(col_name, col_type)}")
                
                manifest[table_name]['columns'][col_name] = {
                    'data_type': col_type,
                    'description': description,
                    'is_pii': self._is_pii_column(col_name)
                }
        
        self._schema_manifest = manifest
        return manifest
    
    def _get_table_description(self, table_name: str) -> str:
        """Get human-readable description of what a table represents"""
        descriptions = {
            'claims': 'Healthcare insurance claims submitted by users and processed by providers',
            'users': 'Registered users/beneficiaries of the health insurance program',
            'providers': 'Healthcare facilities and providers that submit claims',
            'states': 'Geographic states/regions in the system',
            'transactions': 'Financial transactions related to claims and payments',
            'appointments': 'Medical appointments scheduled by users',
            'health_records': 'Health records and medical history',
            'services': 'Healthcare services available in the system',
            'paymentorders': 'Payment orders and billing information',
        }
        return descriptions.get(table_name.lower(), f"Table containing {table_name} data")
    
    def _infer_column_meaning(self, col_name: str, col_type: str) -> str:
        """Infer the meaning of a column from its name"""
        col_lower = col_name.lower()
        
        if 'id' in col_lower:
            return 'Identifier field'
        elif 'name' in col_lower:
            return 'Name field (PII - redacted)'
        elif 'date' in col_lower or 'created' in col_lower or 'updated' in col_lower:
            return 'Date/timestamp field'
        elif 'status' in col_lower:
            return 'Status indicator'
        elif 'cost' in col_lower or 'price' in col_lower or 'amount' in col_lower:
            return 'Monetary value'
        elif 'count' in col_lower or 'total' in col_lower:
            return 'Aggregate count or total'
        elif 'phone' in col_lower:
            return 'Phone number (masked)'
        elif 'email' in col_lower:
            return 'Email address (masked)'
        else:
            return 'Data field'
    
    def _is_pii_column(self, col_name: str) -> bool:
        """Check if a column contains PII"""
        pii_keywords = ['name', 'phone', 'email', 'dob', 'birth', 'ssn', 'address', 'id']
        return any(keyword in col_name.lower() for keyword in pii_keywords)
    
    def clear_cache(self):
        """Clear cached schema manifest"""
        self._schema_manifest = None


# Global instance
analytics_view_service = AnalyticsViewService()


