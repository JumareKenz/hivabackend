# HIVA - Hayok Intelligent Virtual Assistant

State-of-the-art AI assistant for insurance company with 9 branch support.

## 🚀 Features

- **High Performance**: Optimized async operations with HTTP/2
- **Smart Branch Detection**: Automatic branch identification from queries
- **Context-Aware**: Maintains conversation history and branch-specific context
- **RAG System**: Advanced retrieval with BAAI/bge-small-en-v1.5 embeddings
- **Smart Caching**: Response caching that maintains accuracy and context
- **Streaming Support**: Real-time streaming responses
- **9 Branch Support**: Kano, Kogi, Kaduna, FCT, Adamawa, Zamfara, Sokoto, Rivers, Osun

## 📋 Requirements

- Python 3.12+
- Ollama with phi3:latest model
- 20 CPU cores, 12GB RAM (optimized for Contabo VPS)

## 🛠️ Installation

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
cd services/ai
pip install -r requirements.txt
```

## 🚀 Running

```bash
cd services/ai
source ../../venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## 📡 API Endpoints

### Streaming
```
POST /api/v1/stream
{
  "query": "What is FHIS?",
  "session_id": "optional",
  "branch_id": "fct"
}
```

### Non-Streaming
```
POST /api/v1/ask
{
  "query": "What is FHIS?",
  "session_id": "optional",
  "branch_id": "fct"
}
```

## 📁 Project Structure

```
hiva/
├── services/
│   └── ai/
│       ├── app/
│       │   ├── api/v1/        # API endpoints
│       │   ├── services/     # Core services
│       │   ├── rag/          # RAG system
│       │   └── core/         # Configuration
│       └── requirements.txt
├── docs/                     # Branch FAQ documents
└── venv/                     # Virtual environment
```

## 🔧 Configuration

Edit `app/core/config.py` or set environment variables:

```python
LLM_MODEL: str = "phi3:latest"
EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
RESPONSE_CACHE_ENABLED: bool = True
```

## 📚 Documentation

- `FRONTEND_INTEGRATION.md` - Frontend setup guide
- `BRANCH_DETECTION_GUIDE.md` - Branch detection details
- `PERFORMANCE_OPTIMIZATION.md` - Performance tuning
- `SMART_CACHING.md` - Caching system
- `FAQ_INGESTION_COMPLETE.md` - FAQ setup

## 🎯 Branch Support

- Kano (KSCHMA)
- Kogi (KGSHIA)
- Kaduna (KADCHMA)
- FCT (FHIS)
- Adamawa (ASCHMA)
- Zamfara (ZAMCHEMA)
- Sokoto (SOHEMA)
- Rivers (RIVCHPP)
- Osun (OSHIA)

## 📝 License

Proprietary - All rights reserved

