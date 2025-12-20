# SQL Extraction Fix - Comprehensive Error Handling

## Problem
Queries failing with: "Generated query is not a SELECT statement"

## Root Cause
LLM sometimes returns responses that:
1. Don't start with SELECT
2. Have SELECT buried in the middle
3. Include markdown or explanations
4. Have formatting issues

## Solution Applied

### 1. Enhanced SQL Extraction (`_extract_sql_from_response`)
**Multiple Extraction Strategies**:
- Strategy 1: Find SELECT anywhere in response and extract from there
- Strategy 2: Reconstruct SELECT if FROM exists but SELECT is missing
- Strategy 3: Look for SQL keywords (COUNT, SUM, GROUP BY) and extract SQL
- Strategy 4: Aggressive regex extraction for complete SQL statements

### 2. Debug Logging Added
- Logs raw LLM response (first 500 chars)
- Logs extracted SQL (first 200 chars)
- Logs full response on extraction failure
- Helps identify what LLM is actually returning

### 3. Better Error Messages
- Error messages now include LLM response preview
- Makes debugging easier

## Code Changes

### Enhanced Extraction Logic
```python
# Multiple fallback strategies
if not (is_select or has_union):
    # Strategy 1: Find SELECT anywhere
    # Strategy 2: Reconstruct SELECT
    # Strategy 3: Extract using SQL keywords
    # Strategy 4: Aggressive regex
```

### Debug Logging
```python
print(f"[DEBUG] LLM raw response: {response[:500]}")
print(f"[DEBUG] Extracted SQL: {sql[:200]}")
print(f"[ERROR] SQL extraction failed: {e}")
```

## Testing

When you run queries, check the logs for:
- `[DEBUG] LLM raw response` - What LLM actually returned
- `[DEBUG] Extracted SQL` - What was extracted
- `[ERROR] SQL extraction failed` - If extraction fails

## Next Steps

1. Test queries and check logs
2. If extraction still fails, logs will show what LLM returned
3. Adjust extraction logic based on actual LLM responses

## Status

✅ **Enhanced extraction logic applied**
✅ **Debug logging added**
✅ **Better error messages**

The system should now handle edge cases better and provide debugging information when extraction fails.


