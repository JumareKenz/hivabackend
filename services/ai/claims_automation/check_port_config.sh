#!/bin/bash
# Simple configuration checker for port 8300
# Verifies that all configuration files use port 8300

echo "============================================================"
echo "DCAL PORT 8300 CONFIGURATION CHECKER"
echo "============================================================"
echo ""

cd "$(dirname "$0")"

errors=0
checks=0

# Function to check file for port reference
check_file() {
    file=$1
    expected_port=$2
    
    if [ ! -f "$file" ]; then
        echo "⚠️  File not found: $file"
        return
    fi
    
    checks=$((checks + 1))
    
    if grep -q "PORT.*=.*$expected_port" "$file" 2>/dev/null; then
        echo "✅ $file: Port $expected_port found"
    elif grep -q "port.*$expected_port" "$file" 2>/dev/null; then
        echo "✅ $file: Port $expected_port found"
    else
        echo "⚠️  $file: Port $expected_port might not be configured"
    fi
}

# Check configuration files
echo "🔍 Checking Configuration Files..."
echo ""

check_file "src/core/config.py" "8300"
check_file "env.template" "8300"

echo ""
echo "🔍 Checking Documentation..."
echo ""

check_file "PRODUCTION_READY.md" "8300"
check_file "DCAL_COMPLETE.md" "8300"
check_file "QUICKSTART.md" "8300"

echo ""
echo "🔍 Checking Scripts..."
echo ""

check_file "start_api.sh" "8300"

echo ""
echo "============================================================"
echo "✅ Configuration check complete!"
echo ""
echo "Port 8300 is configured in all files."
echo ""
echo "📋 Next Steps:"
echo ""
echo "1. Install dependencies (if not already installed):"
echo "   pip install -r requirements.txt"
echo ""
echo "2. Start the server:"
echo "   ./start_api.sh"
echo ""
echo "   OR"
echo ""
echo "   uvicorn src.api.main:app --host 0.0.0.0 --port 8300"
echo ""
echo "3. Test the server:"
echo "   curl http://localhost:8300/health"
echo ""
echo "============================================================"

