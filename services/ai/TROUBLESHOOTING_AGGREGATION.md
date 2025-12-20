# Troubleshooting: Aggregation Query Issues

## Problem
Query "Show me top 10 providers by claim volume this month" returns individual claim records instead of aggregated provider summaries.

## Expected vs Actual

**Expected:**
```
provider_name              | claim_count | total_volume
---------------------------|-------------|-------------
Care Crest                 | 150         | 2,500,000
Maria Goretti Hospital     | 120         | 1,800,000
OLAJIDE STEPHEN            | 95          | 1,200,000
... (top 10 only)
```

**Actual:**
- Individual claim records (100+ rows)
- No aggregation
- No grouping by provider
- No limit to top 10

## Debugging Steps

### 1. Check Generated SQL
Look at the API response for the `sql_query` field. It should show:
```sql
SELECT 
    COALESCE(c.provider_name, p.name, ...) as provider_name,
    COUNT(*) as claim_count,
    SUM(c.total_cost) as total_volume
FROM analytics_view_claims c
LEFT JOIN analytics_view_providers p ON c.provider_id = p.id
WHERE DATE(c.created_at) >= '2025-12-01' AND DATE(c.created_at) <= '2025-12-31'
GROUP BY provider_name
ORDER BY claim_count DESC
LIMIT 10
```

If you see a query without `GROUP BY`, that's the problem.

### 2. Check Server Logs
The enhanced endpoint now logs the generated SQL:
```
[DEBUG] Generated SQL: <sql here>
[DEBUG] Query: <user query>
```

### 3. Verify Analytics Views Exist
Run:
```bash
python -m app.services.setup_analytics_views
```

Then check if `analytics_view_claims` and `analytics_view_providers` exist in your database.

### 4. Verify Enhanced Generator is Used
Check `ai/app/api/v1/admin.py` line 81 - it should use:
```python
sql_result = await enhanced_sql_generator.generate_sql(...)
```

NOT:
```python
sql_result = await sql_generator.generate_sql(...)  # OLD - wrong!
```

## Quick Fixes

### If Fast-Path Isn't Matching
The pattern should match:
- "top" + "provider"/"facility" + "claim"/"volume"
- OR "show" + "top" + "provider"/"facility"

If your query doesn't match, try rephrasing:
- ✅ "Show me top 10 providers by claim volume this month"
- ✅ "Top 10 providers by claims this month"
- ✅ "Top facilities by volume"
- ❌ "Which providers have the most claims" (might not match)

### If Analytics Views Don't Exist
The system will try to query `analytics_view_claims` but if the views don't exist, you'll get an error. Set them up first.

### If Query Still Returns Individual Records
The self-correction loop should catch this, but if it doesn't:
1. Check the `sql_query` in the response
2. Manually verify the SQL works in your database
3. The issue might be in the schema - provider names might be in a different column

## Common Issues

### Issue 1: Provider Names in Wrong Column
If provider names appear in `user_name` column instead of a provider column, the JOIN might be wrong. Check your actual schema.

### Issue 2: Date Filter Not Working
If "this month" isn't being detected, check for typos. The code handles "this mont" but other variations might not work.

### Issue 3: GROUP BY Not Working
If the SQL has GROUP BY but still returns individual rows, check:
- Are there duplicate provider names?
- Is the GROUP BY clause correct?
- Are there NULL values causing issues?

## Next Steps

1. **Check the `sql_query` field** in your API response
2. **Share the generated SQL** so we can debug further
3. **Verify analytics views exist** in your database
4. **Check server logs** for the DEBUG output

The fast-path should now catch this query pattern and generate proper aggregation SQL.

