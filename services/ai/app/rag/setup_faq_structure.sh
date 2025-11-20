#!/bin/bash
# Helper script to set up FAQ directory structure for 9 branches

FAQ_DIR="/root/hiva/services/ai/app/rag/faqs"

echo "📁 Setting up FAQ directory structure..."

# Create main directories
mkdir -p "$FAQ_DIR"
mkdir -p "$FAQ_DIR/branches"

# Create directories for 9 branches (customize these names)
branches=("lagos" "abuja" "port-harcourt" "kano" "ibadan" "benin" "calabar" "enugu" "kaduna")

for branch in "${branches[@]}"; do
    mkdir -p "$FAQ_DIR/branches/$branch"
    echo "✓ Created directory for: $branch"
done

echo ""
echo "✅ Directory structure created!"
echo ""
echo "📝 Next steps:"
echo "1. Upload your general FAQs to: $FAQ_DIR/"
echo "2. Upload branch-specific FAQs to: $FAQ_DIR/branches/{branch_name}/"
echo "3. Run: python -m app.rag.ingest"
echo ""
echo "📁 Current structure:"
tree -L 2 "$FAQ_DIR" 2>/dev/null || find "$FAQ_DIR" -type d | head -20

