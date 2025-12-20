# Admin Chat Service - Setup Complete ✅

## Overview
The Admin Chat Service enables internal staff (analysts, operations, senior management) to query large datasets using natural language and receive actionable insights (tables, charts, summaries), **no SQL skills required**.

## How It Works

1. **User Query**: User types a natural-language query (e.g., "Show top 10 facilities by claim volume in Osun State this quarter")
2. **SQL Generation**: System translates to SQL via a schema-aware agent using LLM
3. **Query Execution**: Executes on read-only analytics database (MySQL)
4. **Results & Visualization**: Returns results plus visualization suggestions and commentary
5. **Follow-up Questions**: Users can refine via follow-up questions (chat context retained)

## Components Status

### ✅ Completed Components

1. **Database Service** (`app/services/database_service.py`)
   - ✅ MySQL connection pool initialized
   - ✅ Read-only query execution
   - ✅ Schema information retrieval
   - ✅ Connection tested and working

2. **SQL Generator** (`app/services/sql_generator.py`)
   - ✅ Schema-aware SQL generation
   - ✅ Natural language to SQL translation
   - ✅ Conversation history support
   - ✅ Security: Only SELECT queries allowed

3. **Visualization Service** (`app/services/visualization_service.py`)
   - ✅ Data analysis and visualization suggestions
   - ✅ Table formatting with pagination
   - ✅ Summary generation

4. **Conversation Manager** (`app/services/conversation_manager.py`)
   - ✅ Chat context retention
   - ✅ Follow-up question support
   - ✅ Conversation history management

5. **LLM Client** (`app/services/llm_client.py`)
   - ✅ RunPod API integration
   - ⚠️  **Requires configuration** (see below)

6. **Authentication** (`app/core/auth.py`)
   - ✅ Admin API key authentication
   - ✅ Bearer token support
   - ✅ Development mode (no auth if key not set)

7. **FastAPI Application** (`main.py`)
   - ✅ Main application entry point
   - ✅ Database initialization on startup
   - ✅ CORS configuration
   - ✅ API endpoints registered

## Configuration Required

### 1. RunPod LLM Configuration (Required for SQL Generation)

Add to `/root/hiva/services/ai/.env`:

```bash
# RunPod GPU LLM Configuration
RUNPOD_API_KEY=your_runpod_api_key_here
RUNPOD_ENDPOINT_ID=your_endpoint_id_here
# OR use direct URL:
RUNPOD_BASE_URL=https://api.runpod.ai/v2/{endpoint_id}/runsync
```

**Note**: Without RunPod configuration, SQL generation will fail. The service will still work for direct SQL queries, but natural language to SQL translation requires the LLM.

### 2. Admin API Key (Optional - for production)

Add to `/root/hiva/services/ai/.env`:

```bash
ADMIN_API_KEY=your_secure_admin_api_key_here
```

If not set, the service runs in development mode (no authentication required).

### 3. Database Configuration (Already Set ✅)

```bash
ANALYTICS_DB_TYPE=mysql
ANALYTICS_DB_HOST=claimify-api.hayokmedicare.ng
ANALYTICS_DB_PORT=3306
ANALYTICS_DB_NAME=hip
ANALYTICS_DB_USER=hipnanle
ANALYTICS_DB_PASSWORD=NSanle657.
```

## API Endpoints

### POST `/api/v1/admin/query`
Natural language query endpoint

**Request:**
```json
{
  "query": "Show top 10 facilities by claim volume in Osun State this quarter",
  "session_id": "optional-session-id",
  "refine_query": false
}
```

**Response:**
```json
{
  "success": true,
  "data": [...],
  "sql": "SELECT ...",
  "sql_explanation": "...",
  "visualization": {
    "type": "table_with_chart",
    "table": {...},
    "suggestions": [...]
  },
  "summary": "...",
  "session_id": "...",
  "confidence": 0.85
}
```

### GET `/api/v1/admin/schema?table_name=optional`
Get database schema information

### GET `/api/v1/admin/health`
Health check endpoint

## Running the Service

### Development Mode

```bash
cd /root/hiva/services/ai/admin_chat
source venv/bin/activate
python3 main.py
```

### Production Mode (using uvicorn)

```bash
cd /root/hiva/services/ai/admin_chat
source venv/bin/activate
uvicorn main:app --host 194.163.168.161 --port 8001
```

## Testing

### Test Database Connection
```bash
cd /root/hiva/services/ai/admin_chat
source venv/bin/activate
python3 test_db_connection.py
```

### Test End-to-End Flow
```bash
cd /root/hiva/services/ai/admin_chat
source venv/bin/activate
python3 test_end_to_end.py
```

## Example Usage

### 1. Natural Language Query
```bash
curl -X POST "http://localhost:8001/api/v1/admin/query" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-admin-key" \
  -d '{
    "query": "Show me the top 10 facilities by claim volume",
    "session_id": "session-123"
  }'
```

### 2. Follow-up Query (with context)
```bash
curl -X POST "http://localhost:8001/api/v1/admin/query" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-admin-key" \
  -d '{
    "query": "What about in Osun State?",
    "session_id": "session-123",
    "refine_query": true
  }'
```

## Architecture

```
User Query (Natural Language)
    ↓
SQL Generator (LLM + Schema)
    ↓
Database Service (Read-Only MySQL)
    ↓
Visualization Service
    ↓
Response (Data + Charts + Summary)
```

## Security Features

1. **Read-Only Queries**: Only SELECT statements allowed
2. **Query Validation**: Forbidden keywords blocked (INSERT, UPDATE, DELETE, etc.)
3. **Admin Authentication**: API key or Bearer token required
4. **Connection Pooling**: Secure connection management

## Next Steps

1. ✅ Database connection: **Working**
2. ⚠️  Configure RunPod LLM for SQL generation
3. ✅ Test API endpoints
4. ✅ Deploy service
5. ✅ Frontend integration

## Troubleshooting

### SQL Generation Fails
- Check RunPod API key is set in `.env`
- Verify RunPod endpoint is accessible
- Check LLM client logs

### Database Connection Fails
- Verify database credentials in `.env`
- Check firewall allows port 3306
- Test with `test_db_connection.py`

### Authentication Fails
- Check `ADMIN_API_KEY` is set (or remove for dev mode)
- Verify API key in request headers

## Support

For issues or questions, check:
- Database connection: `test_db_connection.py`
- End-to-end flow: `test_end_to_end.py`
- Service logs: Check console output







