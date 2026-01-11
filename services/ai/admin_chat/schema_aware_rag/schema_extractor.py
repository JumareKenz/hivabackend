#!/usr/bin/env python3
"""
Schema Extractor - Extract DDL and metadata from the database
Part of Schema-Aware RAG System for Admin Chatbot

This script connects to the 'hip' database and extracts:
1. DDL (CREATE TABLE statements) for top 20 most important tables
2. Column metadata including types, constraints, and relationships
3. Table relationships (foreign keys)
4. Sample data patterns for better understanding
"""

import asyncio
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path

# Import database service
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from app.services.database_service import database_service


@dataclass
class ColumnInfo:
    """Column metadata"""
    name: str
    data_type: str
    is_nullable: bool
    is_primary_key: bool = False
    is_foreign_key: bool = False
    references_table: Optional[str] = None
    references_column: Optional[str] = None
    default_value: Optional[str] = None
    description: Optional[str] = None


@dataclass
class TableInfo:
    """Table metadata with importance scoring"""
    name: str
    columns: List[ColumnInfo]
    row_count: int
    primary_key: Optional[str] = None
    foreign_keys: List[Dict[str, str]] = field(default_factory=list)
    importance_score: float = 0.0
    domain: str = "general"  # clinical, providers, financial, general
    description: str = ""
    sample_values: Dict[str, List[Any]] = field(default_factory=dict)


class SchemaExtractor:
    """
    Extracts and manages database schema for RAG system
    
    Features:
    - Automatic DDL generation
    - Table importance scoring (for selective retrieval)
    - Foreign key relationship mapping
    - Domain classification (clinical, providers, financial)
    """
    
    # Core tables for the HIP healthcare system - ranked by importance
    CORE_TABLES = {
        # Domain: Clinical Claims & Diagnosis
        'claims': {'domain': 'clinical', 'importance': 100, 'desc': 'Healthcare claims submitted by patients'},
        'service_summaries': {'domain': 'clinical', 'importance': 95, 'desc': 'Service summary records linking claims to diagnoses'},
        'diagnoses': {'domain': 'clinical', 'importance': 90, 'desc': 'Medical diagnosis codes and names'},
        'services': {'domain': 'clinical', 'importance': 85, 'desc': 'Medical services catalog'},
        'claims_services': {'domain': 'clinical', 'importance': 85, 'desc': 'Junction table linking claims to services'},
        'health_records': {'domain': 'clinical', 'importance': 80, 'desc': 'Patient health records'},
        
        # Domain: Providers & Facilities
        'providers': {'domain': 'providers', 'importance': 90, 'desc': 'Healthcare providers (hospitals, clinics)'},
        'facility_accreditations': {'domain': 'providers', 'importance': 75, 'desc': 'Provider accreditation status'},
        'quality_assurances': {'domain': 'providers', 'importance': 70, 'desc': 'Quality assurance records'},
        
        # Domain: Users & Demographics
        'users': {'domain': 'users', 'importance': 95, 'desc': 'System users (patients, providers, admins)'},
        'dependants': {'domain': 'users', 'importance': 80, 'desc': 'Patient dependents'},
        'states': {'domain': 'users', 'importance': 85, 'desc': 'Nigerian states for geographic filtering'},
        'lgas': {'domain': 'users', 'importance': 75, 'desc': 'Local Government Areas'},
        
        # Domain: Financial
        'transactions': {'domain': 'financial', 'importance': 75, 'desc': 'Financial transactions'},
        'authorization_codes': {'domain': 'financial', 'importance': 70, 'desc': 'Pre-authorization codes for claims'},
        
        # Domain: Administration
        'drugs': {'domain': 'clinical', 'importance': 70, 'desc': 'Pharmaceutical drug catalog'},
        'comments': {'domain': 'admin', 'importance': 50, 'desc': 'Comments on claims/records'},
        'documents': {'domain': 'admin', 'importance': 45, 'desc': 'Uploaded documents'},
    }
    
    # Known canonical join paths (critical for correct SQL generation)
    CANONICAL_JOINS = {
        'claims_to_diagnosis': {
            'path': 'claims → diagnoses (via CAST)',
            'sql': 'claims c JOIN diagnoses d ON d.id = CAST(c.diagnosis AS UNSIGNED) WHERE c.diagnosis REGEXP \'^[0-9]+$\'',
            'description': 'Link claims to diagnoses via claims.diagnosis TEXT column (contains diagnosis ID)'
        },
        'claims_to_services': {
            'path': 'claims → claims_services → services',
            'sql': 'claims c JOIN claims_services cs ON cs.claims_id = c.id JOIN services s ON s.id = cs.services_id',
            'description': 'Link claims to medical services via junction table'
        },
        'claims_to_provider': {
            'path': 'claims → providers',
            'sql': 'claims c JOIN providers p ON c.provider_id = p.id',
            'description': 'Link claims to healthcare providers'
        },
        'claims_to_user': {
            'path': 'claims → users',
            'sql': 'claims c JOIN users u ON c.user_id = u.id',
            'description': 'Link claims to patients (users)'
        },
        'user_to_state': {
            'path': 'users → states',
            'sql': 'users u JOIN states s ON u.state = s.id',
            'description': 'Link users to their state for geographic filtering'
        },
        'claims_to_state': {
            'path': 'claims → users → states',
            'sql': 'claims c JOIN users u ON c.user_id = u.id JOIN states s ON u.state = s.id',
            'description': 'Link claims to states via user relationship'
        }
    }
    
    def __init__(self):
        self.tables: Dict[str, TableInfo] = {}
        self.ddl_cache: Dict[str, str] = {}
        self._initialized = False
        self._output_dir = Path(__file__).parent / "extracted_schema"
        self._output_dir.mkdir(exist_ok=True)
    
    async def initialize(self) -> bool:
        """Initialize database connection"""
        if not database_service.pool:
            await database_service.initialize()
        return database_service.pool is not None
    
    async def extract_all_tables(self) -> List[str]:
        """Get list of all tables in the database"""
        query = """
            SELECT table_name, table_rows
            FROM information_schema.tables
            WHERE table_schema = DATABASE()
            AND table_type = 'BASE TABLE'
            ORDER BY table_rows DESC
        """
        result = await database_service.execute_query(query)
        return [(row['table_name'], row['table_rows'] or 0) for row in result]
    
    async def extract_table_columns(self, table_name: str) -> List[ColumnInfo]:
        """Extract column information for a table"""
        query = """
            SELECT 
                c.column_name,
                c.data_type,
                c.is_nullable,
                c.column_key,
                c.column_default,
                c.extra,
                kcu.referenced_table_name,
                kcu.referenced_column_name
            FROM information_schema.columns c
            LEFT JOIN information_schema.key_column_usage kcu 
                ON c.table_schema = kcu.table_schema 
                AND c.table_name = kcu.table_name 
                AND c.column_name = kcu.column_name
                AND kcu.referenced_table_name IS NOT NULL
            WHERE c.table_schema = DATABASE()
            AND c.table_name = %s
            ORDER BY c.ordinal_position
        """
        result = await database_service.execute_query(query, [table_name])
        
        columns = []
        for row in result:
            col = ColumnInfo(
                name=row['column_name'],
                data_type=row['data_type'],
                is_nullable=row['is_nullable'] == 'YES',
                is_primary_key=row['column_key'] == 'PRI',
                is_foreign_key=row['referenced_table_name'] is not None,
                references_table=row['referenced_table_name'],
                references_column=row['referenced_column_name'],
                default_value=row['column_default']
            )
            columns.append(col)
        
        return columns
    
    async def extract_foreign_keys(self, table_name: str) -> List[Dict[str, str]]:
        """Extract foreign key relationships for a table"""
        query = """
            SELECT 
                kcu.column_name,
                kcu.referenced_table_name,
                kcu.referenced_column_name,
                kcu.constraint_name
            FROM information_schema.key_column_usage kcu
            WHERE kcu.table_schema = DATABASE()
            AND kcu.table_name = %s
            AND kcu.referenced_table_name IS NOT NULL
        """
        result = await database_service.execute_query(query, [table_name])
        
        return [
            {
                'column': row['column_name'],
                'references_table': row['referenced_table_name'],
                'references_column': row['referenced_column_name'],
                'constraint': row['constraint_name']
            }
            for row in result
        ]
    
    async def get_sample_values(self, table_name: str, columns: List[str], limit: int = 5) -> Dict[str, List[Any]]:
        """Get sample values for specified columns (for understanding data patterns)"""
        samples = {}
        for col in columns[:5]:  # Limit to 5 columns for safety
            try:
                query = f"SELECT DISTINCT `{col}` FROM `{table_name}` WHERE `{col}` IS NOT NULL LIMIT {limit}"
                result = await database_service.execute_query(query)
                samples[col] = [row[col] for row in result]
            except Exception:
                samples[col] = []
        return samples
    
    def generate_ddl(self, table_info: TableInfo) -> str:
        """Generate CREATE TABLE DDL statement"""
        lines = [f"CREATE TABLE `{table_info.name}` ("]
        
        col_defs = []
        for col in table_info.columns:
            col_def = f"  `{col.name}` {col.data_type.upper()}"
            if not col.is_nullable:
                col_def += " NOT NULL"
            if col.default_value:
                col_def += f" DEFAULT {col.default_value}"
            if col.is_primary_key:
                col_def += " PRIMARY KEY"
            col_defs.append(col_def)
        
        # Add foreign key constraints
        for fk in table_info.foreign_keys:
            fk_def = f"  FOREIGN KEY (`{fk['column']}`) REFERENCES `{fk['references_table']}`(`{fk['references_column']}`)"
            col_defs.append(fk_def)
        
        lines.append(",\n".join(col_defs))
        lines.append(");")
        
        # Add comment with description
        ddl = "\n".join(lines)
        if table_info.description:
            ddl = f"-- {table_info.description}\n-- Rows: ~{table_info.row_count:,}\n{ddl}"
        
        return ddl
    
    async def extract_table_info(self, table_name: str) -> TableInfo:
        """Extract complete information for a single table"""
        # Get row count
        count_query = f"SELECT COUNT(*) as cnt FROM `{table_name}`"
        try:
            count_result = await database_service.execute_query(count_query)
            row_count = count_result[0]['cnt'] if count_result else 0
        except Exception:
            row_count = 0
        
        # Get columns
        columns = await self.extract_table_columns(table_name)
        
        # Get foreign keys
        foreign_keys = await self.extract_foreign_keys(table_name)
        
        # Get metadata from CORE_TABLES if available
        core_info = self.CORE_TABLES.get(table_name, {})
        
        # Calculate importance score
        importance = core_info.get('importance', 0)
        if importance == 0:
            # Auto-score based on row count and relationships
            if row_count > 100000:
                importance = 60
            elif row_count > 10000:
                importance = 40
            elif row_count > 1000:
                importance = 20
            else:
                importance = 10
            # Boost for foreign key relationships
            importance += len(foreign_keys) * 5
        
        # Find primary key
        primary_key = next((col.name for col in columns if col.is_primary_key), None)
        
        table_info = TableInfo(
            name=table_name,
            columns=columns,
            row_count=row_count,
            primary_key=primary_key,
            foreign_keys=foreign_keys,
            importance_score=importance,
            domain=core_info.get('domain', 'general'),
            description=core_info.get('desc', '')
        )
        
        return table_info
    
    async def extract_top_tables(self, n: int = 50) -> Dict[str, TableInfo]:
        """
        Extract DDL for top N most important tables
        
        Priority:
        1. Core tables defined in CORE_TABLES
        2. Tables with most rows
        3. Tables with most relationships
        """
        print(f"🔄 Extracting schema for top {n} tables...")
        
        # Get all tables
        all_tables = await self.extract_all_tables()
        
        # Score and sort tables
        scored_tables = []
        for table_name, row_count in all_tables:
            core_info = self.CORE_TABLES.get(table_name, {})
            base_score = core_info.get('importance', 0)
            
            # Skip system tables
            if table_name.startswith('telescope_') or table_name.startswith('oauth_'):
                continue
            
            # Calculate score
            if base_score == 0:
                # Auto-score
                if row_count > 100000:
                    base_score = 50
                elif row_count > 10000:
                    base_score = 30
                elif row_count > 1000:
                    base_score = 15
                else:
                    base_score = 5
            
            scored_tables.append((table_name, base_score, row_count))
        
        # Sort by score (descending)
        scored_tables.sort(key=lambda x: (-x[1], -x[2]))
        
        # Extract top N
        tables = {}
        for table_name, score, row_count in scored_tables[:n]:
            print(f"  📊 Extracting: {table_name} (score: {score}, rows: {row_count:,})")
            table_info = await self.extract_table_info(table_name)
            tables[table_name] = table_info
            self.ddl_cache[table_name] = self.generate_ddl(table_info)
        
        self.tables = tables
        self._initialized = True
        
        print(f"✅ Extracted {len(tables)} table schemas")
        return tables
    
    def get_ddl(self, table_name: str) -> Optional[str]:
        """Get DDL for a specific table"""
        return self.ddl_cache.get(table_name)
    
    def get_all_ddl(self) -> str:
        """Get combined DDL for all extracted tables"""
        return "\n\n".join(self.ddl_cache.values())
    
    def get_tables_by_domain(self, domain: str) -> List[TableInfo]:
        """Get tables filtered by domain"""
        return [t for t in self.tables.values() if t.domain == domain]
    
    def get_canonical_joins(self) -> Dict[str, Dict]:
        """Get canonical join paths for SQL generation"""
        return self.CANONICAL_JOINS
    
    def generate_documentation(self) -> str:
        """Generate human-readable documentation for training"""
        docs = []
        
        # Add canonical join paths
        docs.append("=== CANONICAL JOIN PATHS ===")
        docs.append("These are the CORRECT ways to join tables in this database:\n")
        for name, info in self.CANONICAL_JOINS.items():
            docs.append(f"• {name}:")
            docs.append(f"  Path: {info['path']}")
            docs.append(f"  SQL: {info['sql']}")
            docs.append(f"  Description: {info['description']}\n")
        
        # Add table descriptions
        docs.append("\n=== TABLE DESCRIPTIONS ===")
        for table_name, table_info in sorted(self.tables.items(), key=lambda x: -x[1].importance_score):
            docs.append(f"\n• {table_name} ({table_info.domain})")
            docs.append(f"  Description: {table_info.description}")
            docs.append(f"  Rows: ~{table_info.row_count:,}")
            docs.append(f"  Primary Key: {table_info.primary_key}")
            
            # Key columns
            key_cols = [c for c in table_info.columns if c.is_primary_key or c.is_foreign_key][:5]
            if key_cols:
                docs.append(f"  Key Columns: {', '.join(c.name for c in key_cols)}")
            
            # Foreign keys
            if table_info.foreign_keys:
                fk_desc = [f"{fk['column']} → {fk['references_table']}" for fk in table_info.foreign_keys]
                docs.append(f"  Foreign Keys: {', '.join(fk_desc)}")
        
        return "\n".join(docs)
    
    async def save_schema(self, filename: str = "schema.json"):
        """Save extracted schema to JSON file"""
        output_path = self._output_dir / filename
        
        data = {
            'extracted_at': datetime.now().isoformat(),
            'tables': {
                name: {
                    'name': t.name,
                    'domain': t.domain,
                    'description': t.description,
                    'row_count': t.row_count,
                    'importance_score': t.importance_score,
                    'primary_key': t.primary_key,
                    'columns': [
                        {
                            'name': c.name,
                            'data_type': c.data_type,
                            'is_nullable': c.is_nullable,
                            'is_primary_key': c.is_primary_key,
                            'is_foreign_key': c.is_foreign_key,
                            'references_table': c.references_table,
                            'references_column': c.references_column
                        }
                        for c in t.columns
                    ],
                    'foreign_keys': t.foreign_keys
                }
                for name, t in self.tables.items()
            },
            'canonical_joins': self.CANONICAL_JOINS,
            'ddl': self.ddl_cache
        }
        
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"✅ Schema saved to {output_path}")
        return output_path
    
    async def save_ddl(self, filename: str = "ddl.sql"):
        """Save DDL statements to SQL file"""
        output_path = self._output_dir / filename
        
        with open(output_path, 'w') as f:
            f.write(f"-- DDL for HIP Healthcare Database\n")
            f.write(f"-- Extracted: {datetime.now().isoformat()}\n")
            f.write(f"-- Tables: {len(self.ddl_cache)}\n\n")
            f.write(self.get_all_ddl())
        
        print(f"✅ DDL saved to {output_path}")
        return output_path
    
    async def save_documentation(self, filename: str = "documentation.md"):
        """Save documentation to markdown file"""
        output_path = self._output_dir / filename
        
        with open(output_path, 'w') as f:
            f.write("# HIP Healthcare Database Documentation\n\n")
            f.write(f"Generated: {datetime.now().isoformat()}\n\n")
            f.write(self.generate_documentation())
        
        print(f"✅ Documentation saved to {output_path}")
        return output_path


# Singleton instance
schema_extractor = SchemaExtractor()


async def main():
    """Main function to run schema extraction"""
    print("=" * 60)
    print("Schema Extractor for HIP Healthcare Database")
    print("=" * 60)
    
    # Initialize
    if not await schema_extractor.initialize():
        print("❌ Failed to initialize database connection")
        return
    
    # Extract top 50 tables
    tables = await schema_extractor.extract_top_tables(n=50)
    
    # Save outputs
    await schema_extractor.save_schema()
    await schema_extractor.save_ddl()
    await schema_extractor.save_documentation()
    
    # Print summary
    print("\n" + "=" * 60)
    print("EXTRACTION SUMMARY")
    print("=" * 60)
    
    print("\nTop Tables by Importance:")
    for name, info in sorted(tables.items(), key=lambda x: -x[1].importance_score)[:10]:
        print(f"  {info.importance_score:3.0f} | {name:30} | {info.row_count:>10,} rows | {info.domain}")
    
    print("\nCanonical Join Paths:")
    for name, join in schema_extractor.get_canonical_joins().items():
        print(f"  • {name}: {join['path']}")
    
    print("\nOutput files:")
    print(f"  • extracted_schema/schema.json")
    print(f"  • extracted_schema/ddl.sql")
    print(f"  • extracted_schema/documentation.md")


if __name__ == "__main__":
    asyncio.run(main())

