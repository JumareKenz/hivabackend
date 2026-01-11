# Clinical PPH Endpoint - Server Restart Guide

## ✅ Verification Complete

All routes are properly configured:
- ✅ `/api/v1/clinical-pph/ask` (POST)
- ✅ `/api/v1/clinical-pph/stream` (POST)
- ✅ `/api/v1/clinical-pph/health` (GET)

## ⚠️ Issue

The server at `https://api.hiva.chat` was started **before** the Clinical PPH routes were added, so it doesn't have the new endpoints loaded.

## 🔄 Solution: Restart the Server

### Option 1: Restart via Process (if running directly)

```bash
# Find the process
ps aux | grep "uvicorn app.main:app" | grep -v grep

# Kill the process (replace PID with actual process ID)
kill <PID>

# Restart the server
cd /root/hiva/services/ai
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

### Option 2: Restart via Systemd (if using a service)

```bash
# Check if there's a systemd service
systemctl status hiva-ai  # or whatever the service name is

# Restart the service
sudo systemctl restart hiva-ai
```

### Option 3: Restart via Docker/Container

```bash
# If using Docker
docker-compose restart

# Or if using a container directly
docker restart <container-name>
```

### Option 4: Graceful Restart (Recommended)

```bash
# Send HUP signal for graceful reload (if supported)
kill -HUP <PID>

# Or use uvicorn's reload feature (development)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## ✅ After Restart - Verify

### Test Health Endpoint

```bash
curl https://api.hiva.chat/api/v1/clinical-pph/health
```

Expected response:
```json
{
  "status": "healthy",
  "kb_id": "clinical_pph",
  "kb_name": "Clinical PPH (Postpartum Hemorrhage)",
  "collection_count": 244,
  "cache_stats": {
    "cache_size": 0,
    "max_cache_size": 256,
    "cache_utilization": 0.0
  }
}
```

### Test Ask Endpoint

```bash
curl -X POST https://api.hiva.chat/api/v1/clinical-pph/ask \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is postpartum hemorrhage?",
    "session_id": "test-123"
  }'
```

Expected response:
```json
{
  "answer": "Postpartum haemorrhage is defined as...",
  "session_id": "test-123",
  "kb_id": "clinical_pph",
  "kb_name": "Clinical PPH (Postpartum Hemorrhage)"
}
```

## 🔍 Current Server Status

The server is currently running but **does not have the Clinical PPH routes loaded** because it was started before the routes were added.

**Process ID**: Check with `ps aux | grep uvicorn`

## 📝 Quick Restart Command

If you have access to the server:

```bash
cd /root/hiva/services/ai
pkill -f "uvicorn app.main:app"
source .venv/bin/activate
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 > /tmp/hiva-ai.log 2>&1 &
```

## ✅ Verification Script

Run this to verify routes are loaded:

```bash
cd /root/hiva/services/ai
source .venv/bin/activate
python3 verify_clinical_pph_routes.py
```

---

**Status**: Routes configured ✅ | Server restart required ⚠️


