# HIVA RAG System - Complete Documentation

## Overview

This is a comprehensive, production-ready Retrieval-Augmented Generation (RAG) system designed for nine Nigerian states and a general providers knowledge base. Each knowledge domain is isolated with its own vector store, endpoints, and document management.

## Architecture

### System Components

1. **Document Ingestion Pipeline** (`app/state_kb/ingest.py`)
   - Processes PDF, DOCX, TXT, and MD files
   - Chunks documents intelligently with overlap
   - Generates embeddings using SentenceTransformers
   - Stores in isolated ChromaDB collections

2. **Vector Store** (`app/state_kb/store.py`)
   - ChromaDB for persistent vector storage
   - One collection per knowledge base
   - Collection naming: `kb_{kb_id}` (e.g., `kb_adamawa`)

3. **Retrieval System** (`app/state_kb/retriever.py`)
   - Semantic search using cosine similarity
   - Relevance scoring
   - Metadata filtering

4. **Service Layer** (`app/state_kb/service.py`)
   - Async retrieval with caching
   - LRU cache for performance
   - Error handling and logging

5. **API Layer** (`app/api/v1/kb_factory.py`)
   - RESTful endpoints per knowledge base
   - Conversation management
   - Health checks

6. **Conversation Manager** (`app/services/conversation_manager.py`)
   - Multi-turn dialogue tracking
   - Context-aware responses
   - Session management

## Knowledge Bases

### States (9)

1. **Adamawa** (`adamawa`) - ASCHMA
2. **FCT** (`fct`) - FHIS
3. **Kano** (`kano`) - KSCHMA
4. **Zamfara** (`zamfara`) - ZAMCHEMA
5. **Kogi** (`kogi`) - KGSHIA
6. **Osun** (`osun`) - OSHIA
7. **Rivers** (`rivers`) - RIVCHPP
8. **Sokoto** (`sokoto`) - SOHEMA
9. **Kaduna** (`kaduna`) - KADCHMA

### Providers

- **General Providers** (`providers`) - General provider information

## Folder Structure

```
app/
├── rag/
│   ├── faqs/
│   │   ├── branches/
│   │   │   ├── adamawa/
│   │   │   ├── fct/
│   │   │   ├── kano/
│   │   │   ├── zamfara/
│   │   │   ├── kogi/
│   │   │   ├── osun/
│   │   │   ├── rivers/
│   │   │   ├── sokoto/
│   │   │   └── kaduna/
│   │   └── providers/
│   ├── utils.py          # Document processing utilities
│   └── db/               # ChromaDB storage (branch FAQs)
│
├── state_kb/
│   ├── db/               # ChromaDB storage (state/provider KBs)
│   ├── registry.py       # KB definitions
│   ├── store.py          # Vector store management
│   ├── retriever.py      # Document retrieval
│   ├── service.py        # Async service layer
│   └── ingest.py         # Document ingestion
│
└── api/
    └── v1/
        ├── states/
        │   ├── adamawa.py
        │   ├── fct.py
        │   ├── kano.py
        │   ├── zamfara.py
        │   ├── kogi.py
        │   ├── osun.py
        │   ├── rivers.py
        │   ├── sokoto.py
        │   └── kaduna.py
        ├── providers/
        │   └── kb.py
        └── kb_factory.py  # Router factory
```

## Setup

### 1. Install Dependencies

```bash
cd /root/hiva/services/ai
python3 -m pip install -r requirements.txt
```

### 2. Prepare Documents

Place your FAQ and policy documents in the appropriate folders:

```bash
# Example: Add Adamawa documents
cp your_documents.pdf app/rag/faqs/branches/adamawa/
cp your_faqs.docx app/rag/faqs/branches/adamawa/

# Example: Add provider documents
cp provider_guidelines.pdf app/rag/faqs/providers/
```

### 3. Ingest Documents

Ingest all knowledge bases:

```bash
python3 -m app.state_kb.ingest
```

Or ingest a specific knowledge base:

```bash
# Ingest Adamawa
python3 -m app.state_kb.ingest adamawa

# Ingest Providers
python3 -m app.state_kb.ingest providers

# Clear and re-ingest
python3 -m app.state_kb.ingest adamawa --clear
```

### 4. Start the Server

```bash
cd /root/hiva/services/ai
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## API Endpoints

### State Endpoints

Each state has three endpoints:

#### POST `/api/v1/states/{state_id}/ask`

Query the knowledge base.

**Request:**
```json
{
  "query": "What is the enrollment process?",
  "session_id": "optional-session-id",
  "top_k": 5
}
```

**Response:**
```json
{
  "answer": "The enrollment process involves...",
  "session_id": "session-id",
  "kb_id": "adamawa",
  "kb_name": "Adamawa State"
}
```

#### POST `/api/v1/states/{state_id}/stream`

Streaming endpoint (currently returns JSON, same as `/ask`).

#### GET `/api/v1/states/{state_id}/health`

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "kb_id": "adamawa",
  "kb_name": "Adamawa State",
  "collection_count": 150,
  "cache_stats": {
    "cache_size": 45,
    "max_cache_size": 256,
    "cache_utilization": 0.18
  }
}
```

### Provider Endpoint

#### POST `/api/v1/providers/ask`

Same structure as state endpoints.

#### POST `/api/v1/providers/stream`

Streaming endpoint.

#### GET `/api/v1/providers/health`

Health check.

## Usage Examples

### Python

```python
import httpx

# Query Adamawa knowledge base
response = httpx.post(
    "http://localhost:8000/api/v1/states/adamawa/ask",
    json={
        "query": "What are the enrollment requirements?",
        "session_id": "user-123",
        "top_k": 5
    }
)
data = response.json()
print(data["answer"])
```

### cURL

```bash
# Query Kano knowledge base
curl -X POST http://localhost:8000/api/v1/states/kano/ask \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How do I enroll?",
    "session_id": "session-123",
    "top_k": 5
  }'

# Health check
curl http://localhost:8000/api/v1/states/kano/health
```

### JavaScript/TypeScript

```javascript
// Query providers knowledge base
const response = await fetch('http://localhost:8000/api/v1/providers/ask', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    query: 'What are the provider requirements?',
    session_id: 'user-123',
    top_k: 5
  })
});

const data = await response.json();
console.log(data.answer);
```

## Conversation Management

The system maintains conversation context across multiple turns:

```python
# First query
response1 = httpx.post(
    "http://localhost:8000/api/v1/states/adamawa/ask",
    json={
        "query": "What is the enrollment process?",
        "session_id": "user-123"
    }
)

# Follow-up query (uses conversation history)
response2 = httpx.post(
    "http://localhost:8000/api/v1/states/adamawa/ask",
    json={
        "query": "What documents do I need?",
        "session_id": "user-123"  # Same session_id
    }
)
```

## Configuration

### Environment Variables

Create a `.env` file in `/root/hiva/services/ai/`:

```env
# LLM Configuration
LLM_API_URL=http://localhost:11434
LLM_MODEL=llama3:latest
LLM_TIMEOUT_SECONDS=120
TEMPERATURE=0.2

# Embedding Configuration
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5

# RAG Configuration
RAG_CHUNK_SIZE=900
RAG_CHUNK_OVERLAP=120
RAG_DEFAULT_TOP_K=5
```

### Supported Embedding Models

- `BAAI/bge-small-en-v1.5` (default) - Fast, good quality
- `BAAI/bge-base-en-v1.5` - Better quality, slower
- `sentence-transformers/all-MiniLM-L6-v2` - Very fast, smaller
- `sentence-transformers/all-mpnet-base-v2` - High quality, slower

## Document Processing

### Supported Formats

- **PDF** (`.pdf`) - Extracted using `pdfplumber`
- **Word Documents** (`.docx`) - Extracted using `python-docx`
- **Text Files** (`.txt`) - Plain text
- **Markdown** (`.md`) - Markdown formatted

### Chunking Strategy

Documents are chunked intelligently:
1. First split by paragraphs (double newlines)
2. If chunks are too large, split by sentences
3. If still too large, split by words
4. Overlap between chunks for context preservation

Default settings:
- Chunk size: 900 characters
- Overlap: 120 characters

## Performance Optimization

### Caching

The system uses an LRU cache for frequently accessed queries:
- Default cache size: 256 entries
- Cache key: MD5 hash of `kb_id:query:top_k`
- Automatic eviction when cache is full

### Async Operations

All retrieval operations are async to avoid blocking:
- Document retrieval runs in executor
- LLM calls are async
- Concurrent request handling

## Monitoring and Debugging

### Logging

The system uses Python's logging module. Set log level:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Health Checks

Monitor knowledge base health:

```bash
# Check all knowledge bases
for state in adamawa fct kano zamfara kogi osun rivers sokoto kaduna; do
  echo "Checking $state..."
  curl http://localhost:8000/api/v1/states/$state/health
done

# Check providers
curl http://localhost:8000/api/v1/providers/health
```

## Troubleshooting

### No Documents Retrieved

1. Check if documents are ingested:
   ```bash
   python3 -m app.state_kb.ingest <kb_id>
   ```

2. Verify documents are in the correct folder:
   ```bash
   ls -la app/rag/faqs/branches/<state_id>/
   ```

3. Check collection count:
   ```bash
   curl http://localhost:8000/api/v1/states/<state_id>/health
   ```

### Poor Retrieval Quality

1. Increase `top_k` parameter (default: 5)
2. Try a different embedding model
3. Adjust chunk size and overlap
4. Improve document quality and structure

### Slow Performance

1. Use a faster embedding model
2. Reduce `top_k` parameter
3. Enable caching (default: enabled)
4. Check system resources

## Best Practices

1. **Document Organization**: Keep related documents together in state folders
2. **Naming Conventions**: Use descriptive filenames
3. **Regular Updates**: Re-ingest when documents change
4. **Session Management**: Use consistent `session_id` for multi-turn conversations
5. **Error Handling**: Always check response status codes
6. **Monitoring**: Regularly check health endpoints

## Future Enhancements

- [ ] True SSE streaming for token-by-token responses
- [ ] Support for additional vector stores (Pinecone, Weaviate)
- [ ] Advanced reranking for better relevance
- [ ] Multi-modal support (images, tables)
- [ ] Query expansion and reformulation
- [ ] Analytics and usage tracking
- [ ] Fine-tuning embedding models on domain data

## Support

For issues or questions:
1. Check the health endpoints
2. Review logs for error messages
3. Verify document ingestion
4. Test with simple queries first

## License

[Your License Here]

