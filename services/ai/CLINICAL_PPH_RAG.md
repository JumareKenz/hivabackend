# Clinical PPH RAG System - Implementation Guide

## Overview

The Clinical PPH (Postpartum Hemorrhage) RAG system is a dedicated, isolated knowledge base for clinical PPH information. It follows the same architectural patterns as the state/provider KB system but is specifically tailored for clinical documentation.

## Quick Start

### 1. Add Documents

Place your FAQ and policy documents in:
```
/root/hiva/services/ai/clinical_pph/docs/
```

Supported formats: PDF, DOCX, TXT, MD, JSONL

### 2. Ingest Documents

```bash
cd /root/hiva/services/ai
python -m clinical_pph.ingest
```

### 3. Query the API

```bash
curl -X POST http://localhost:8000/api/v1/clinical-pph/ask \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the symptoms of postpartum hemorrhage?",
    "session_id": "test-123"
  }'
```

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────┐
│                    API Layer                             │
│  /api/v1/clinical-pph/ask                               │
│  /api/v1/clinical-pph/stream                            │
│  /api/v1/clinical-pph/health                            │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────┐
│              ClinicalPPHService                          │
│  - Async retrieval                                        │
│  - LRU caching                                           │
│  - Error handling                                         │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────┐
│                 Retriever                                │
│  - Query embedding                                       │
│  - Vector search                                         │
│  - Document formatting                                   │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────┐
│              ChromaDB Store                              │
│  - Persistent vector storage                             │
│  - Isolated collection                                   │
│  - Metadata management                                   │
└──────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Document Ingestion**:
   - Documents → Text Extraction → Chunking → Embedding → ChromaDB

2. **Query Processing**:
   - User Query → Embedding → Vector Search → Context Retrieval → LLM → Response

3. **Conversation Management**:
   - Session ID → Conversation History → Context Building → Multi-turn Support

## Key Features

### 1. Isolated Knowledge Base

- Separate ChromaDB collection (`clinical_pph_collection`)
- Independent from other KBs (states, providers)
- Dedicated storage directory (`clinical_pph/db/`)

### 2. Multi-format Support

- **PDF**: Extracted with pdfplumber, OCR fallback
- **DOCX**: Extracted with python-docx
- **TXT/MD**: Direct text reading
- **JSONL**: Structured Q&A pairs

### 3. Intelligent Chunking

- Paragraph-aware splitting
- Sentence boundary preservation
- Configurable overlap for context continuity

### 4. Caching

- LRU cache for frequently accessed queries
- Configurable cache size (default: 256)
- Automatic eviction when full

### 5. Conversation Context

- Multi-turn dialogue support
- Session-based history tracking
- Context-aware query reformulation

## API Reference

### POST /api/v1/clinical-pph/ask

Query the knowledge base.

**Request:**
```json
{
  "query": "string (required)",
  "session_id": "string (optional)",
  "top_k": 5
}
```

**Response:**
```json
{
  "answer": "string",
  "session_id": "string",
  "kb_id": "clinical_pph",
  "kb_name": "Clinical PPH (Postpartum Hemorrhage)"
}
```

### GET /api/v1/clinical-pph/health

Health check endpoint.

**Response:**
```json
{
  "status": "healthy|unhealthy",
  "kb_id": "clinical_pph",
  "kb_name": "Clinical PPH (Postpartum Hemorrhage)",
  "collection_count": 150,
  "cache_stats": {
    "cache_size": 45,
    "max_cache_size": 256,
    "cache_utilization": 0.176
  }
}
```

## Integration with Conversation Manager

The system integrates with the global conversation manager:

```python
from app.services.conversation_manager import conversation_manager

# Set KB context
conversation_manager.set_kb_context(
    "clinical_pph",
    {
        "name": "Clinical PPH (Postpartum Hemorrhage)",
        "kb_id": "clinical_pph",
        "domain": "clinical",
        "topic": "postpartum_hemorrhage"
    }
)

# Get context for LLM
context = conversation_manager.get_context_for_llm(
    session_id=session_id,
    kb_id="clinical_pph",
    rag_context=retrieved_docs,
    current_query=user_query
)
```

## Configuration

### Embedding Model

Default: `BAAI/bge-small-en-v1.5`

To change, edit `app/core/config.py`:
```python
EMBEDDING_MODEL: str = "sentence-transformers/all-mpnet-base-v2"
```

### Chunking Parameters

Default:
- Chunk size: 900 characters
- Overlap: 120 characters

To change:
```python
RAG_CHUNK_SIZE: int = 1000
RAG_CHUNK_OVERLAP: int = 150
```

## Best Practices

### Document Organization

```
clinical_pph/docs/
├── faqs/
│   ├── general_faqs.pdf
│   └── treatment_faqs.docx
├── policies/
│   ├── pph_protocol.pdf
│   └── guidelines.docx
└── structured/
    └── qa_pairs.jsonl
```

### Query Optimization

1. **Be Specific**: "What are the risk factors for PPH?" vs "Tell me about PPH"
2. **Use Medical Terms**: Use proper clinical terminology
3. **Context Matters**: Use session_id for follow-up questions

### Ingestion Workflow

1. **Add Documents**: Place in `docs/` directory
2. **Test Extraction**: Verify text extraction works
3. **Ingest**: Run `python -m clinical_pph.ingest`
4. **Verify**: Check health endpoint
5. **Test Queries**: Try sample queries

## Troubleshooting

### Common Issues

1. **Empty Collection**
   - Run: `python -m clinical_pph.ingest`
   - Check: Documents exist in `docs/` directory

2. **Import Errors**
   - Ensure: Running from `/root/hiva/services/ai`
   - Check: Python path includes project root

3. **Low Retrieval Quality**
   - Increase: `top_k` parameter
   - Review: Document chunking strategy
   - Consider: Larger embedding model

4. **Memory Issues**
   - Reduce: Cache size in `service.py`
   - Optimize: Chunk size and overlap

## Performance Considerations

### Caching

- Default cache size: 256 queries
- LRU eviction policy
- Cache hit rate typically 30-50% for repeated queries

### Embedding Generation

- First query: ~2-3 seconds (model loading)
- Subsequent queries: ~100-300ms
- Batch ingestion: Progress bar shows status

### Vector Search

- ChromaDB query time: ~50-200ms
- Scales well up to ~10,000 documents
- Consider indexing for larger collections

## Future Enhancements

Potential improvements:

1. **Hybrid Search**: Combine vector and keyword search
2. **Re-ranking**: Use cross-encoder for better relevance
3. **Streaming**: True SSE support for token streaming
4. **Analytics**: Query logging and analytics
5. **Multi-language**: Support for multiple languages

## Support

For issues or questions:
1. Check health endpoint
2. Review logs in application output
3. Verify document ingestion completed
4. Test with sample queries

---

**System Version**: 1.0.0
**Last Updated**: 2024


