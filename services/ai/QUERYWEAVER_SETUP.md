# QueryWeaver Integration Guide

## Overview

QueryWeaver is a graph-powered NL2SQL engine that uses FalkorDB for schema understanding. It provides:
- **Graph-based schema understanding** - Better relationship mapping
- **Contextual memory** - Remembers previous queries
- **Open source** - Built on FalkorDB

## Setup Options

### Option 1: Docker (Recommended)

```bash
# Run QueryWeaver in Docker
docker run -p 5000:5000 -it falkordb/queryweaver

# Or with environment variables
docker run -p 5000:5000 \
  -e DATABASE_URL="mysql://user:pass@host:3306/dbname" \
  -it falkordb/queryweaver
```

### Option 2: Local Installation

```bash
# Install QueryWeaver (if available as Python package)
pip install queryweaver

# Or clone from GitHub
git clone https://github.com/falkordb/queryweaver
cd queryweaver
pip install -r requirements.txt
python app.py
```

## Configuration

Add to your `.env` file:

```bash
# QueryWeaver Configuration
USE_QUERYWEAVER=true
QUERYWEAVER_URL=http://localhost:5000

# Database connection (for QueryWeaver)
QUERYWEAVER_DB_URL=mysql://user:password@host:3306/dbname
```

## Integration

The `queryweaver_service.py` is already integrated with:
- ✅ Enhanced SQL Generator (tries QueryWeaver first, falls back if unavailable)
- ✅ Automatic validation
- ✅ Privacy compliance checks
- ✅ Error handling

## Usage

QueryWeaver is automatically used when:
1. `USE_QUERYWEAVER=true` in config
2. QueryWeaver service is running
3. Query confidence > 0.7

Otherwise, the system falls back to the enhanced SQL generator.

## API Endpoints

QueryWeaver typically provides:
- `POST /api/generate-sql` - Generate SQL from natural language
- `POST /api/validate-sql` - Validate SQL query
- `POST /api/explain-sql` - Explain SQL query
- `GET /health` - Health check

## Benefits

1. **Graph-based understanding** - Better relationship mapping
2. **Contextual memory** - Learns from previous queries
3. **Open source** - Transparent and customizable

## Fallback

If QueryWeaver is unavailable, the system automatically uses:
- Enhanced SQL Generator with Vector RAG
- Self-correction loop
- Privacy compliance

## Testing

```python
from app.services.queryweaver_service import queryweaver_service

# Initialize
await queryweaver_service.initialize()

# Generate SQL
result = await queryweaver_service.generate_sql(
    "Show me top 10 providers by claim volume"
)

print(result)
```

## Notes

- QueryWeaver must use `analytics_view_*` tables for PHI compliance
- All queries are validated before execution
- Privacy compliance is enforced regardless of SQL source

