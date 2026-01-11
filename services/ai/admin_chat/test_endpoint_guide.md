# Testing the API Endpoint

## Endpoint Details

- **URL**: `POST http://localhost:8001/api/v1/admin/query`
- **Authentication**: Requires `X-API-Key` header or `Bearer` token
- **Content-Type**: `application/json`

## Test Query

```json
{
  "query": "show me the disease with highest number of patients",
  "refine_query": false
}
```

## Authentication

The endpoint requires authentication. You can provide it in one of two ways:

1. **X-API-Key Header**:
   ```bash
   curl -X POST http://localhost:8001/api/v1/admin/query \
     -H "Content-Type: application/json" \
     -H "X-API-Key: YOUR_ADMIN_API_KEY" \
     -d '{"query": "show me the disease with highest number of patients", "refine_query": false}'
   ```

2. **Bearer Token**:
   ```bash
   curl -X POST http://localhost:8001/api/v1/admin/query \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer YOUR_ADMIN_API_KEY" \
     -d '{"query": "show me the disease with highest number of patients", "refine_query": false}'
   ```

## Expected Response

The response will include:

1. **Domain 3.1: Query Intelligence**
   - Intent classification (aggregations)
   - Schema-aware reasoning

2. **Domain 3.2: Safety & Governance**
   - Role permission check
   - Query safety validation
   - PII detection (if any)

3. **Domain 1: Clinical Claims & Diagnosis**
   - Domain routing
   - SQL validation
   - SQL rewriting (if needed)

4. **Domain 3.3: Explainability**
   - SQL explanation
   - User-facing justification

5. **Domain 3.5: Performance**
   - Cost estimation
   - Execution time

6. **Domain 3.6: Metrics**
   - Query metrics recorded

7. **Results**
   - Disease name (not code)
   - Patient count
   - Sanitized output

## Response Structure

```json
{
  "success": true,
  "data": [
    {
      "Diagnosis": "Malaria",
      "Total Claims": 1243
    }
  ],
  "sql": "SELECT d.name AS diagnosis, COUNT(DISTINCT c.id) AS total_claims ...",
  "sql_explanation": "This answer is based on the claims, diagnoses, ...",
  "confidence": 0.80,
  "row_count": 1,
  "source": "vanna",
  "session_id": "...",
  "summary": "...",
  "visualization": {...}
}
```

## Verification Checklist

✅ Query should return:
- Disease **name** (e.g., "Malaria") - NOT code (e.g., "80471")
- Patient count (distinct claims)
- Human-readable output

✅ SQL should:
- Use canonical join path
- Return `diagnoses.name` (not `diagnosis_code`)
- Count `DISTINCT claims.id`
- Group by `d.name` (not `d.id`)

✅ All Domain 3 components should be active:
- Intent classification
- Safety checks
- Explainability
- Performance estimation
- Metrics recording

## Testing with Python

```python
import requests

response = requests.post(
    "http://localhost:8001/api/v1/admin/query",
    json={
        "query": "show me the disease with highest number of patients",
        "refine_query": False
    },
    headers={
        "Content-Type": "application/json",
        "X-API-Key": "YOUR_ADMIN_API_KEY"  # Get from .env file
    }
)

print(response.json())
```

## Getting the API Key

The API key is set in the `.env` file as `ADMIN_API_KEY`. If not set, the server runs in development mode and allows access without authentication.



