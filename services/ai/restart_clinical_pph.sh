#!/bin/bash
# Restart script for Clinical PPH endpoints

echo "🔄 Restarting HIVA AI server to load Clinical PPH routes..."

cd /root/hiva/services/ai

# Find and kill existing process
PID=$(ps aux | grep "uvicorn app.main:app" | grep -v grep | awk '{print $2}')
if [ ! -z "$PID" ]; then
    echo "   Stopping existing server (PID: $PID)..."
    kill $PID
    sleep 2
    # Force kill if still running
    if ps -p $PID > /dev/null 2>&1; then
        kill -9 $PID
    fi
    echo "   ✓ Server stopped"
else
    echo "   ℹ️  No existing server found"
fi

# Activate virtual environment
source .venv/bin/activate

# Start server
echo "   Starting server..."
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 > /tmp/hiva-ai.log 2>&1 &
NEW_PID=$!

sleep 3

# Verify server started
if ps -p $NEW_PID > /dev/null 2>&1; then
    echo "   ✓ Server started (PID: $NEW_PID)"
    echo ""
    echo "✅ Server restarted successfully!"
    echo ""
    echo "📋 Test the endpoint:"
    echo "   curl https://api.hiva.chat/api/v1/clinical-pph/health"
    echo ""
    echo "📄 Logs: tail -f /tmp/hiva-ai.log"
else
    echo "   ✗ Server failed to start. Check logs: /tmp/hiva-ai.log"
    exit 1
fi
