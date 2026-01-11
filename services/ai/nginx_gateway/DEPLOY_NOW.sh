#!/bin/bash
#
# Production Deployment Script - Cloudflare Ready
# Deploys the auto-discovery NGINX gateway with api.hiva.chat endpoint
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "================================================================================"
echo "Production Deployment - Cloudflare Integration"
echo "================================================================================"
echo ""
echo "This will deploy the NGINX gateway with:"
echo "  - Base Domain: api.hiva.chat"
echo "  - Cloudflare: Enabled"
echo "  - SSL: Enabled"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Please run as root or with sudo"
    exit 1
fi

# Set production environment
export BASE_DOMAIN=api.hiva.chat
export SSL_ENABLED=true
export CLOUDFLARE_ENABLED=true
export DRY_RUN=false

# Run deployment
echo "🚀 Starting deployment..."
echo ""

./deploy_gateway.sh

echo ""
echo "================================================================================"
echo "✅ Deployment Complete"
echo "================================================================================"
echo ""
echo "Next steps:"
echo "  1. Configure DNS in Cloudflare:"
echo "     - hiva-ai.api.hiva.chat → <server-ip> (Proxied)"
echo "     - hiva-admin-chat.api.hiva.chat → <server-ip> (Proxied)"
echo "     - dcal-ai-engine.api.hiva.chat → <server-ip> (Proxied)"
echo ""
echo "  2. Set Cloudflare SSL/TLS mode to 'Full (strict)'"
echo ""
echo "  3. Test endpoints:"
echo "     curl https://hiva-ai.api.hiva.chat/health"
echo "     curl https://hiva-admin-chat.api.hiva.chat/health"
echo "     curl https://dcal-ai-engine.api.hiva.chat/health"
echo ""
echo "  4. Monitor logs:"
echo "     tail -f /var/log/nginx/*_access.log"
echo ""
