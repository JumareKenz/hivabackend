# RAG System Architecture

## System Overview

The HIVA RAG system is a modular, scalable architecture designed to handle multiple isolated knowledge bases. Each knowledge base (state or provider) operates independently with its own vector store, endpoints, and document management.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        Client Layer                          │
│  (Web App, Mobile App, API Consumers)                        │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                      API Layer (FastAPI)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ /states/     │  │ /states/     │  │ /providers/  │      │
│  │ adamawa/ask  │  │ kano/ask     │  │ ask          │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│         │                 │                   │              │
│         └─────────────────┴───────────────────┘              │
│                            │                                 │
│                   ┌────────▼────────┐                        │
│                   │  KB Factory    │                        │
│                   │  (Router Gen)   │                        │
│                   └────────┬────────┘                        │
└────────────────────────────┼─────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                   Service Layer                              │
│  ┌──────────────────┐  ┌──────────────────┐               │
│  │ StateKBService   │  │ ConversationMgr  │               │
│  │ (Async + Cache)  │  │ (Multi-turn)     │               │
│  └────────┬─────────┘  └────────┬─────────┘               │
│           │                      │                          │
│           └──────────┬───────────┘                          │
│                      │                                       │
│              ┌───────▼────────┐                             │
│              │  Retriever     │                             │
│              │  (Vector Search)│                             │
│              └───────┬────────┘                             │
└──────────────────────┼──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                  Vector Store Layer                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ kb_adamawa   │  │ kb_kano      │  │ kb_providers │      │
│  │ (ChromaDB)   │  │ (ChromaDB)   │  │ (ChromaDB)   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              Document Processing Layer                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ PDF Extract  │  │ DOCX Extract │  │ Text Extract │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│           │                │                 │               │
│           └────────────────┴─────────────────┘               │
│                            │                                 │
│                   ┌─────────▼─────────┐                       │
│                   │  Text Chunking   │                       │
│                   │  (Smart Split)   │                       │
│                   └─────────┬─────────┘                       │
│                             │                                 │
│                   ┌─────────▼─────────┐                       │
│                   │  Embedding Model  │                       │
│                   │  (SentenceTrans)  │                       │
│                   └───────────────────┘                       │
└─────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. API Layer

**Location**: `app/api/v1/`

**Components**:
- `kb_factory.py`: Factory pattern for creating routers
- `states/{state_id}.py`: State-specific routers
- `providers/kb.py`: Provider router

**Responsibilities**:
- Request validation
- Response formatting
- Error handling
- Session management

### 2. Service Layer

**Location**: `app/state_kb/service.py`

**Features**:
- Async retrieval
- LRU caching (256 entries)
- Error handling
- Logging

**Cache Strategy**:
- Key: MD5(`kb_id:query:top_k`)
- Eviction: LRU when cache is full
- TTL: None (manual clear or restart)

### 3. Retrieval Layer

**Location**: `app/state_kb/retriever.py`

**Process**:
1. Validate query
2. Get collection for KB
3. Generate query embedding
4. Vector search (cosine similarity)
5. Format results with metadata

**Features**:
- Relevance scoring
- Metadata filtering
- Empty collection detection

### 4. Vector Store

**Location**: `app/state_kb/store.py`

**Technology**: ChromaDB (persistent)

**Structure**:
- One collection per KB
- Collection name: `kb_{kb_id}`
- Storage: `app/state_kb/db/`

**Metadata**:
- `kb_id`: Knowledge base identifier
- `source_path`: Original file path
- `chunk_index`: Chunk position in document
- `doc_type`: Document type

### 5. Document Processing

**Location**: `app/rag/utils.py`

**Supported Formats**:
- PDF: `pdfplumber`
- DOCX: `python-docx`
- TXT: Direct read
- MD: Direct read

**Chunking Strategy**:
1. Split by paragraphs (preferred)
2. Split by sentences (fallback)
3. Split by words (fallback)
4. Character split (last resort)

**Parameters**:
- Chunk size: 900 characters
- Overlap: 120 characters

### 6. Embedding Model

**Default**: `BAAI/bge-small-en-v1.5`

**Characteristics**:
- Fast inference
- Good quality
- 384 dimensions
- English optimized

**Alternatives**:
- `BAAI/bge-base-en-v1.5`: Better quality, slower
- `all-MiniLM-L6-v2`: Very fast, smaller
- `all-mpnet-base-v2`: High quality, slower

### 7. Conversation Manager

**Location**: `app/services/conversation_manager.py`

**Features**:
- Multi-turn dialogue tracking
- Context-aware responses
- Session management
- TTL-based cleanup (24 hours)

**Storage**:
- In-memory (per-process)
- Session-based
- Max history: 10 messages

## Data Flow

### Query Flow

```
1. Client Request
   ↓
2. API Router (kb_factory)
   ↓
3. StateKBService.retrieve_async()
   ├─ Check cache
   ├─ If miss: Retriever.retrieve()
   │   ├─ Get collection
   │   ├─ Generate embedding
   │   ├─ Vector search
   │   └─ Format results
   └─ Update cache
   ↓
4. ConversationManager.get_context_for_llm()
   ├─ Get conversation history
   ├─ Get KB context
   └─ Build context string
   ↓
5. LLM Client (Ollama)
   ├─ Format messages
   ├─ Add context
   └─ Generate response
   ↓
6. ConversationManager.add_message()
   ↓
7. Return response to client
```

### Ingestion Flow

```
1. Document Files (PDF/DOCX/TXT/MD)
   ↓
2. Extract Text (utils.py)
   ├─ PDF: pdfplumber
   ├─ DOCX: python-docx
   └─ TXT/MD: Direct read
   ↓
3. Chunk Text (utils.py)
   ├─ Split by paragraphs
   ├─ Handle overlaps
   └─ Generate chunks
   ↓
4. Generate Embeddings (SentenceTransformer)
   ├─ Encode chunks
   └─ Batch processing
   ↓
5. Store in ChromaDB
   ├─ Create collection (if needed)
   ├─ Add documents
   ├─ Add embeddings
   └─ Add metadata
```

## Isolation Strategy

### Knowledge Base Isolation

Each KB is completely isolated:

1. **Separate Collections**: Each KB has its own ChromaDB collection
2. **Separate Endpoints**: Each KB has its own API routes
3. **Separate Folders**: Documents stored in separate directories
4. **Separate Context**: Conversation context is KB-specific

### Benefits

- **Scalability**: Add new KBs without affecting others
- **Performance**: Independent caching and retrieval
- **Maintenance**: Update one KB without impacting others
- **Security**: Isolated access control (future)

## Performance Considerations

### Caching

- **Query Cache**: LRU cache for frequent queries
- **Model Cache**: Singleton embedding model
- **Collection Cache**: ChromaDB client singleton

### Async Operations

- **Retrieval**: Runs in executor (non-blocking)
- **LLM Calls**: Fully async
- **I/O Operations**: Async file operations

### Optimization Tips

1. Use faster embedding models for development
2. Adjust `top_k` based on use case
3. Enable caching for production
4. Batch document ingestion
5. Monitor cache hit rates

## Scalability

### Horizontal Scaling

- Stateless API layer (can run multiple instances)
- Shared vector store (ChromaDB can be externalized)
- Load balancer for API instances

### Vertical Scaling

- Increase cache size
- Use faster embedding models
- Increase `top_k` for better recall
- Optimize chunk sizes

### Future Enhancements

- Distributed vector store (Pinecone, Weaviate)
- Redis for shared caching
- Database for conversation persistence
- CDN for static document serving

## Security Considerations

### Current Implementation

- Input validation on API layer
- Error message sanitization
- Session-based isolation

### Future Enhancements

- Authentication/Authorization
- Rate limiting
- Input sanitization
- Audit logging
- Encryption at rest

## Monitoring and Observability

### Logging

- Structured logging with levels
- Error tracking with stack traces
- Performance metrics

### Health Checks

- Collection count verification
- Cache statistics
- Service availability

### Metrics (Future)

- Query latency
- Cache hit rate
- Error rate
- Document count per KB

## Testing Strategy

### Unit Tests

- Document processing functions
- Chunking logic
- Cache operations

### Integration Tests

- End-to-end query flow
- Conversation management
- Vector store operations

### Load Tests

- Concurrent request handling
- Cache performance
- Memory usage

## Deployment

### Development

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Production

```bash
# Use gunicorn with uvicorn workers
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

### Docker

```dockerfile
FROM python:3.11
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Maintenance

### Regular Tasks

1. **Document Updates**: Re-ingest when documents change
2. **Cache Clearing**: Clear cache if needed
3. **Health Monitoring**: Regular health checks
4. **Log Review**: Monitor error logs
5. **Performance Tuning**: Adjust parameters based on usage

### Backup Strategy

- ChromaDB data: `app/state_kb/db/`
- Document files: `app/rag/faqs/`
- Configuration: `.env` files

## Future Architecture Enhancements

1. **Multi-Modal Support**: Images, tables, charts
2. **Advanced Reranking**: Cross-encoder reranking
3. **Query Expansion**: Automatic query enhancement
4. **Hybrid Search**: Keyword + semantic search
5. **Fine-Tuning**: Domain-specific embeddings
6. **Analytics**: Usage tracking and insights

