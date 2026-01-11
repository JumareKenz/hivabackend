# CURL Test Results: Highest Disease with Number of Patients

## Test Details

**Query**: `show me which disease has the highest number of patients`  
**Endpoint**: `http://localhost:8001/api/v1/admin/query`  
**Method**: `POST`

## CURL Command

```bash
curl -X POST "http://localhost:8001/api/v1/admin/query" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: e11b645954810073cf458b1502073ca407f64748291ee2a10f7f1007ce56fe1e" \
  -d '{
    "query": "show me which disease has the highest number of patients",
    "refine_query": false
  }' \
  --max-time 120
```

## Response

```json
{
  "success": false,
  "error": "This query requires clarification to ensure accurate clinical claims analysis interpretation. The query involves more relationships than expected. Please specify exactly what you want to analyze.",
  "sql": "SELECT d.name AS disease, COUNT(DISTINCT DISTINCT c.id) AS patient_count FROM claims c JOIN service_summaries ss ON ss.claim_id = c.id JOIN service_summary_diagnosis ssd ON ssd.service_summary_id = ss.id JOIN diagnoses d ON d.id = ssd.diagnosis_id JOIN users u ON c.user_id = u.id JOIN states s ON u.state = s.id WHERE s.name LIKE '%StateName%' GROUP BY d.name ORDER BY patient_count DESC LIMIT 1",
  "confidence": 0.6,
  "row_count": 0
}
```

## Issues Identified

### 1. SQL Generation Issues
- ❌ **Duplicate DISTINCT**: `COUNT(DISTINCT DISTINCT c.id)` - SQL syntax error
- ❌ **Unnecessary state filter**: `WHERE s.name LIKE '%StateName%'` - placeholder text, not needed for this query
- ❌ **Extra joins**: Includes `users` and `states` tables when not needed for a simple "highest disease" query

### 2. Confidence Scorer
- ⚠️ **Blocked query**: Confidence score of 0.6 triggered the clarification request
- ⚠️ **Reason**: "The query involves more relationships than expected"

## Expected SQL (Correct)

```sql
SELECT 
    d.name AS disease,
    COUNT(DISTINCT c.id) AS patient_count
FROM claims c
JOIN service_summaries ss ON ss.claim_id = c.id
JOIN service_summary_diagnosis ssd ON ssd.service_summary_id = ss.id
JOIN diagnoses d ON d.id = ssd.diagnosis_id
GROUP BY d.name
ORDER BY patient_count DESC
LIMIT 1
```

## Recommendations

1. **Fix SQL Rewriter**: Add rule to remove duplicate DISTINCT keywords
2. **Improve Prompt**: Update LLM prompt to not include state filters when not mentioned in query
3. **Adjust Confidence Scorer**: Lower threshold or improve logic for disease aggregation queries
4. **Fix Fast-Path Logic**: Ensure disease queries skip fast-path and go to LLM

## Status

- ✅ Endpoint is responding
- ✅ SQL generation is working (but has issues)
- ❌ Query is being blocked by confidence scorer
- ❌ Generated SQL has syntax errors


