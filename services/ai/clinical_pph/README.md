# Clinical PPH RAG System

A comprehensive Retrieval-Augmented Generation (RAG) system specifically designed for Clinical Postpartum Hemorrhage (PPH) knowledge base. This system provides isolated, efficient access to FAQ and policy documents through a dedicated RESTful API.

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Folder Structure](#folder-structure)
- [Setup & Installation](#setup--installation)
- [Document Ingestion](#document-ingestion)
- [API Endpoints](#api-endpoints)
- [Usage Examples](#usage-examples)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)

## 🎯 Overview

The Clinical PPH RAG system is a modular, scalable solution that:

- **Isolates Clinical PPH knowledge** in its own dedicated vector database
- **Supports multiple document formats** (PDF, DOCX, TXT, MD, JSONL)
- **Provides semantic search** using state-of-the-art embeddings
- **Manages conversational context** for multi-turn dialogues
- **Offers RESTful API endpoints** for easy integration

## 🏗️ Architecture

### Core Components

1. **Vector Store** (`store.py`)
   - ChromaDB persistent storage
   - Isolated collection for Clinical PPH documents
   - Automatic collection management

2. **Document Retriever** (`retriever.py`)
   - Semantic search using sentence transformers
   - Query embedding generation
   - Relevance-based document retrieval

3. **Async Service** (`service.py`)
   - LRU caching for improved performance
   - Async/await support for non-blocking operations
   - Error handling and logging

4. **Document Ingestion** (`ingest.py`)
   - Multi-format document parsing
   - Intelligent text chunking
   - Embedding generation and storage

5. **API Router** (`app/api/v1/clinical_pph/router.py`)
   - RESTful endpoints
   - Conversation context management
   - LLM integration

### Technology Stack

- **Vector Database**: ChromaDB (persistent, local storage)
- **Embeddings**: SentenceTransformers (BAAI/bge-small-en-v1.5)
- **API Framework**: FastAPI
- **LLM Integration**: Groq API (via Ollama client)
- **Document Processing**: pdfplumber, python-docx

## 📁 Folder Structure

```
clinical_pph/
├── __init__.py              # Module exports
├── store.py                  # ChromaDB vector store management
├── retriever.py              # Semantic search and retrieval
├── service.py                # Async service with caching
├── ingest.py                 # Document ingestion pipeline
├── README.md                 # This file
├── docs/                     # Place FAQ and policy documents here
│   ├── faqs/                 # FAQ documents
│   └── policies/             # Policy documents
└── db/                       # ChromaDB storage (auto-created)

app/api/v1/clinical_pph/
├── __init__.py               # Router exports
└── router.py                 # FastAPI endpoints
```

## 🚀 Setup & Installation

### Prerequisites

Ensure you have the required dependencies installed:

```bash
cd /root/hiva/services/ai
pip install -r requirements.txt
```

Required packages:
- `chromadb>=0.5.0`
- `sentence-transformers>=2.6.0`
- `fastapi>=0.104.0`
- `pdfplumber>=0.11.0`
- `python-docx>=1.1.0`

### Initial Setup

1. **Create the documents directory** (if not exists):
   ```bash
   mkdir -p /root/hiva/services/ai/clinical_pph/docs
   ```

2. **Add your documents**:
   - Place FAQ documents in `clinical_pph/docs/faqs/`
   - Place policy documents in `clinical_pph/docs/policies/`
   - Supported formats: PDF, DOCX, TXT, MD, JSONL

3. **Ingest documents**:
   ```bash
   cd /root/hiva/services/ai
   python -m clinical_pph.ingest
   ```

## 📥 Document Ingestion

### Basic Ingestion

Ingest all documents from the `docs/` directory:

```bash
python -m clinical_pph.ingest
```

### Clear and Re-ingest

To clear existing documents and re-ingest:

```bash
python -m clinical_pph.ingest --clear
```

### Supported Document Formats

- **PDF** (`.pdf`): Extracted using pdfplumber, with OCR fallback
- **DOCX** (`.docx`): Extracted using python-docx
- **Text** (`.txt`, `.md`): Direct text reading
- **JSONL** (`.jsonl`): Q&A pairs in JSON Lines format

### JSONL Format

For structured Q&A pairs, use JSONL format:

```jsonl
{"question": "What are the symptoms of PPH?", "answer": "Symptoms include...", "section": "Symptoms", "intent": "symptoms"}
{"question": "How is PPH treated?", "answer": "Treatment involves...", "section": "Treatment", "intent": "treatment"}
```

### Chunking Strategy

Documents are automatically chunked with:
- **Chunk size**: 900 characters (configurable)
- **Overlap**: 120 characters (configurable)
- **Strategy**: Paragraph-aware chunking with sentence boundary preservation

## 🔌 API Endpoints

### Base URL

All endpoints are prefixed with `/api/v1/clinical-pph`

### 1. Query Endpoint

**POST** `/api/v1/clinical-pph/ask`

Query the Clinical PPH knowledge base.

**Request Body:**
```json
{
  "query": "What are the risk factors for postpartum hemorrhage?",
  "session_id": "optional-session-id",
  "top_k": 5
}
```

**Response:**
```json
{
  "answer": "Risk factors for postpartum hemorrhage include...",
  "session_id": "session-id",
  "kb_id": "clinical_pph",
  "kb_name": "Clinical PPH (Postpartum Hemorrhage)"
}
```

**Parameters:**
- `query` (required): User question
- `session_id` (optional): Session identifier for conversation context
- `top_k` (optional): Number of documents to retrieve (default: 5)

### 2. Streaming Endpoint

**POST** `/api/v1/clinical-pph/stream`

Compatibility endpoint (currently returns JSON, can be enhanced for SSE).

**Request/Response:** Same as `/ask`

### 3. Health Check

**GET** `/api/v1/clinical-pph/health`

Check the health status of the knowledge base.

**Response:**
```json
{
  "status": "healthy",
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

## 💡 Usage Examples

### Python Example

```python
import requests

# Query the knowledge base
response = requests.post(
    "http://localhost:8000/api/v1/clinical-pph/ask",
    json={
        "query": "What are the treatment protocols for PPH?",
        "session_id": "user-123",
        "top_k": 5
    }
)

result = response.json()
print(result["answer"])
```

### cURL Example

```bash
curl -X POST http://localhost:8000/api/v1/clinical-pph/ask \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the symptoms of postpartum hemorrhage?",
    "session_id": "test-session",
    "top_k": 5
  }'
```

### Multi-turn Conversation

```python
import requests

session_id = "user-123"

# First query
response1 = requests.post(
    "http://localhost:8000/api/v1/clinical-pph/ask",
    json={
        "query": "What is postpartum hemorrhage?",
        "session_id": session_id
    }
)
print(response1.json()["answer"])

# Follow-up query (uses conversation context)
response2 = requests.post(
    "http://localhost:8000/api/v1/clinical-pph/ask",
    json={
        "query": "What are the risk factors?",
        "session_id": session_id  # Same session_id
    }
)
print(response2.json()["answer"])
```

## ⚙️ Configuration

### Environment Variables

The system uses settings from `app/core/config.py`. Key configurations:

- `EMBEDDING_MODEL`: Embedding model name (default: `"BAAI/bge-small-en-v1.5"`)
- `RAG_CHUNK_SIZE`: Document chunk size (default: `900`)
- `RAG_CHUNK_OVERLAP`: Chunk overlap size (default: `120`)
- `RAG_DEFAULT_TOP_K`: Default number of documents to retrieve (default: `5`)

### Customization

To customize the embedding model, edit `app/core/config.py`:

```python
class Settings(BaseSettings):
    EMBEDDING_MODEL: str = "sentence-transformers/all-mpnet-base-v2"  # Larger, more accurate
    RAG_CHUNK_SIZE: int = 1000  # Larger chunks
    RAG_CHUNK_OVERLAP: int = 150  # More overlap
```

## 🔍 Troubleshooting

### No Documents Retrieved

**Problem**: Queries return "I couldn't find specific information..."

**Solutions**:
1. Check if documents are ingested:
   ```bash
   python -m clinical_pph.ingest
   ```
2. Verify documents exist in `clinical_pph/docs/`
3. Check collection count:
   ```bash
   curl http://localhost:8000/api/v1/clinical-pph/health
   ```

### Empty Collection

**Problem**: Health check shows `collection_count: 0`

**Solution**: Run ingestion:
```bash
python -m clinical_pph.ingest --clear
```

### Import Errors

**Problem**: `ModuleNotFoundError: No module named 'clinical_pph'`

**Solution**: Ensure you're running from the correct directory:
```bash
cd /root/hiva/services/ai
python -m clinical_pph.ingest
```

### Low Retrieval Quality

**Problem**: Retrieved documents are not relevant

**Solutions**:
1. Increase `top_k` parameter (try 7-10)
2. Use more specific queries
3. Consider using a larger embedding model
4. Review document chunking strategy

## 📚 Additional Resources

- [RAG System Documentation](../RAG_SYSTEM.md)
- [Architecture Documentation](../ARCHITECTURE.md)
- [Quick Start Guide](../QUICK_START.md)

## 🤝 Contributing

When adding new documents:

1. Place documents in `clinical_pph/docs/`
2. Run ingestion: `python -m clinical_pph.ingest`
3. Test with health check endpoint
4. Verify retrieval quality with sample queries

## 📝 License

This system is part of the HIVA AI service.

---

**Last Updated**: 2024
**Version**: 1.0.0


