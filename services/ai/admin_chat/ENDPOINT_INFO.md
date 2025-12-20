# Admin Chat Service - Endpoint Information

## API Endpoint

The Admin Chat Service is available at:

```
http://194.163.168.161:8001
```

## Base URL

```
http://194.163.168.161:8001
```

## Available Endpoints

### 1. Health Check
```
GET /health
```
**Response:**
```json
{
  "status": "healthy",
  "database_available": true
}
```

### 2. Root Endpoint
```
GET /
```
**Response:**
```json
{
  "service": "Hiva Admin Chat API",
  "version": "1.0.0",
  "status": "running",
  "database_available": true
}
```

### 3. Natural Language Query
```
POST /api/v1/admin/query
```

**Headers:**
```
Content-Type: application/json
X-API-Key: <your-admin-api-key>
```

**Request Body:**
```json
{
  "query": "Show me the total number of claims",
  "session_id": "unique-session-id",
  "refine_query": false
}
```

**Response:**
```json
{
  "success": true,
  "data": [...],
  "sql": "SELECT COUNT(*) AS total_claims FROM claims",
  "sql_explanation": "...",
  "visualization": {...},
  "summary": "...",
  "session_id": "unique-session-id",
  "error": null,
  "confidence": 0.9
}
```

### 4. Database Schema
```
GET /api/v1/admin/schema
```

**Headers:**
```
X-API-Key: <your-admin-api-key>
```

**Response:**
```json
{
  "tables": [
    {
      "table_name": "claims",
      "columns": [...]
    }
  ]
}
```

## Authentication

All admin endpoints (except `/health` and `/`) require authentication via:

1. **X-API-Key Header:**
   ```
   X-API-Key: <your-admin-api-key>
   ```

2. **Bearer Token:**
   ```
   Authorization: Bearer <your-admin-api-key>
   ```

## Example Usage

### Using cURL

```bash
# Health check (no auth required)
curl http://194.163.168.161:8001/health

# Query with API key
curl -X POST "http://194.163.168.161:8001/api/v1/admin/query" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{
    "query": "Show me the top 10 facilities by claim volume",
    "session_id": "my-session-123"
  }'
```

### Using JavaScript/Fetch

```javascript
const response = await fetch('http://194.163.168.161:8001/api/v1/admin/query', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': 'your-api-key-here'
  },
  body: JSON.stringify({
    query: 'Show me the total number of claims',
    session_id: 'my-session-123'
  })
});

const data = await response.json();
console.log(data);
```

## Service Management

The service runs as a systemd service and will automatically restart if it crashes.

### Check Status
```bash
sudo systemctl status hiva-admin-chat
```

### View Logs
```bash
sudo journalctl -u hiva-admin-chat -f
```

### Restart Service
```bash
sudo systemctl restart hiva-admin-chat
```

### Stop Service
```bash
sudo systemctl stop hiva-admin-chat
```

### Start Service
```bash
sudo systemctl start hiva-admin-chat
```

## CORS Configuration

The service allows requests from:
- `https://hiva.chat`
- `https://api.hiva.chat`
- `http://localhost:3000`
- `http://localhost:5173`
- `https://hiva-two.vercel.app`

## Notes

- The service runs on port **8001** (different from the RAG chatbot on port 8000)
- The service uses a **read-only** database connection for security
- All SQL queries are validated to ensure they are SELECT statements only
- Conversation context is maintained per `session_id` for follow-up queries





