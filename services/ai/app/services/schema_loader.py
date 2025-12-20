"""
Schema Loader - Loads and caches comprehensive database schema
Integrates with database inspector to provide rich schema context
"""
import asyncio
from typing import Dict, Any, Optional
from app.services.database_inspector import database_inspector
from app.services.analytics_view_service import analytics_view_service


class SchemaLoader:
    """
    Loads and manages comprehensive database schema for SQL generation.
    Integrates database inspection with analytics view service.
    """
    
    def __init__(self):
        self._comprehensive_schema: Optional[Dict[str, Any]] = None
        self._semantic_manifest: Optional[Dict[str, Any]] = None
    
    async def load_comprehensive_schema(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Load comprehensive database schema including:
        - All tables and their schemas
        - Relationships
        - Sample data
        - Query patterns
        - Semantic manifest
        
        Args:
            force_refresh: If True, re-inspect database even if cached
        
        Returns:
            Comprehensive schema dictionary
        """
        if self._comprehensive_schema and not force_refresh:
            return self._comprehensive_schema
        
        print("📚 Loading comprehensive database schema...")
        
        # Inspect database
        inspection = await database_inspector.inspect_database()
        
        # Get analytics view semantic manifest
        analytics_manifest = await analytics_view_service.get_semantic_manifest()
        
        # Merge analytics view info with inspection results
        self._comprehensive_schema = {
            **inspection,
            'analytics_views_manifest': analytics_manifest
        }
        
        # Build unified semantic manifest
        self._semantic_manifest = self._build_unified_manifest(
            inspection.get('semantic_manifest', {}),
            analytics_manifest
        )
        
        self._comprehensive_schema['unified_semantic_manifest'] = self._semantic_manifest
        
        print(f"✅ Schema loaded: {len(inspection.get('tables', []))} tables analyzed")
        return self._comprehensive_schema
    
    def _build_unified_manifest(self, inspection_manifest: Dict, analytics_manifest: Dict) -> Dict:
        """Build unified semantic manifest from inspection and analytics views"""
        unified = {}
        
        # Start with inspection manifest
        unified.update(inspection_manifest)
        
        # Enhance with analytics view information
        for table_name, table_info in analytics_manifest.items():
            if table_name not in unified:
                unified[table_name] = table_info
            else:
                # Merge column descriptions
                existing_cols = unified[table_name].get('columns', {})
                new_cols = table_info.get('columns', {})
                
                for col_name, col_info in new_cols.items():
                    if col_name in existing_cols:
                        # Merge descriptions
                        existing_cols[col_name].update(col_info)
                    else:
                        existing_cols[col_name] = col_info
                
                unified[table_name]['columns'] = existing_cols
        
        return unified
    
    async def get_schema_for_query(self, query: str) -> Dict[str, Any]:
        """
        Get relevant schema information for a specific query.
        Filters and prioritizes tables/columns based on query content.
        
        Args:
            query: Natural language query
        
        Returns:
            Filtered schema information relevant to the query
        """
        if not self._comprehensive_schema:
            await self.load_comprehensive_schema()
        
        query_lower = query.lower()
        
        # Identify relevant tables
        relevant_tables = []
        all_tables = self._comprehensive_schema.get('table_schemas', {})
        
        for table_name, schema in all_tables.items():
            table_lower = table_name.lower().replace('analytics_view_', '')
            
            # Check if query mentions this table
            if table_lower in query_lower:
                relevant_tables.append((table_name, schema, 10))  # High priority
            elif any(keyword in query_lower for keyword in self._get_table_keywords(table_lower)):
                relevant_tables.append((table_name, schema, 5))  # Medium priority
        
        # Sort by priority
        relevant_tables.sort(key=lambda x: x[2], reverse=True)
        
        # Build filtered schema
        filtered_schema = {
            'tables': [{'table_name': name, **schema} for name, schema, _ in relevant_tables[:20]],  # Top 20
            'relationships': self._comprehensive_schema.get('relationships', {}),
            'query_patterns': self._comprehensive_schema.get('query_patterns', [])
        }
        
        return filtered_schema
    
    def _get_table_keywords(self, table_name: str) -> List[str]:
        """Get keywords associated with a table"""
        keywords_map = {
            'claims': ['claim', 'claim volume', 'claim count', 'claim cost'],
            'users': ['user', 'patient', 'beneficiary', 'member'],
            'providers': ['provider', 'facility', 'hospital', 'clinic'],
            'states': ['state', 'region', 'location', 'geographic'],
            'transactions': ['transaction', 'payment', 'revenue', 'financial'],
            'appointments': ['appointment', 'schedule', 'booking'],
        }
        
        for key, keywords in keywords_map.items():
            if key in table_name:
                return keywords
        
        return []
    
    def get_semantic_manifest(self) -> Dict[str, Any]:
        """Get unified semantic manifest"""
        return self._semantic_manifest or {}


# Global instance
schema_loader = SchemaLoader()

