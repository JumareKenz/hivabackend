# HIVA AI Services - Backend Server

A comprehensive, production-ready AI services backend platform providing Retrieval-Augmented Generation (RAG), natural language to SQL analytics, and specialized knowledge bases for healthcare administration in Nigeria.

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Directory Structure](#directory-structure)
- [Main Components](#main-components)
- [Getting Started](#getting-started)
- [API Documentation](#api-documentation)
- [Configuration](#configuration)
- [Development](#development)
- [Deployment](#deployment)

## 🎯 Overview

HIVA AI Services is a modular FastAPI-based backend platform that powers intelligent conversational interfaces, document retrieval systems, and analytics capabilities for healthcare administration. The system supports multiple knowledge domains, state-specific FAQ systems, clinical documentation, and administrative analytics.

### Key Features

- **Multi-Domain RAG System**: Isolated knowledge bases for 9 Nigerian states, providers, and clinical documentation
- **Natural Language to SQL**: Admin chat service for querying databases without SQL knowledge
- **Clinical PPH System**: Specialized RAG for Postpartum Hemorrhage clinical guidelines
- **Claims Automation**: Automated claims processing and validation
- **State-Specific APIs**: Dedicated endpoints for each state's health insurance scheme
- **Conversation Management**: Multi-turn dialogue support with context retention
- **Vector Search**: ChromaDB-powered semantic search with sentence transformers

## 🏗️ Architecture

The system follows a modular, microservices-oriented architecture:

```
┌─────────────────────────────────────────────────────────────┐
│                    Client Layer                              │
│         (Web App, Mobile App, API Consumers)                  │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│              API Gateway (Nginx) / FastAPI                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Main AI      │  │ Admin Chat   │  │ Clinical PPH │      │
│  │ Service      │  │ Service      │  │ Service      │      │
│  │ (Port 8000)  │  │ (Port 8001)  │  │              │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└───────────────────────┬─────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ RAG Services│ │ SQL Generator│ │ Vector Store │
│ (States/    │ │ (Vanna AI)   │ │ (ChromaDB)   │
│ Providers)  │ │              │ │              │
└──────────────┘ └──────────────┘ └──────────────┘
```

### Technology Stack

- **Framework**: FastAPI 0.104.0+
- **LLM Integration**: Groq API, RunPod (Qwen2.5-7B-Instruct)
- **Vector Database**: ChromaDB
- **Embeddings**: SentenceTransformers (BAAI/bge-small-en-v1.5)
- **Database**: MySQL (for admin analytics)
- **Document Processing**: pdfplumber, python-docx
- **Visualization**: Plotly, Matplotlib
- **API Gateway**: Nginx

## 📁 Directory Structure

```
services/
├── ai/                              # Main AI services directory
│   ├── app/                         # Main AI service (Port 8000)
│   │   ├── api/                     # API endpoints
│   │   │   └── v1/
│   │   │       ├── chat.py          # Main chat endpoint
│   │   │       ├── stream.py        # Streaming endpoint
│   │   │       ├── states/          # State-specific endpoints (9 states)
│   │   │       ├── providers/       # Provider knowledge base endpoints
│   │   │       └── clinical_pph/    # Clinical PPH endpoints
│   │   ├── core/
│   │   │   └── config.py           # Main service configuration
│   │   ├── services/                # Core services
│   │   │   ├── rag_service.py      # RAG orchestration
│   │   │   ├── conversation_manager.py  # Chat context management
│   │   │   ├── branch_detector.py  # State/branch detection
│   │   │   └── ollama_client.py    # LLM client (Groq API)
│   │   ├── rag/                     # FAQ ingestion utilities
│   │   ├── state_kb/                # State knowledge base system
│   │   │   ├── store.py            # ChromaDB vector store
│   │   │   ├── retriever.py        # Semantic search
│   │   │   ├── service.py          # Async service layer
│   │   │   └── ingest.py           # Document ingestion
│   │   ├── providers_rag/           # Production-grade provider RAG
│   │   └── main.py                  # Main FastAPI application
│   │
│   ├── admin_chat/                  # Admin Chat Service (Port 8001)
│   │   ├── app/
│   │   │   ├── api/v1/
│   │   │   │   └── admin.py        # Admin analytics endpoints
│   │   │   ├── core/
│   │   │   │   └── config.py       # Admin service configuration
│   │   │   └── services/
│   │   │       ├── sql_generator.py      # NL to SQL translation
│   │   │       ├── database_service.py   # MySQL connection pool
│   │   │       ├── visualization_service.py  # Chart generation
│   │   │       ├── vanna_service.py      # Vanna AI integration
│   │   │       ├── domain_router.py      # Domain routing
│   │   │       └── intent_router.py      # Intent classification
│   │   └── main.py                  # Admin service entry point
│   │
│   ├── clinical_pph/                 # Clinical PPH RAG system
│   │   ├── store.py                 # Vector store
│   │   ├── retriever.py             # Document retrieval
│   │   ├── service.py               # Service layer
│   │   ├── ingest.py                # Document ingestion
│   │   └── docs/                    # Clinical documents
│   │
│   ├── claims_automation/            # Claims processing system
│   ├── zamfara_rag/                  # Zamfara-specific RAG
│   ├── nginx_gateway/                # Nginx configuration
│   ├── requirements.txt              # Python dependencies
│   └── ARCHITECTURE.md               # Detailed architecture docs
│
└── .gitignore                        # Git ignore rules
```

## 🔧 Main Components

### 1. Main AI Service (`ai/app/main.py`)

The primary AI service providing:
- **Chat API**: `/api/chat` - Main conversational endpoint
- **Streaming API**: `/api/v1/stream` - Server-sent events for streaming responses
- **State Endpoints**: `/api/v1/states/{state_id}/ask` - State-specific FAQ queries
  - Supported states: Adamawa, FCT, Kano, Zamfara, Kogi, Osun, Rivers, Sokoto, Kaduna
- **Provider Endpoints**: `/api/v1/providers/ask` - Provider knowledge base queries
- **Clinical PPH**: `/api/v1/clinical-pph/ask` - Clinical documentation queries
- **Health Check**: `/health` - Service health status

**Port**: 8000  
**LLM**: Groq API (default: `groq/compound`, `groq/compound-mini`)

### 2. Admin Chat Service (`ai/admin_chat/main.py`)

Natural language to SQL analytics service for internal staff:
- **Admin Analytics**: `/api/v1/admin/query` - NL to SQL query endpoint
- **Schema Information**: `/api/v1/admin/schema` - Database schema details
- **Health Check**: `/health` - Service health status

**Port**: 8001  
**LLM**: RunPod (Qwen2.5-7B-Instruct) with Groq fallback  
**Database**: MySQL (read-only analytics database)  
**Features**:
- Vanna AI integration for SQL generation
- Domain-aware routing (claims, providers, facilities, etc.)
- Visualization suggestions (charts, tables)
- Conversation context retention

### 3. RAG Systems

#### State Knowledge Bases
- **9 Nigerian States**: Each with isolated vector store and endpoints
- **Document Formats**: PDF, DOCX, TXT, MD
- **Embedding Model**: BAAI/bge-small-en-v1.5
- **Vector Store**: ChromaDB (persistent, local storage)

#### Provider Knowledge Base
- **Production-Grade**: Zero-hallucination RAG system
- **Grounding**: Strict source attribution
- **Safety**: Content validation and filtering

#### Clinical PPH
- **Specialized Domain**: Postpartum Hemorrhage clinical guidelines
- **Isolated Collection**: Separate from other knowledge bases
- **Multi-Format Support**: PDF, DOCX, TXT, MD, JSONL

### 4. Claims Automation

Automated claims processing system with validation, fraud detection, and workflow management.

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- MySQL (for admin chat service)
- ChromaDB (installed via pip)
- Groq API key (for LLM access)
- RunPod API key (optional, for admin chat)

### Installation

1. **Clone the repository**:
```bash
git clone <repository-url>
cd services
```

2. **Create virtual environment**:
```bash
cd ai
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**:
```bash
pip install -r requirements.txt
```

4. **Configure environment variables**:

Create `.env` file in `ai/` directory:
```env
# LLM Configuration
LLM_API_KEY=your_groq_api_key
LLM_MODEL=groq/compound
LLM_API_URL=https://api.groq.com/openai/v1

# Admin Chat (optional)
RUNPOD_API_KEY=your_runpod_key
GROQ_API_KEY=your_groq_key
ADMIN_API_KEY=your_admin_key

# Database (for admin chat)
DB_HOST=localhost
DB_PORT=3306
DB_USER=your_user
DB_PASSWORD=your_password
DB_NAME=your_database
```

### Running Locally

#### Main AI Service

```bash
cd ai/app
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Service will be available at: `http://localhost:8000`

#### Admin Chat Service

```bash
cd ai/admin_chat
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

Service will be available at: `http://localhost:8001`

### Document Ingestion

#### Ingest State Knowledge Bases

```bash
cd ai/app/state_kb
python ingest.py --kb-id adamawa --docs-path ../rag/faqs/branches/adamawa/
```

#### Ingest Clinical PPH Documents

```bash
cd ai/clinical_pph
python ingest.py --docs-path docs/
```

## 📡 API Documentation

### Main AI Service (Port 8000)

#### Chat Endpoint
```http
POST /api/chat
Content-Type: application/json

{
  "message": "What is the enrollment process?",
  "conversation_id": "optional-session-id",
  "kb_id": "optional-knowledge-base-id"
}
```

#### State-Specific Query
```http
POST /api/v1/states/adamawa/ask
Content-Type: application/json

{
  "query": "What are the benefits covered?",
  "conversation_id": "optional-session-id"
}
```

#### Health Check
```http
GET /health
```

### Admin Chat Service (Port 8001)

#### Natural Language Query
```http
POST /api/v1/admin/query
Authorization: Bearer <admin_api_key>
Content-Type: application/json

{
  "query": "Show top 10 facilities by claim volume in Osun State this quarter",
  "conversation_id": "optional-session-id"
}
```

#### Schema Information
```http
GET /api/v1/admin/schema
Authorization: Bearer <admin_api_key>
```

### Interactive API Documentation

FastAPI provides automatic interactive documentation:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

## ⚙️ Configuration

### Main Service Configuration

Located in `ai/app/core/config.py`:
- `SERVICE_NAME`: Service identifier
- `HOST`: Bind address (default: `0.0.0.0`)
- `PORT`: Service port (default: `8000`)
- `LLM_MODEL`: LLM model identifier
- `EMBEDDING_MODEL`: Embedding model for RAG
- `RAG_CHUNK_SIZE`: Document chunk size
- `RAG_DEFAULT_TOP_K`: Number of retrieved documents

### Admin Chat Configuration

Located in `ai/admin_chat/app/core/config.py`:
- `PORT`: Admin service port (default: `8001`)
- `RUNPOD_BASE_URL`: RunPod endpoint
- `USE_VANNA_AI`: Enable Vanna AI integration
- `ADMIN_API_KEY`: Authentication key

## 🛠️ Development

### Project Structure Guidelines

- **API Routes**: `app/api/v1/` - RESTful endpoints
- **Services**: `app/services/` - Business logic
- **Core**: `app/core/` - Configuration and utilities
- **RAG**: `app/rag/`, `app/state_kb/` - Retrieval systems

### Adding a New State Knowledge Base

1. Add documents to `app/rag/faqs/branches/{state_id}/`
2. Create router in `app/api/v1/states/{state_id}.py`
3. Register router in `app/main.py`
4. Ingest documents: `python app/state_kb/ingest.py --kb-id {state_id}`

### Testing

```bash
# Test main service
curl http://localhost:8000/health

# Test admin service
curl http://localhost:8001/health
```

## 🚢 Deployment

### Docker Deployment

The project includes Docker configuration:
- `Dockerfile`: Container definition
- `docker-compose.yml`: Multi-service orchestration

### Production Considerations

- **Environment Variables**: Use secure secret management
- **Database Connections**: Connection pooling configured
- **Vector Store**: ChromaDB persistence enabled
- **CORS**: Configured for production domains
- **Rate Limiting**: Implement as needed
- **Monitoring**: Add logging and metrics collection

### Nginx Gateway

Configuration available in `ai/nginx_gateway/` for production routing.

## 📚 Additional Documentation

- **Architecture Details**: See `ai/ARCHITECTURE.md`
- **RAG System**: See `ai/RAG_SYSTEM.md`
- **Clinical PPH**: See `ai/clinical_pph/README.md`
- **Admin Chat**: See `ai/admin_chat/` documentation files
- **Claims Automation**: See `ai/claims_automation/README.md`

## 🔒 Security Notes

- **API Keys**: Never commit `.env` files
- **Database**: Admin chat uses read-only database connections
- **SQL Injection**: All SQL queries are parameterized
- **Authentication**: Admin endpoints require API key
- **CORS**: Configured for specific origins

## 📝 License

[Specify license here]

## 🤝 Contributing

[Contributing guidelines]

## 📧 Contact

[Contact information]

---

**Version**: 3.0.0  
**Last Updated**: 2024  
**Status**: Production Ready
