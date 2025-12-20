# Timeout Issue Fix

## Problem
Queries like "Show me claims by status" were timing out after 30 seconds.

## Root Cause
The RunPod GPU endpoint can be slow when processing large schema prompts (81 tables). Even with optimizations, complex queries can take 30-90+ seconds.

## Solutions Implemented

### 1. Fast Path for Simple Queries
- For queries like "claims by status", only the `claims` table schema is sent to the LLM
- Reduces prompt size by ~95%, dramatically speeding up generation

### 2. Reduced Token Limit
- Capped `max_tokens` at 500 (down from 2000) for faster generation
- SQL queries are typically short, so this doesn't affect quality

### 3. Schema Optimization
- Reduced default schema from 50 tables to 20-30 tables
- Prioritizes relevant tables based on query content

### 4. Better Error Messages
- More helpful timeout error messages
- Suggests simplifying queries or retrying

## Recommendations

### For Users
1. **Keep queries simple**: "claims by status" works better than long descriptions
2. **Be specific**: Mention the table name in your query
3. **Retry if timeout**: The RunPod pod may be temporarily slow
4. **Break complex queries**: Split into smaller parts

### For Developers
1. **Monitor RunPod performance**: Check pod status if timeouts persist
2. **Consider caching**: Cache common queries to avoid LLM calls
3. **Add query templates**: Pre-defined queries for common patterns
4. **Increase frontend timeout**: If backend is working but slow, increase frontend timeout from 30s to 60s+

## Testing
Test with:
```bash
curl -X POST http://localhost:8001/api/v1/admin/query \
  -H "X-API-Key: YOUR_KEY" \
  -d '{"query": "Show me claims by status"}'
```

Expected: Response in < 10 seconds with fast path optimization.




