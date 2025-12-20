"""
Standalone Database Inspection Script
Doesn't require full app setup - uses direct database connection
"""
import asyncio
import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

# Database configuration from environment
DB_TYPE = os.getenv("ANALYTICS_DB_TYPE", "mysql")
DB_HOST = os.getenv("ANALYTICS_DB_HOST")
DB_PORT = int(os.getenv("ANALYTICS_DB_PORT", "3306"))
DB_NAME = os.getenv("ANALYTICS_DB_NAME")
DB_USER = os.getenv("ANALYTICS_DB_USER")
DB_PASSWORD = os.getenv("ANALYTICS_DB_PASSWORD")


async def inspect_database_standalone():
    """Standalone database inspection"""
    print("=" * 80)
    print("DATABASE INSPECTION & ADMIN QUERY DOCUMENTATION GENERATOR")
    print("=" * 80)
    print()
    
    if not all([DB_HOST, DB_NAME, DB_USER, DB_PASSWORD]):
        print("❌ Database configuration missing. Please set:")
        print("   ANALYTICS_DB_HOST, ANALYTICS_DB_NAME, ANALYTICS_DB_USER, ANALYTICS_DB_PASSWORD")
        return
    
    # Import database driver
    if DB_TYPE == "mysql":
        import aiomysql
        pool = await aiomysql.create_pool(
            host=DB_HOST,
            port=DB_PORT,
            db=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            minsize=1,
            maxsize=5
        )
    elif DB_TYPE == "postgresql":
        import asyncpg
        conn_string = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        pool = await asyncpg.create_pool(conn_string, min_size=1, max_size=5)
    else:
        print(f"❌ Unsupported database type: {DB_TYPE}")
        return
    
    print("✅ Database connected")
    print()
    
    # Get all tables
    print("2. Scanning database tables...")
    tables = await get_all_tables(pool, DB_TYPE, DB_NAME)
    print(f"   Found {len(tables)} tables")
    print()
    
    # Analyze each table
    print("3. Analyzing table schemas...")
    table_schemas = {}
    for table in tables[:50]:  # Limit to 50 tables
        table_name = table.get('table_name', '')
        if table_name:
            schema = await analyze_table(pool, DB_TYPE, table_name, DB_NAME)
            table_schemas[table_name] = schema
            print(f"   ✓ {table_name} - {len(schema.get('columns', []))} columns")
    
    print()
    
    # Generate documentation
    print("4. Generating documentation...")
    doc = generate_documentation(table_schemas, tables)
    
    # Save documentation
    output_file = Path(__file__).parent.parent / "ADMIN_QUERY_GUIDE.md"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(doc)
    
    print(f"✅ Documentation saved to: {output_file}")
    print()
    
    # Save schema JSON
    schema_file = Path(__file__).parent.parent / "database_schema.json"
    with open(schema_file, 'w', encoding='utf-8') as f:
        json.dump({
            'tables': tables,
            'table_schemas': table_schemas
        }, f, indent=2, default=str)
    
    print(f"✅ Schema saved to: {schema_file}")
    print()
    
    # Close pool
    pool.close()
    await pool.wait_closed()
    
    print("=" * 80)
    print("INSPECTION COMPLETE")
    print("=" * 80)
    print(f"Tables analyzed: {len(table_schemas)}")
    print(f"Total tables found: {len(tables)}")


async def get_all_tables(pool, db_type: str, db_name: str) -> List[Dict]:
    """Get all tables from database"""
    if db_type == "mysql":
        query = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = %s
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(query, (db_name,))
                return await cursor.fetchall()
    else:  # PostgreSQL
        query = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """
        async with pool.acquire() as conn:
            rows = await conn.fetch(query)
            return [dict(row) for row in rows]


async def analyze_table(pool, db_type: str, table_name: str, db_name: str) -> Dict:
    """Analyze a single table"""
    if db_type == "mysql":
        query = """
            SELECT 
                column_name,
                data_type,
                is_nullable,
                column_default
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
        """
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(query, (db_name, table_name))
                columns = await cursor.fetchall()
    else:  # PostgreSQL
        query = """
            SELECT 
                column_name,
                data_type,
                is_nullable,
                column_default
            FROM information_schema.columns
            WHERE table_name = $1
            ORDER BY ordinal_position
        """
        async with pool.acquire() as conn:
            columns = await conn.fetch(query, table_name)
            columns = [dict(row) for row in columns]
    
    # Sample data
    try:
        if db_type == "mysql":
            sample_query = f"SELECT * FROM `{table_name}` LIMIT 3"
            async with pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(sample_query)
                    samples = await cursor.fetchall()
        else:
            sample_query = f'SELECT * FROM "{table_name}" LIMIT 3'
            async with pool.acquire() as conn:
                samples = await conn.fetch(sample_query)
                samples = [dict(row) for row in samples]
    except:
        samples = []
    
    return {
        'table_name': table_name,
        'columns': columns,
        'sample_data': samples[:3]  # Limit to 3 samples
    }


def generate_documentation(table_schemas: Dict, all_tables: List[Dict]) -> str:
    """Generate admin query documentation"""
    doc = """# Admin Query Guide - Database Schema & Common Queries

This document was automatically generated by inspecting your database structure.

## Available Tables

"""
    
    # Group tables by category
    claims_tables = [t for t in table_schemas.keys() if 'claim' in t.lower()]
    user_tables = [t for t in table_schemas.keys() if any(x in t.lower() for x in ['user', 'patient', 'member'])]
    provider_tables = [t for t in table_schemas.keys() if any(x in t.lower() for x in ['provider', 'facility', 'hospital'])]
    financial_tables = [t for t in table_schemas.keys() if any(x in t.lower() for x in ['transaction', 'payment', 'order', 'billing'])]
    other_tables = [t for t in table_schemas.keys() if t not in claims_tables + user_tables + provider_tables + financial_tables]
    
    # Claims Tables
    if claims_tables:
        doc += "### Claims Tables\n\n"
        for table in claims_tables:
            doc += f"#### {table}\n"
            schema = table_schemas[table]
            doc += f"**Columns:** {len(schema.get('columns', []))}\n\n"
            for col in schema.get('columns', [])[:10]:
                col_name = col.get('column_name', '')
                col_type = col.get('data_type', '')
                doc += f"- `{col_name}` ({col_type})\n"
            doc += "\n"
    
    # User Tables
    if user_tables:
        doc += "### User/Patient Tables\n\n"
        for table in user_tables:
            doc += f"#### {table}\n"
            schema = table_schemas[table]
            doc += f"**Columns:** {len(schema.get('columns', []))}\n\n"
            for col in schema.get('columns', [])[:10]:
                col_name = col.get('column_name', '')
                col_type = col.get('data_type', '')
                doc += f"- `{col_name}` ({col_type})\n"
            doc += "\n"
    
    # Provider Tables
    if provider_tables:
        doc += "### Provider Tables\n\n"
        for table in provider_tables:
            doc += f"#### {table}\n"
            schema = table_schemas[table]
            doc += f"**Columns:** {len(schema.get('columns', []))}\n\n"
            for col in schema.get('columns', [])[:10]:
                col_name = col.get('column_name', '')
                col_type = col.get('data_type', '')
                doc += f"- `{col_name}` ({col_type})\n"
            doc += "\n"
    
    # Financial Tables
    if financial_tables:
        doc += "### Financial Tables\n\n"
        for table in financial_tables:
            doc += f"#### {table}\n"
            schema = table_schemas[table]
            doc += f"**Columns:** {len(schema.get('columns', []))}\n\n"
            for col in schema.get('columns', [])[:10]:
                col_name = col.get('column_name', '')
                col_type = col.get('data_type', '')
                doc += f"- `{col_name}` ({col_type})\n"
            doc += "\n"
    
    # Other Tables
    if other_tables:
        doc += "### Other Tables\n\n"
        for table in other_tables[:20]:  # Limit to 20
            doc += f"#### {table}\n"
            schema = table_schemas[table]
            doc += f"**Columns:** {len(schema.get('columns', []))}\n\n"
    
    # Common Query Examples
    doc += """## Common Query Examples

Based on your database structure, here are example queries you can ask:

### Claims Analysis
- "Show me claims by status"
- "Top 10 providers by claim volume this month"
- "Compare claim volume for November and October 2025"
- "Show me claims by state"
- "What is the total claim cost this month?"

### Provider Analysis
- "Show me all providers"
- "Top providers by claim count"
- "Provider performance this month"

### User/Patient Analysis
- "How many users are in each state?"
- "Show me user distribution by region"

### Financial Analysis
- "What is the total revenue this month?"
- "Show me payment transactions"

### Time-Series Analysis
- "Show me claim trends over the last 6 months"
- "Daily claim volume for this month"

## Privacy & Security

⚠️ **Important:** All queries are read-only and use privacy-compliant analytics views.
- Individual identification queries are blocked
- PII is automatically masked in results
- Small cell suppression is applied (counts 1-4 are redacted)

## Notes

This documentation was generated automatically. For the most up-to-date schema information,
check the `database_schema.json` file.

"""
    
    return doc


if __name__ == "__main__":
    # Import database drivers
    if DB_TYPE == "mysql":
        import aiomysql
    elif DB_TYPE == "postgresql":
        import asyncpg
    
    asyncio.run(inspect_database_standalone())

