# Database Inspection System

## Quick Start

Run the database inspection to analyze your database and generate documentation:

```bash
cd /root/hiva/services/ai
python scripts/inspect_database.py
```

This will:
1. ✅ Connect to your database
2. ✅ Scan all tables and views
3. ✅ Analyze schemas and relationships  
4. ✅ Sample data to understand structure
5. ✅ Generate `ADMIN_QUERY_GUIDE.md` with common queries
6. ✅ Save detailed schema to `database_schema.json`

## What Gets Inspected

### Tables Analyzed
- All base tables in your database
- All analytics views (if they exist)
- System tables are excluded

### For Each Table
- **Schema**: Column names, types, nullability
- **Relationships**: Foreign keys and table relationships
- **Sample Data**: 5 rows to understand data structure
- **Row Count**: Estimated number of rows
- **Semantic Types**: What each column represents

### Query Patterns Identified
- Claims analysis queries
- Provider performance queries
- User/patient distribution queries
- Financial/revenue queries
- Time-series analysis
- Geographic analysis
- Period comparisons

## Generated Files

### ADMIN_QUERY_GUIDE.md
Comprehensive guide listing:
- Common questions admins may ask
- Example queries for each pattern
- Tables used for each query type
- Aggregation requirements

### database_schema.json
Detailed JSON file with:
- Complete table schemas
- Column analysis
- Relationships
- Sample data
- Query patterns

## Integration with Chatbot

The inspection results are automatically used by the SQL generator:
- **Better Context**: LLM knows all tables and relationships
- **Smarter Queries**: Understands query patterns
- **Accurate SQL**: Better schema awareness = better SQL

## Privacy Compliance

- Prefers analytics views over raw tables
- Only samples 5 rows (for structure, not data)
- All queries still go through privacy validation
- PII is masked in results

## Manual Refresh

To force a fresh inspection:

```python
from app.services.schema_loader import schema_loader
await schema_loader.load_comprehensive_schema(force_refresh=True)
```

## Troubleshooting

**Inspection fails?**
- Check database connection
- Verify table permissions
- Check if analytics views exist
- Review error logs

**Schema not updating?**
- Force refresh with `force_refresh=True`
- Clear cache in schema_loader
- Re-run inspection script

The system will fall back to basic schema info if inspection fails, so queries will still work.

