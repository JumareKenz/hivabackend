# Database Inspection & Schema Loading Guide

## Overview

The system now includes comprehensive database inspection that:
1. Scans all tables in the database
2. Analyzes schemas and relationships
3. Samples data to understand structure
4. Identifies common query patterns
5. Builds semantic understanding for better SQL generation

## Running Database Inspection

### Initial Inspection

Run the inspection script to analyze your database:

```bash
cd /root/hiva/services/ai
python scripts/inspect_database.py
```

This will:
- Connect to your database
- Scan all tables and views
- Analyze schemas and relationships
- Sample data from each table
- Generate `ADMIN_QUERY_GUIDE.md` documentation
- Save detailed schema to `database_schema.json`

### Output Files

1. **ADMIN_QUERY_GUIDE.md** - Comprehensive guide of common admin queries
2. **database_schema.json** - Detailed schema information in JSON format

## How It Works

### 1. Database Inspector (`database_inspector.py`)

The inspector:
- Gets all tables (base tables + analytics views)
- Analyzes each table's schema
- Samples data (5 rows per table) to understand structure
- Identifies relationships between tables
- Infers semantic types for columns
- Identifies common query patterns

### 2. Schema Loader (`schema_loader.py`)

The loader:
- Caches comprehensive schema information
- Filters schema based on query content
- Merges inspection results with analytics view manifests
- Provides unified semantic manifest to SQL generator

### 3. Enhanced SQL Generator Integration

The SQL generator now:
- Uses comprehensive schema instead of basic schema info
- Gets filtered schema relevant to the query
- Includes query patterns in context
- Has better understanding of table relationships

## Schema Analysis Features

### Column Semantic Types

The inspector automatically categorizes columns:
- `primary_key` - Unique identifiers
- `foreign_key` - References to other tables
- `temporal` - Dates and timestamps
- `monetary` - Cost, price, amount fields
- `categorical` - Status, type, category fields
- `geographic` - Location, state, region fields
- `contact_info` - Email, phone fields
- `identifier_text` - Names, titles, labels

### Relationship Detection

Automatically identifies:
- `users` ← `claims.user_id`
- `providers` ← `claims.provider_id`
- `states` ← `users.state` or `users.state_id`

### Query Pattern Identification

Identifies common patterns like:
- Claims by status
- Claims by date range
- Claims by provider
- Claims by state
- User distribution
- Provider performance
- Revenue analysis
- Time-series trends
- Period comparisons

## Admin Query Documentation

The generated `ADMIN_QUERY_GUIDE.md` includes:

1. **Claims Analysis** - Common claim-related queries
2. **Provider Analysis** - Provider performance queries
3. **User/Patient Analysis** - User distribution queries
4. **Financial Analysis** - Revenue and payment queries
5. **Geographic Analysis** - State/region queries
6. **Time-Series Analysis** - Trend analysis queries
7. **Comparison Queries** - Month-over-month, year-over-year

Each section includes:
- Query descriptions
- Example queries
- Tables used
- Aggregation requirements

## Benefits

1. **Better SQL Generation** - LLM has full context of database structure
2. **Smarter Query Understanding** - Knows relationships and patterns
3. **Comprehensive Documentation** - Admins know what they can ask
4. **Automatic Pattern Recognition** - Identifies common query types
5. **Semantic Understanding** - Knows what each column represents

## Usage

The inspection runs automatically when:
- First query is made (lazy loading)
- Schema is explicitly refreshed
- Database structure changes

To force refresh:
```python
from app.services.schema_loader import schema_loader
await schema_loader.load_comprehensive_schema(force_refresh=True)
```

## Privacy Compliance

- Inspection prefers analytics views over raw tables
- Only samples 5 rows per table (for structure understanding)
- All queries still go through privacy validation
- PII is masked in sampled data

## Troubleshooting

If inspection fails:
1. Check database connection
2. Verify analytics views exist
3. Check table permissions
4. Review error logs

The system will fall back to basic schema info if inspection fails.

