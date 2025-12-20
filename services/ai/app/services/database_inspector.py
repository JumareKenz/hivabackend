"""
Database Inspector - Comprehensive database schema and data analysis
Scans all tables, analyzes schemas, and builds semantic understanding
"""
import asyncio
from typing import Dict, Any, List, Optional, Set
from collections import defaultdict
from app.services.database_service import database_service


class DatabaseInspector:
    """
    Inspects database structure, analyzes schemas, and identifies
    what admins typically need to query.
    """
    
    def __init__(self):
        self._schema_cache: Optional[Dict[str, Any]] = None
        self._table_analysis: Optional[Dict[str, Any]] = None
        self._sample_data: Optional[Dict[str, List[Dict]]] = None
    
    async def inspect_database(self) -> Dict[str, Any]:
        """
        Comprehensive database inspection.
        Scans all tables, analyzes schemas, and samples data.
        
        Returns:
            Complete database analysis including:
            - All tables and their schemas
            - Relationships between tables
            - Sample data from each table
            - Common query patterns
        """
        if not database_service.pool:
            return {}
        
        print("🔍 Starting comprehensive database inspection...")
        
        # Step 1: Get all tables (both base tables and views)
        all_tables = await self._get_all_tables()
        print(f"📊 Found {len(all_tables)} tables/views")
        
        # Step 2: Get detailed schema for each table
        table_schemas = {}
        for table in all_tables:
            table_name = table.get('table_name', '')
            if table_name:
                schema = await self._get_table_schema(table_name)
                table_schemas[table_name] = schema
                print(f"  ✓ Analyzed schema for {table_name}")
        
        # Step 3: Sample data from each table (limited rows for analysis)
        sample_data = {}
        for table_name in table_schemas.keys():
            # Skip system tables and views for sampling
            if not table_name.startswith('analytics_view_') and 'information_schema' not in table_name:
                try:
                    samples = await self._sample_table_data(table_name, limit=5)
                    if samples:
                        sample_data[table_name] = samples
                        print(f"  ✓ Sampled data from {table_name}")
                except Exception as e:
                    print(f"  ⚠️  Could not sample {table_name}: {e}")
        
        # Step 4: Identify relationships
        relationships = await self._identify_relationships(table_schemas)
        
        # Step 5: Identify common query patterns
        query_patterns = self._identify_query_patterns(table_schemas, sample_data)
        
        # Step 6: Build semantic manifest
        semantic_manifest = self._build_semantic_manifest(table_schemas, relationships, sample_data)
        
        self._schema_cache = {
            'tables': all_tables,
            'table_schemas': table_schemas,
            'relationships': relationships,
            'sample_data': sample_data,
            'query_patterns': query_patterns,
            'semantic_manifest': semantic_manifest
        }
        
        print("✅ Database inspection complete!")
        return self._schema_cache
    
    async def _get_all_tables(self) -> List[Dict[str, Any]]:
        """Get all tables and views from the database"""
        try:
            # Get both base tables and views
            schema_info = await database_service.get_schema_info(use_analytics_views=False)
            tables = schema_info.get('tables', [])
            
            # Also get analytics views if they exist
            try:
                analytics_schema = await database_service.get_schema_info(use_analytics_views=True)
                analytics_tables = analytics_schema.get('tables', [])
                # Merge, avoiding duplicates
                existing_names = {t.get('table_name') for t in tables}
                for at in analytics_tables:
                    if at.get('table_name') not in existing_names:
                        tables.append(at)
            except:
                pass
            
            return tables
        except Exception as e:
            print(f"Error getting tables: {e}")
            return []
    
    async def _get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """Get detailed schema for a specific table"""
        try:
            schema_info = await database_service.get_schema_info(table_name=table_name)
            
            # Get additional metadata
            columns = schema_info.get('columns', [])
            
            # Analyze column types and patterns
            column_analysis = {}
            for col in columns:
                col_name = col.get('column_name', '')
                col_type = col.get('data_type', '')
                nullable = col.get('is_nullable', 'YES')
                
                column_analysis[col_name] = {
                    'data_type': col_type,
                    'is_nullable': nullable == 'YES',
                    'is_primary_key': self._is_primary_key(col_name),
                    'is_foreign_key': self._is_foreign_key(col_name),
                    'is_indexed': self._is_indexed(col_name, table_name),
                    'semantic_type': self._infer_semantic_type(col_name, col_type)
                }
            
            return {
                'table_name': table_name,
                'columns': columns,
                'column_analysis': column_analysis,
                'estimated_rows': await self._estimate_row_count(table_name)
            }
        except Exception as e:
            print(f"Error getting schema for {table_name}: {e}")
            return {}
    
    async def _sample_table_data(self, table_name: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Sample data from a table to understand its structure"""
        try:
            # Try analytics view first (preferred for privacy)
            if not table_name.startswith('analytics_view_'):
                try:
                    query = f"SELECT * FROM analytics_view_{table_name} LIMIT {limit}"
                    results = await database_service.execute_query(query)
                    if results:
                        return results
                except:
                    pass
            
            # Fallback to raw table (for inspection only)
            db_type = database_service.db_type or "mysql"
            if db_type == "mysql":
                query = f"SELECT * FROM `{table_name}` LIMIT {limit}"
            else:
                query = f'SELECT * FROM "{table_name}" LIMIT {limit}'
            
            results = await database_service._execute_schema_query(query)
            return results
        except Exception as e:
            return []
    
    async def _estimate_row_count(self, table_name: str) -> Optional[int]:
        """Estimate row count for a table"""
        try:
            # Try analytics view first
            if not table_name.startswith('analytics_view_'):
                try:
                    query = f"SELECT COUNT(*) as count FROM analytics_view_{table_name}"
                    results = await database_service.execute_query(query)
                    if results:
                        return results[0].get('count', 0)
                except:
                    pass
            
            # Fallback to raw table
            db_type = database_service.db_type or "mysql"
            if db_type == "mysql":
                query = f"SELECT COUNT(*) as count FROM `{table_name}`"
            else:
                query = f'SELECT COUNT(*) as count FROM "{table_name}"'
            
            results = await database_service._execute_schema_query(query)
            if results:
                return results[0].get('count', 0)
        except:
            pass
        return None
    
    def _is_primary_key(self, column_name: str) -> bool:
        """Check if column is likely a primary key"""
        return column_name.lower() == 'id' or column_name.lower().endswith('_id') and 'id' in column_name.lower()
    
    def _is_foreign_key(self, column_name: str) -> bool:
        """Check if column is likely a foreign key"""
        fk_patterns = ['_id', 'user_id', 'provider_id', 'state_id', 'claim_id', 'patient_id']
        return any(pattern in column_name.lower() for pattern in fk_patterns) and column_name.lower() != 'id'
    
    def _is_indexed(self, column_name: str, table_name: str) -> bool:
        """Check if column is likely indexed (heuristic)"""
        # Common indexed columns
        indexed_patterns = ['id', 'user_id', 'provider_id', 'created_at', 'updated_at', 'status', 'state']
        return any(pattern in column_name.lower() for pattern in indexed_patterns)
    
    def _infer_semantic_type(self, column_name: str, data_type: str) -> str:
        """Infer semantic meaning of a column"""
        col_lower = column_name.lower()
        
        if 'id' in col_lower:
            if col_lower == 'id':
                return 'primary_key'
            return 'foreign_key'
        elif any(x in col_lower for x in ['name', 'title', 'label']):
            return 'identifier_text'
        elif any(x in col_lower for x in ['email', 'phone', 'mobile', 'telephone']):
            return 'contact_info'
        elif any(x in col_lower for x in ['date', 'time', 'created', 'updated', 'timestamp']):
            return 'temporal'
        elif any(x in col_lower for x in ['cost', 'price', 'amount', 'total', 'fee', 'charge']):
            return 'monetary'
        elif any(x in col_lower for x in ['count', 'number', 'quantity', 'qty']):
            return 'numeric_count'
        elif any(x in col_lower for x in ['status', 'state', 'type', 'category']):
            return 'categorical'
        elif any(x in col_lower for x in ['address', 'location', 'city', 'state', 'region']):
            return 'geographic'
        elif 'description' in col_lower or 'note' in col_lower or 'comment' in col_lower:
            return 'text_content'
        else:
            return 'general'
    
    async def _identify_relationships(self, table_schemas: Dict[str, Dict]) -> Dict[str, List[Dict]]:
        """Identify relationships between tables"""
        relationships = defaultdict(list)
        
        for table_name, schema in table_schemas.items():
            columns = schema.get('column_analysis', {})
            
            for col_name, col_info in columns.items():
                if col_info.get('is_foreign_key'):
                    # Try to identify target table
                    if 'user_id' in col_name.lower():
                        relationships[table_name].append({
                            'column': col_name,
                            'target_table': 'users',
                            'relationship_type': 'many_to_one'
                        })
                    elif 'provider_id' in col_name.lower():
                        relationships[table_name].append({
                            'column': col_name,
                            'target_table': 'providers',
                            'relationship_type': 'many_to_one'
                        })
                    elif 'claim_id' in col_name.lower():
                        relationships[table_name].append({
                            'column': col_name,
                            'target_table': 'claims',
                            'relationship_type': 'many_to_one'
                        })
                    elif 'state' in col_name.lower() or 'state_id' in col_name.lower():
                        relationships[table_name].append({
                            'column': col_name,
                            'target_table': 'states',
                            'relationship_type': 'many_to_one'
                        })
        
        return dict(relationships)
    
    def _identify_query_patterns(self, table_schemas: Dict, sample_data: Dict) -> List[Dict[str, Any]]:
        """Identify common query patterns based on schema and data"""
        patterns = []
        
        # Pattern 1: Claims analysis
        if 'claims' in [t.lower() for t in table_schemas.keys()]:
            patterns.append({
                'pattern': 'claims_by_status',
                'description': 'Count claims grouped by status',
                'example_query': 'Show me claims by status',
                'tables': ['claims'],
                'aggregation': True
            })
            patterns.append({
                'pattern': 'claims_by_date',
                'description': 'Claims filtered by date range',
                'example_query': 'Show me claims for October 2025',
                'tables': ['claims'],
                'aggregation': False
            })
            patterns.append({
                'pattern': 'claims_by_provider',
                'description': 'Claims grouped by provider',
                'example_query': 'Top 10 providers by claim volume',
                'tables': ['claims', 'providers'],
                'aggregation': True
            })
            patterns.append({
                'pattern': 'claims_by_state',
                'description': 'Claims grouped by state/region',
                'example_query': 'Show me claims by state',
                'tables': ['claims', 'users', 'states'],
                'aggregation': True
            })
        
        # Pattern 2: User/Patient analysis
        if 'users' in [t.lower() for t in table_schemas.keys()]:
            patterns.append({
                'pattern': 'users_by_state',
                'description': 'User distribution by state',
                'example_query': 'How many users are in each state?',
                'tables': ['users', 'states'],
                'aggregation': True
            })
        
        # Pattern 3: Provider analysis
        if 'providers' in [t.lower() for t in table_schemas.keys()]:
            patterns.append({
                'pattern': 'provider_performance',
                'description': 'Provider performance metrics',
                'example_query': 'Show me provider performance this month',
                'tables': ['providers', 'claims'],
                'aggregation': True
            })
        
        # Pattern 4: Financial analysis
        financial_tables = ['transactions', 'paymentorders', 'claims']
        if any(t in [tbl.lower() for tbl in table_schemas.keys()] for t in financial_tables):
            patterns.append({
                'pattern': 'revenue_analysis',
                'description': 'Revenue and financial metrics',
                'example_query': 'What is the total revenue this month?',
                'tables': financial_tables,
                'aggregation': True
            })
        
        # Pattern 5: Time-series analysis
        patterns.append({
            'pattern': 'time_series',
            'description': 'Trends over time (daily, monthly, yearly)',
            'example_query': 'Show me claim trends over the last 6 months',
            'tables': ['claims'],
            'aggregation': True
        })
        
        # Pattern 6: Comparison queries
        patterns.append({
            'pattern': 'period_comparison',
            'description': 'Compare metrics between time periods',
            'example_query': 'Compare claim volume for November and October 2025',
            'tables': ['claims'],
            'aggregation': True
        })
        
        return patterns
    
    def _build_semantic_manifest(self, table_schemas: Dict, relationships: Dict, sample_data: Dict) -> Dict[str, Any]:
        """Build comprehensive semantic manifest for LLM"""
        manifest = {}
        
        for table_name, schema in table_schemas.items():
            columns = schema.get('column_analysis', {})
            table_rels = relationships.get(table_name, [])
            
            manifest[table_name] = {
                'description': self._generate_table_description(table_name, columns, sample_data.get(table_name, [])),
                'columns': {},
                'relationships': table_rels,
                'common_queries': self._suggest_common_queries(table_name, columns, table_rels)
            }
            
            for col_name, col_info in columns.items():
                semantic_type = col_info.get('semantic_type', 'general')
                manifest[table_name]['columns'][col_name] = {
                    'data_type': col_info.get('data_type'),
                    'semantic_type': semantic_type,
                    'description': self._generate_column_description(col_name, col_info, semantic_type),
                    'is_primary_key': col_info.get('is_primary_key'),
                    'is_foreign_key': col_info.get('is_foreign_key'),
                    'nullable': col_info.get('is_nullable')
                }
        
        return manifest
    
    def _generate_table_description(self, table_name: str, columns: Dict, sample_data: List[Dict]) -> str:
        """Generate human-readable table description"""
        table_lower = table_name.lower().replace('analytics_view_', '')
        
        descriptions = {
            'claims': 'Healthcare insurance claims submitted by users and processed by providers. Contains claim details, status, costs, and processing information.',
            'users': 'Registered users/beneficiaries of the health insurance program. Contains user demographics and registration information.',
            'providers': 'Healthcare facilities and providers that submit claims. Contains provider details, locations, and facility information.',
            'states': 'Geographic states/regions in the system. Reference table for state information.',
            'transactions': 'Financial transactions related to claims and payments. Contains payment records and transaction details.',
            'appointments': 'Medical appointments scheduled by users. Contains appointment details and scheduling information.',
            'health_records': 'Health records and medical history. Contains patient medical information.',
            'services': 'Healthcare services available in the system. Reference table for service types and codes.',
            'paymentorders': 'Payment orders and billing information. Contains billing and payment order details.',
        }
        
        if table_lower in descriptions:
            return descriptions[table_lower]
        
        # Generate based on columns
        if 'claim' in table_lower:
            return f"Table containing {table_lower} data related to healthcare claims"
        elif 'user' in table_lower or 'patient' in table_lower:
            return f"Table containing {table_lower} data related to users or patients"
        elif 'provider' in table_lower or 'facility' in table_lower:
            return f"Table containing {table_lower} data related to healthcare providers"
        else:
            return f"Table containing {table_lower} data"
    
    def _generate_column_description(self, col_name: str, col_info: Dict, semantic_type: str) -> str:
        """Generate human-readable column description"""
        col_lower = col_name.lower()
        
        if semantic_type == 'primary_key':
            return f"Unique identifier for {col_name.replace('_id', '').replace('id', 'record')}"
        elif semantic_type == 'foreign_key':
            target = col_lower.replace('_id', '').replace('id', '')
            return f"Reference to {target} table (foreign key)"
        elif semantic_type == 'temporal':
            if 'created' in col_lower:
                return "Timestamp when record was created"
            elif 'updated' in col_lower:
                return "Timestamp when record was last updated"
            else:
                return "Date or timestamp field"
        elif semantic_type == 'monetary':
            return "Monetary value in local currency"
        elif semantic_type == 'categorical':
            if 'status' in col_lower:
                return "Status indicator (e.g., Pending, Approved, Rejected)"
            else:
                return "Categorical classification"
        elif semantic_type == 'geographic':
            return "Geographic location information"
        else:
            return f"{col_name.replace('_', ' ').title()} field"
    
    def _suggest_common_queries(self, table_name: str, columns: Dict, relationships: List[Dict]) -> List[str]:
        """Suggest common queries for a table"""
        queries = []
        table_lower = table_name.lower().replace('analytics_view_', '')
        
        if 'claims' in table_lower:
            queries.extend([
                "Show me claims by status",
                "Top 10 providers by claim volume",
                "Compare claim volume for November and October 2025",
                "Show me claims by state",
                "What is the total claim cost this month?"
            ])
        
        if 'user' in table_lower:
            queries.extend([
                "How many users are in each state?",
                "Show me user distribution by region"
            ])
        
        if 'provider' in table_lower:
            queries.extend([
                "Show me all providers",
                "Top providers by claim count"
            ])
        
        return queries
    
    async def get_comprehensive_schema(self) -> Dict[str, Any]:
        """Get comprehensive schema information"""
        if not self._schema_cache:
            await self.inspect_database()
        return self._schema_cache or {}


# Global instance
database_inspector = DatabaseInspector()

