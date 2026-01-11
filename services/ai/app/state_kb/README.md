## State/Provider RAG (Knowledge Bases)

This service supports **10 isolated knowledge bases**:
- **States**: `adamawa`, `fct`, `kano`, `zamfara`, `kogi`, `osun`, `rivers`, `sokoto`, `kaduna`
- **Providers**: `providers`

Each KB is stored in its own **ChromaDB collection** (`kb_<kb_id>`) under:
- `app/state_kb/db/`

### Document folders (per KB)

This repo already contains the per-KB folders:
- **States**: `app/rag/faqs/branches/<state_id>/`
- **Providers**: `app/rag/faqs/providers/`

Supported file formats:
- `.pdf`, `.docx`, `.txt`, `.md`

### Ingest / build vector indices

From `services/ai/`:

```bash
python3 -m app.state_kb.ingest
```

Ingest a single KB:

```bash
python3 -m app.state_kb.ingest adamawa
python3 -m app.state_kb.ingest providers
```

Clear and re-ingest:

```bash
python3 -m app.state_kb.ingest adamawa --clear
```

### API endpoints (dedicated per KB)

All endpoints are mounted under `/api/v1`.

- **States**: `POST /api/v1/states/<state_id>/ask`
  - Example: `POST /api/v1/states/adamawa/ask`
- **Providers**: `POST /api/v1/providers/ask`

Request body:

```json
{
  "query": "What is the waiting period?",
  "session_id": "optional-session-id",
  "top_k": 5
}
```

Example `curl`:

```bash
curl -X POST http://localhost:8000/api/v1/states/adamawa/ask \
  -H "Content-Type: application/json" \
  -d '{"query":"Is enrollment compulsory?","session_id":"demo1","top_k":5}'
```

### Conversation context (multi-turn)

Pass a stable `session_id` across requests; the service stores short chat history in memory and
injects a compact conversation summary + recent turns to keep answers consistent across follow-ups.


