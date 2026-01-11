#!/bin/bash
# DCAL API Server Startup Script
# Starts the FastAPI server on port 8300

echo "🚀 Starting DCAL Admin Portal API Server on port 8300..."
echo ""
echo "Environment: ${ENVIRONMENT:-development}"
echo "Host: 0.0.0.0"
echo "Port: 8300"
echo ""

cd "$(dirname "$0")"

# Check if virtual environment exists
if [ -d "venv" ]; then
    echo "✅ Activating virtual environment..."
    source venv/bin/activate
fi

# Check if dependencies are installed
if ! python3 -c "import fastapi" 2>/dev/null; then
    echo "⚠️  FastAPI not found. Installing dependencies..."
    pip install -r requirements.txt
fi

echo ""
echo "Starting server..."
echo "---"
echo "📍 API Endpoints:"
echo "   - Health Check: http://localhost:8300/health"
echo "   - API Docs: http://localhost:8300/docs"
echo "   - OpenAPI Spec: http://localhost:8300/openapi.json"
echo ""
echo "🔒 Security:"
echo "   - JWT Authentication: Enabled"
echo "   - RBAC: Enabled"
echo "   - HMAC Signing: Enabled"
echo ""
echo "Press Ctrl+C to stop the server"
echo "---"
echo ""

# Start the server with uvicorn
uvicorn src.api.main:app \
    --host 0.0.0.0 \
    --port 8300 \
    --reload \
    --log-level info

# Note: Remove --reload for production
# Add --workers 4 for production deployment

