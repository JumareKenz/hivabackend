"""
Database Inspection Script
Run this to inspect the database and generate admin query documentation
"""
import asyncio
import json
from pathlib import Path
import sys
from typing import Dict

# Add the app directory to Python path
app_dir = Path(__file__).parent.parent
sys.path.insert(0, str(app_dir))
# Also add parent directory for app.core imports
sys.path.insert(0, str(app_dir.parent))

from app.services.database_service import database_service
from app.services.database_inspector import database_inspector
from app.services.schema_loader import schema_loader


async def main():
    """Main inspection function"""
    print("=" * 80)
    print("DATABASE INSPECTION & ADMIN QUERY DOCUMENTATION GENERATOR")
    print("=" * 80)
    print()
    
    # Initialize database
    print("1. Initializing database connection...")
    await database_service.initialize()
    
    if not database_service.pool:
        print("❌ Database not available. Please check your configuration.")
        return
    
    print("✅ Database connected")
    print()
    
    # Inspect database
    print("2. Inspecting database structure...")
    inspection = await database_inspector.inspect_database()
    print()
    
    # Load comprehensive schema
    print("3. Loading comprehensive schema...")
    comprehensive_schema = await schema_loader.load_comprehensive_schema()
    print()
    
    # Generate documentation
    print("4. Generating admin query documentation...")
    doc = generate_admin_documentation(comprehensive_schema)
    
    # Save documentation
    output_file = Path(__file__).parent.parent / "ADMIN_QUERY_GUIDE.md"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(doc)
    
    print(f"✅ Documentation saved to: {output_file}")
    print()
    
    # Print summary
    print("=" * 80)
    print("INSPECTION SUMMARY")
    print("=" * 80)
    print(f"Tables analyzed: {len(inspection.get('tables', []))}")
    print(f"Query patterns identified: {len(comprehensive_schema.get('query_patterns', []))}")
    print(f"Relationships found: {len(inspection.get('relationships', {}))}")
    print()
    
    # Save detailed schema JSON for reference
    schema_file = Path(__file__).parent.parent / "database_schema.json"
    with open(schema_file, 'w', encoding='utf-8') as f:
        json.dump(comprehensive_schema, f, indent=2, default=str)
    print(f"✅ Detailed schema saved to: {schema_file}")


def generate_admin_documentation(schema: Dict) -> str:
    """Generate comprehensive admin query documentation"""
    doc = """# Admin Query Guide - Common Questions & Queries

This document lists common questions admins may ask and how the system handles them.

## Table of Contents
1. [Claims Analysis](#claims-analysis)
2. [Provider Analysis](#provider-analysis)
3. [User/Patient Analysis](#userpatient-analysis)
4. [Financial Analysis](#financial-analysis)
5. [Geographic Analysis](#geographic-analysis)
6. [Time-Series Analysis](#time-series-analysis)
7. [Comparison Queries](#comparison-queries)

---

"""
    
    # Get query patterns
    patterns = schema.get('query_patterns', [])
    table_schemas = schema.get('table_schemas', {})
    semantic_manifest = schema.get('unified_semantic_manifest', {})
    
    # Claims Analysis
    doc += "## Claims Analysis\n\n"
    claims_patterns = [p for p in patterns if 'claim' in p.get('pattern', '').lower()]
    for pattern in claims_patterns:
        doc += f"### {pattern.get('description')}\n"
        doc += f"**Example Query:** `{pattern.get('example_query')}`\n\n"
        doc += f"**Tables Used:** {', '.join(pattern.get('tables', []))}\n"
        doc += f"**Aggregation:** {'Yes' if pattern.get('aggregation') else 'No'}\n\n"
    
    # Provider Analysis
    doc += "## Provider Analysis\n\n"
    provider_patterns = [p for p in patterns if 'provider' in p.get('pattern', '').lower()]
    for pattern in provider_patterns:
        doc += f"### {pattern.get('description')}\n"
        doc += f"**Example Query:** `{pattern.get('example_query')}`\n\n"
    
    # User Analysis
    doc += "## User/Patient Analysis\n\n"
    user_patterns = [p for p in patterns if 'user' in p.get('pattern', '').lower()]
    for pattern in user_patterns:
        doc += f"### {pattern.get('description')}\n"
        doc += f"**Example Query:** `{pattern.get('example_query')}`\n\n"
    
    # Financial Analysis
    doc += "## Financial Analysis\n\n"
    financial_patterns = [p for p in patterns if 'revenue' in p.get('pattern', '').lower() or 'financial' in p.get('pattern', '').lower()]
    for pattern in financial_patterns:
        doc += f"### {pattern.get('description')}\n"
        doc += f"**Example Query:** `{pattern.get('example_query')}`\n\n"
    
    # Time-Series
    doc += "## Time-Series Analysis\n\n"
    time_patterns = [p for p in patterns if 'time' in p.get('pattern', '').lower() or 'series' in p.get('pattern', '').lower()]
    for pattern in time_patterns:
        doc += f"### {pattern.get('description')}\n"
        doc += f"**Example Query:** `{pattern.get('example_query')}`\n\n"
    
    # Comparison
    doc += "## Comparison Queries\n\n"
    comparison_patterns = [p for p in patterns if 'comparison' in p.get('pattern', '').lower() or 'compare' in p.get('pattern', '').lower()]
    for pattern in comparison_patterns:
        doc += f"### {pattern.get('description')}\n"
        doc += f"**Example Query:** `{pattern.get('example_query')}`\n\n"
    
    # Available Tables
    doc += "## Available Tables\n\n"
    doc += "The following tables are available for querying:\n\n"
    for table_name, table_schema in table_schemas.items():
        if not table_name.startswith('information_schema'):
            doc += f"### {table_name}\n"
            description = semantic_manifest.get(table_name, {}).get('description', 'No description available')
            doc += f"**Description:** {description}\n\n"
            
            columns = table_schema.get('column_analysis', {})
            if columns:
                doc += "**Key Columns:**\n"
                for col_name, col_info in list(columns.items())[:10]:  # Top 10 columns
                    semantic_type = col_info.get('semantic_type', 'general')
                    doc += f"- `{col_name}` ({col_info.get('data_type', 'unknown')}) - {semantic_type}\n"
                doc += "\n"
    
    # Common Query Examples
    doc += "## Common Query Examples\n\n"
    doc += "### Claims Queries\n"
    doc += "- `Show me claims by status`\n"
    doc += "- `Top 10 providers by claim volume this month`\n"
    doc += "- `Compare claim volume for November and October 2025`\n"
    doc += "- `Show me claims by state`\n"
    doc += "- `What is the total claim cost this month?`\n\n"
    
    doc += "### Provider Queries\n"
    doc += "- `Show me all providers`\n"
    doc += "- `Top providers by claim count`\n"
    doc += "- `Provider performance this month`\n\n"
    
    doc += "### User Queries\n"
    doc += "- `How many users are in each state?`\n"
    doc += "- `Show me user distribution by region`\n\n"
    
    doc += "### Financial Queries\n"
    doc += "- `What is the total revenue this month?`\n"
    doc += "- `Show me payment transactions`\n\n"
    
    doc += "### Time-Series Queries\n"
    doc += "- `Show me claim trends over the last 6 months`\n"
    doc += "- `Daily claim volume for this month`\n\n"
    
    doc += "## Privacy & Security\n\n"
    doc += "⚠️ **Important:** All queries are read-only and use privacy-compliant analytics views.\n"
    doc += "- Individual identification queries are blocked\n"
    doc += "- PII is automatically masked in results\n"
    doc += "- Small cell suppression is applied (counts 1-4 are redacted)\n\n"
    
    return doc


if __name__ == "__main__":
    asyncio.run(main())

