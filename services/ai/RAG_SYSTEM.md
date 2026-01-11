## HIVA RAG System (States + Providers)

This repo implements a **modular Retrieval-Augmented Generation (RAG)** system where each knowledge domain is isolated:

- **Branch FAQs (legacy)**: `app/rag/` (used by `/api/v1/ask` and `/api/v1/stream`)
- **State + Providers KBs**: `app/state_kb/` (10 dedicated endpoints)

> 📚 **For comprehensive documentation, see:**
> - [Complete RAG System Documentation](RAG_SYSTEM_COMPLETE.md) - Full guide with examples
> - [Architecture Documentation](ARCHITECTURE.md) - System design and components
> - [Quick Start Guide](QUICK_START.md) - Get started in 5 minutes

### Folder structure

#### Branch FAQ RAG (existing endpoints)

- **Docs**: `app/rag/faqs/`
  - General: `app/rag/faqs/*`
  - Branch-specific: `app/rag/faqs/branches/<branch_id>/`
- **Vector DB**: `app/rag/db/` (Chroma persistent store)
- **Ingestion**: `python3 -m app.rag.ingest`
- **Retrieval**: `app/rag/retriever.py`

#### State/Provider KB RAG (new)

- **Docs**:
  - States: `app/rag/faqs/branches/<state_id>/`
  - Providers: `app/rag/faqs/providers/`
- **Vector DB**: `app/state_kb/db/`
  - Per KB collection: `kb_<kb_id>` (e.g. `kb_adamawa`, `kb_providers`)
- **Ingestion**: `python3 -m app.state_kb.ingest`
- **Retrieval**: `app/state_kb/retriever.py`
- **Service**: `app/state_kb/service.py` (async + caching)

### Conversation context (multi-turn)

Conversation history is managed by `app/services/conversation_manager.py`.

- Existing flows use `branch_id`
- State/provider KB flows use `kb_id`

Provide a stable `session_id` across requests to get coherent follow-ups.

### Setup

Install dependencies (from `services/ai/`):

```bash
python3 -m pip install -r requirements.txt
```

### Build indices (ingestion)

Build state/provider KB indices:

```bash
python3 -m app.state_kb.ingest
```

Build branch FAQ index (used by `/ask`):

```bash
python3 -m app.rag.ingest
```

### API endpoints

Mounted under `/api/v1` in `app/main.py`.

- **States**: `POST /api/v1/states/<state_id>/ask`
  - `adamawa`, `fct`, `kano`, `zamfara`, `kogi`, `osun`, `rivers`, `sokoto`, `kaduna`
- **Providers**: `POST /api/v1/providers/ask`

Body:

```json
{ "query": "…", "session_id": "optional", "top_k": 5 }
```


