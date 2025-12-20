# Comparison Query & PII Blocking Fixes

## Issues Fixed

### 1. Comparison Queries Returning Individual Records
**Problem**: Query "compare claim volume for november and october 2025 in kogi state" was returning individual claim records instead of aggregated comparison.

**Solution**: Added fast-path for comparison queries that generates proper UNION ALL queries:

```sql
SELECT 
    'October 2025' as period,
    COUNT(*) as claim_count,
    COALESCE(SUM(c.total_cost), 0) as total_volume
FROM analytics_view_claims c
LEFT JOIN analytics_view_users u ON c.user_id = u.id
LEFT JOIN analytics_view_states s ON u.state = s.id
WHERE DATE(c.created_at) >= '2025-10-01' AND DATE(c.created_at) <= '2025-10-31'
AND s.name = 'Kogi'
UNION ALL
SELECT 
    'November 2025' as period,
    COUNT(*) as claim_count,
    COALESCE(SUM(c.total_cost), 0) as total_volume
FROM analytics_view_claims c
LEFT JOIN analytics_view_users u ON c.user_id = u.id
LEFT JOIN analytics_view_states s ON u.state = s.id
WHERE DATE(c.created_at) >= '2025-11-01' AND DATE(c.created_at) <= '2025-11-30'
AND s.name = 'Kogi'
ORDER BY period
```

**Expected Result**:
```
period           | claim_count | total_volume
-----------------|-------------|-------------
October 2025     | 150         | 2,500,000
November 2025    | 180         | 3,200,000
```

### 2. PII Blocking Error Message
**Problem**: Query "Show me claims for patient John Doe" was returning confusing error: "Generated query is not a SELECT statement"

**Solution**: 
- Fixed privacy blocking to return proper error message before SQL generation
- Updated error handling to check for `sql is None` or `privacy_blocked` flag
- Improved error messages to be user-friendly

**New Error Response**:
```json
{
  "success": false,
  "error": "For privacy compliance, I only provide insights at the cohort level. I cannot identify specific individuals or answer questions about specific patients.",
  "privacy_blocked": true,
  "privacy_warning": "⚠️ Privacy Notice: For privacy compliance, I only provide insights at the cohort level. I cannot identify specific individuals."
}
```

## Changes Made

### 1. Enhanced SQL Generator (`enhanced_sql_generator.py`)
- Added fast-path for comparison queries (month-over-month, year-over-year)
- Supports state filtering (Kogi, Kano, Osun, etc.)
- Updated prompt to include comparison query patterns
- Fixed SQL extraction to handle UNION ALL queries
- Updated validation to allow UNION ALL and WITH (CTE) queries

### 2. Admin Endpoint (`admin.py`)
- Improved error handling for privacy-blocked queries
- Better error messages when PII is detected
- Checks for `sql is None` before processing

## Supported Comparison Queries

The system now properly handles:
- "Compare claim volume for November and October 2025"
- "Compare November and October 2025 in Kogi state"
- "Show me comparison between October and November 2025"
- "Month-over-month comparison for Kano state"

## Testing

Test with:
1. **Comparison Query**: "compare claim volume for november and october 2025 in kogi state"
   - Should return 2 rows (one for each month) with aggregated counts and volumes

2. **PII Query**: "Show me claims for patient John Doe"
   - Should be blocked with clear privacy message
   - Should NOT generate SQL

3. **Top N Query**: "Show me top 10 providers by claim volume this month"
   - Should return aggregated provider summaries

## Next Steps

If comparison queries still return individual records:
1. Check the generated SQL in the `sql_query` field
2. Verify the fast-path is matching (check server logs)
3. The self-correction loop should fix it if the first attempt fails

