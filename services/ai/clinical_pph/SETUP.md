# Clinical PPH RAG System - Setup Guide

## Quick Setup Checklist

### ✅ Step 1: Verify Installation

```bash
cd /root/hiva/services/ai
python -c "from clinical_pph import clinical_pph_service; print('✓ Imports working')"
```

### ✅ Step 2: Create Documents Directory

```bash
mkdir -p /root/hiva/services/ai/clinical_pph/docs/faqs
mkdir -p /root/hiva/services/ai/clinical_pph/docs/policies
```

### ✅ Step 3: Add Your Documents

Place your FAQ and policy documents in:
- `clinical_pph/docs/faqs/` - FAQ documents
- `clinical_pph/docs/policies/` - Policy documents

Supported formats: PDF, DOCX, TXT, MD, JSONL

### ✅ Step 4: Ingest Documents

```bash
cd /root/hiva/services/ai
python -m clinical_pph.ingest
```

Expected output:
```json
{
  "kb_id": "clinical_pph",
  "status": "ok",
  "count": 150,
  "files_processed": 5,
  "collection": "clinical_pph_collection"
}
```

### ✅ Step 5: Verify Health

```bash
curl http://localhost:8000/api/v1/clinical-pph/health
```

Expected response:
```json
{
  "status": "healthy",
  "kb_id": "clinical_pph",
  "kb_name": "Clinical PPH (Postpartum Hemorrhage)",
  "collection_count": 150,
  "cache_stats": {
    "cache_size": 0,
    "max_cache_size": 256,
    "cache_utilization": 0.0
  }
}
```

### ✅ Step 6: Test Query

```bash
curl -X POST http://localhost:8000/api/v1/clinical-pph/ask \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is postpartum hemorrhage?",
    "session_id": "test-123"
  }'
```

## Troubleshooting

### Import Errors

If you see `ModuleNotFoundError`:
```bash
# Ensure you're in the correct directory
cd /root/hiva/services/ai

# Verify Python can find the module
python -c "import sys; sys.path.insert(0, '.'); from clinical_pph import clinical_pph_service"
```

### Empty Collection

If `collection_count` is 0:
1. Verify documents exist in `clinical_pph/docs/`
2. Re-run ingestion: `python -m clinical_pph.ingest --clear`
3. Check ingestion logs for errors

### API Not Available

If endpoints return 404:
1. Verify router is registered in `app/main.py`
2. Restart the FastAPI server
3. Check server logs for startup errors

## Next Steps

1. **Add More Documents**: Place additional documents in `docs/` and re-ingest
2. **Test Queries**: Try various question types to verify retrieval quality
3. **Monitor Performance**: Check cache stats and response times
4. **Optimize**: Adjust `top_k`, chunk size, or embedding model as needed

## Support

For detailed documentation, see:
- [README.md](README.md) - Complete system documentation
- [../CLINICAL_PPH_RAG.md](../CLINICAL_PPH_RAG.md) - Implementation guide


