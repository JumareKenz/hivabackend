# Provider RAG - Production Deployment Guide

## Pre-Deployment Checklist

### ✅ Safety Layers Implemented

- [x] Response Integrity Layer (`integrity.py`)
- [x] Security Filter (`security.py`)
- [x] RAG Grounding Firewall (`grounding.py`)
- [x] Retry Logic with Validation
- [x] Per-Request Isolation
- [x] Mandatory Citation Enforcement

### ✅ Tests Passed

Run the production validation suite:

```bash
cd /root/hiva/services/ai
python3 -m app.providers_rag.tests.production_validation
```

**Required:** All tests must pass before deployment.

## Deployment Steps

### 1. Verify Configuration

Check `app/providers_rag/config.py`:

```python
require_citations: bool = True  # MUST be True
strict_refusal_mode: bool = True  # MUST be True
enable_citations: bool = True  # MUST be True
```

### 2. Ingest Knowledge Base

```bash
cd /root/hiva/services/ai
python3 -m app.providers_rag.ingestion --clear
```

Verify ingestion:
- Check collection count (should be 288+)
- Verify sections and intents indexed

### 3. Run Production Validation

```bash
python3 -m app.providers_rag.tests.production_validation
```

**DO NOT DEPLOY** if any tests fail.

### 4. Restart Service

```bash
# Stop existing service
pkill -f "uvicorn app.main:app"

# Start with new code
cd /root/hiva/services/ai
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 5. Verify Health

```bash
curl http://localhost:8000/api/v1/providers/health
```

Expected:
```json
{
  "status": "healthy",
  "collection_count": 288,
  "embedding_model_loaded": true,
  "bm25_index_loaded": true
}
```

### 6. Smoke Test

```bash
curl -X POST http://localhost:8000/api/v1/providers/ask \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How do I submit a claim?",
    "session_id": "smoke-test"
  }'
```

Verify:
- Response is complete (ends with punctuation)
- Has citations
- No merged words
- No security leaks

## Monitoring

### Key Metrics to Watch

1. **Response Completeness**
   - All responses end with proper punctuation
   - No truncated sentences
   - Alert if truncation detected

2. **Citation Rate**
   - Should be 100% for non-refusal responses
   - Alert if citations missing

3. **Security Alerts**
   - Monitor for password/credential detection
   - Log all security filter activations

4. **Grounding Score**
   - Average grounding score should be > 0.5
   - Alert if grounding drops

5. **Refusal Rate**
   - Track refusal rate for off-topic queries
   - Should be ~100% for off-topic
   - Should be ~0% for domain queries

### Logging

All safety layer activations are logged:
- `WARNING` - Integrity issues (retries)
- `ERROR` - Security blocks
- `WARNING` - Grounding failures
- `INFO` - Retry attempts

## Rollback Plan

If issues are detected:

1. **Immediate**: Revert to previous code version
2. **Check logs**: Review safety layer activations
3. **Analyze**: Identify which layer failed
4. **Fix**: Address root cause
5. **Re-test**: Run validation suite again

## Success Criteria

System is production-ready when:

- ✅ All production validation tests pass
- ✅ Zero truncated responses in 1000 queries
- ✅ Zero word merging issues
- ✅ Zero context bleeding
- ✅ Zero security leaks
- ✅ 100% citation rate
- ✅ Consistent refusal behavior

## Support

For issues:
1. Check logs: `/var/log/uvicorn.log` or console output
2. Review `ROOT_CAUSE_ANALYSIS.md`
3. Run validation suite to identify failing tests
4. Check health endpoint for system status
