# Admin Chat Service - Quick Start Guide

## ✅ Setup Complete!

The Admin Chat Service is fully configured and ready to use. Here's what was set up:

## What's Working

✅ **Database Connection**: MySQL database connected and tested  
✅ **SQL Generator**: Schema-aware SQL generation service  
✅ **Visualization Service**: Data analysis and formatting  
✅ **Conversation Manager**: Chat context retention  
✅ **Authentication**: Admin API key authentication  
✅ **FastAPI Server**: All endpoints registered and ready  

## Quick Test

### 1. Test Database Connection
```bash
cd /root/hiva/services/ai/admin_chat
source venv/bin/activate
python3 test_db_connection.py
```

### 2. Test End-to-End Flow
```bash
python3 test_end_to_end.py
```

### 3. Start the Server
```bash
python3 main.py
```

The server will start on `http://194.163.168.161:8001`

## API Usage Example

### Natural Language Query
```bash
curl -X POST "http://localhost:8001/api/v1/admin/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Show me the top 10 facilities by claim volume",
    "session_id": "test-session"
  }'
```

### Follow-up Query (with context)
```bash
curl -X POST "http://localhost:8001/api/v1/admin/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What about in Osun State?",
    "session_id": "test-session",
    "refine_query": true
  }'
```

## Configuration Needed

⚠️ **RunPod LLM** (for natural language to SQL):
- Add `RUNPOD_API_KEY` and `RUNPOD_ENDPOINT_ID` to `/root/hiva/services/ai/.env`
- Without this, SQL generation will fail (but direct SQL queries still work)

## Service Architecture

```
Natural Language Query
    ↓
SQL Generator (LLM + Schema)
    ↓
Database (Read-Only MySQL)
    ↓
Visualization Service
    ↓
Response (Data + Charts + Summary)
```

## Key Features

1. **No SQL Skills Required**: Users query in natural language
2. **Schema-Aware**: System knows all tables and columns
3. **Context Retention**: Follow-up questions use conversation history
4. **Visualizations**: Automatic chart suggestions based on data
5. **Read-Only**: Only SELECT queries allowed (security)

## Documentation

- Full setup: `SETUP_COMPLETE.md`
- Database setup: `DATABASE_SETUP_INSTRUCTIONS.txt`
- Firewall setup: `FIREWALL_SETUP.md`

## Next Steps

1. Configure RunPod LLM for SQL generation
2. Test with real queries
3. Deploy to production
4. Integrate with frontend







