# Quick Start Guide - RAG System

## Prerequisites

- Python 3.11+
- Virtual environment (recommended)
- Documents in PDF, DOCX, TXT, or MD format

## Installation

```bash
# Navigate to the AI service directory
cd /root/hiva/services/ai

# Activate virtual environment (if using one)
source /root/hiva/venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Step 1: Add Documents

Place your FAQ and policy documents in the appropriate folders:

```bash
# Example: Add Adamawa documents
cp your_faq.pdf app/rag/faqs/branches/adamawa/
cp your_policies.docx app/rag/faqs/branches/adamawa/

# Example: Add provider documents
cp provider_guidelines.pdf app/rag/faqs/providers/
```

## Step 2: Ingest Documents

Ingest all knowledge bases at once:

```bash
python3 -m app.state_kb.ingest
```

Or ingest specific knowledge bases:

```bash
# Ingest a single state
python3 -m app.state_kb.ingest adamawa

# Ingest providers
python3 -m app.state_kb.ingest providers

# Clear and re-ingest (if needed)
python3 -m app.state_kb.ingest adamawa --clear
```

Expected output:
```json
{
  "results": [
    {
      "kb_id": "adamawa",
      "status": "ok",
      "count": 45,
      "collection": "kb_adamawa"
    }
  ]
}
```

## Step 3: Start the Server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The server will start on `http://localhost:8000`

## Step 4: Test the API

### Health Check

```bash
curl http://localhost:8000/api/v1/states/adamawa/health
```

Expected response:
```json
{
  "status": "healthy",
  "kb_id": "adamawa",
  "kb_name": "Adamawa State",
  "collection_count": 45,
  "cache_stats": {
    "cache_size": 0,
    "max_cache_size": 256,
    "cache_utilization": 0.0
  }
}
```

### Query the Knowledge Base

```bash
curl -X POST http://localhost:8000/api/v1/states/adamawa/ask \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the enrollment process?",
    "session_id": "test-123",
    "top_k": 5
  }'
```

Expected response:
```json
{
  "answer": "The enrollment process involves...",
  "session_id": "test-123",
  "kb_id": "adamawa",
  "kb_name": "Adamawa State"
}
```

## Step 5: Multi-Turn Conversation

```bash
# First query
curl -X POST http://localhost:8000/api/v1/states/adamawa/ask \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the enrollment process?",
    "session_id": "user-123"
  }'

# Follow-up query (uses conversation history)
curl -X POST http://localhost:8000/api/v1/states/adamawa/ask \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What documents do I need?",
    "session_id": "user-123"
  }'
```

## Available Endpoints

### States

- `POST /api/v1/states/adamawa/ask`
- `POST /api/v1/states/fct/ask`
- `POST /api/v1/states/kano/ask`
- `POST /api/v1/states/zamfara/ask`
- `POST /api/v1/states/kogi/ask`
- `POST /api/v1/states/osun/ask`
- `POST /api/v1/states/rivers/ask`
- `POST /api/v1/states/sokoto/ask`
- `POST /api/v1/states/kaduna/ask`

### Providers

- `POST /api/v1/providers/ask`

### Health Checks

- `GET /api/v1/states/{state_id}/health`
- `GET /api/v1/providers/health`

## Troubleshooting

### No documents retrieved

1. Check if documents are ingested:
   ```bash
   curl http://localhost:8000/api/v1/states/adamawa/health
   ```
   Look for `collection_count > 0`

2. Verify documents are in the correct folder:
   ```bash
   ls -la app/rag/faqs/branches/adamawa/
   ```

3. Re-ingest if needed:
   ```bash
   python3 -m app.state_kb.ingest adamawa --clear
   ```

### Server won't start

1. Check if port 8000 is available:
   ```bash
   lsof -i :8000
   ```

2. Check Python version:
   ```bash
   python3 --version  # Should be 3.11+
   ```

3. Verify dependencies:
   ```bash
   pip list | grep -E "fastapi|chromadb|sentence-transformers"
   ```

### Poor response quality

1. Increase `top_k` parameter (default: 5):
   ```json
   {
     "query": "your question",
     "top_k": 10
   }
   ```

2. Check document quality and structure
3. Try re-ingesting with different chunk sizes

## Next Steps

- Read the [Complete Documentation](RAG_SYSTEM_COMPLETE.md)
- Review the [Architecture](ARCHITECTURE.md)
- Check the [API Documentation](RAG_SYSTEM.md)

## Support

For issues:
1. Check health endpoints
2. Review server logs
3. Verify document ingestion
4. Test with simple queries first

