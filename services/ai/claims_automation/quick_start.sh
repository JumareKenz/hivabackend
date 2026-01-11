#!/bin/bash
# DCAL Quick Start Script

echo "=========================================="
echo "🚀 DCAL Quick Start - Port 8300"
echo "=========================================="
echo ""

cd /root/hiva/services/ai/claims_automation

# Check if dependencies installed
echo "📦 Checking dependencies..."
if ! python3 -c "import fastapi" 2>/dev/null; then
    echo "⚠️  FastAPI not found"
    echo "📥 Installing dependencies (this may take 2-3 minutes)..."
    echo ""
    pip3 install -r requirements.txt
    echo ""
    echo "✅ Dependencies installed"
else
    echo "✅ Dependencies already installed"
fi

echo ""
echo "🌐 Starting DCAL server on port 8300..."
echo ""

# Start server in background
uvicorn src.api.main:app --host 0.0.0.0 --port 8300 --reload > server_output.log 2>&1 &
SERVER_PID=$!

echo "   Server PID: $SERVER_PID"
echo "   Waiting for startup..."

# Wait for server to be ready
sleep 6

echo ""
echo "🧪 Testing endpoints..."
echo ""

# Test health endpoint
echo "1. Testing health check..."
if curl -s http://localhost:8300/health > /dev/null 2>&1; then
    echo "   ✅ Health endpoint responsive"
    curl -s http://localhost:8300/health | python3 -m json.tool 2>/dev/null || curl -s http://localhost:8300/health
else
    echo "   ❌ Health endpoint not responding"
    echo ""
    echo "   Check logs: tail server_output.log"
fi

echo ""
echo "2. Testing API info..."
if curl -s http://localhost:8300/api/info > /dev/null 2>&1; then
    echo "   ✅ API info endpoint responsive"
else
    echo "   ⚠️  API info endpoint not responding"
fi

echo ""
echo "=========================================="
echo "✅ DCAL Server Status"
echo "=========================================="
echo ""
echo "Server PID: $SERVER_PID"
echo "Port: 8300"
echo ""
echo "📍 Access Points:"
echo "   • Health Check: http://localhost:8300/health"
echo "   • API Docs: http://localhost:8300/docs"
echo "   • API Info: http://localhost:8300/api/info"
echo ""
echo "📋 Commands:"
echo "   • View logs: tail -f server_output.log"
echo "   • Stop server: kill $SERVER_PID"
echo "   • Check status: curl http://localhost:8300/health"
echo ""
echo "=========================================="
echo ""

# Save PID for easy stopping
echo $SERVER_PID > server.pid
echo "Server PID saved to server.pid"
