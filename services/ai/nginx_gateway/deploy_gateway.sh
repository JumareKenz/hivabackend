#!/bin/bash
#
# Auto-Discovery NGINX Gateway Deployment Script
# Orchestrates the complete deployment process with safety checks
#

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DOMAIN="${BASE_DOMAIN:-api.hiva.chat}"
NGINX_CONFIG_DIR="${NGINX_CONFIG_DIR:-/etc/nginx/sites-available}"
NGINX_ENABLED_DIR="${NGINX_ENABLED_DIR:-/etc/nginx/sites-enabled}"
WORK_DIR="${WORK_DIR:-${SCRIPT_DIR}/.work}"
SSL_ENABLED="${SSL_ENABLED:-true}"
CLOUDFLARE_ENABLED="${CLOUDFLARE_ENABLED:-true}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    local missing=0
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        log_error "python3 not found"
        missing=1
    fi
    
    # Check required Python packages
    if ! python3 -c "import httpx, psutil" 2>/dev/null; then
        log_error "Required Python packages missing (httpx, psutil)"
        log_info "Install with: pip3 install httpx psutil"
        missing=1
    fi
    
    # Check NGINX
    if ! command -v nginx &> /dev/null; then
        log_error "nginx not found"
        missing=1
    fi
    
    # Check ss command
    if ! command -v ss &> /dev/null; then
        log_error "ss command not found (iproute2 package)"
        missing=1
    fi
    
    if [ $missing -eq 1 ]; then
        log_error "Prerequisites check failed"
        exit 1
    fi
    
    log_success "All prerequisites met"
}

# Create work directory
setup_work_dir() {
    mkdir -p "$WORK_DIR"
    log_success "Work directory: $WORK_DIR"
}

# Step 1: Discovery
step_discovery() {
    log_info "Step 1: Auto-Discovery"
    
    local report_file="${WORK_DIR}/discovery_report.json"
    
    python3 "${SCRIPT_DIR}/discover_services.py" \
        --base-domain "$BASE_DOMAIN" \
        --output "$report_file" \
        --timeout 2.0
    
    if [ ! -f "$report_file" ]; then
        log_error "Discovery failed - report not generated"
        exit 1
    fi
    
    local service_count=$(python3 -c "import json; print(len(json.load(open('$report_file'))['services']))")
    
    if [ "$service_count" -eq 0 ]; then
        log_error "No services discovered"
        exit 1
    fi
    
    log_success "Discovered $service_count service(s)"
    echo "$report_file"
}

# Step 2: Validation
step_validation() {
    log_info "Step 2: Service Validation"
    
    local discovery_report="$1"
    local validation_report="${WORK_DIR}/validation_report.json"
    
    python3 "${SCRIPT_DIR}/validate_services.py" \
        --discovery-report "$discovery_report" \
        --output "$validation_report" \
        --timeout 5.0 \
        --retries 3 \
        --fail-on-error
    
    if [ $? -ne 0 ]; then
        log_error "Service validation failed"
        log_warning "Review validation report: $validation_report"
        exit 1
    fi
    
    log_success "All services validated"
    echo "$validation_report"
}

# Step 3: Generate NGINX Config
step_generate_config() {
    log_info "Step 3: Generate NGINX Configuration"
    
    local discovery_report="$1"
    local config_file="${NGINX_CONFIG_DIR}/ai-services.conf"
    
    # Backup existing config if it exists
    if [ -f "$config_file" ]; then
        local backup_file="${config_file}.backup.$(date +%Y%m%d_%H%M%S)"
        log_info "Backing up existing config to: $backup_file"
        cp "$config_file" "$backup_file"
    fi
    
    local ssl_flag=""
    if [ "$SSL_ENABLED" != "true" ]; then
        ssl_flag="--no-ssl"
    fi
    
    local cloudflare_flag=""
    if [ "$CLOUDFLARE_ENABLED" != "true" ]; then
        cloudflare_flag="--no-cloudflare"
    fi
    
    python3 "${SCRIPT_DIR}/generate_nginx_config.py" \
        --discovery-report "$discovery_report" \
        --output "$config_file" \
        --base-domain "$BASE_DOMAIN" \
        $ssl_flag \
        $cloudflare_flag
    
    if [ ! -f "$config_file" ]; then
        log_error "NGINX config generation failed"
        exit 1
    fi
    
    log_success "NGINX configuration generated: $config_file"
    echo "$config_file"
}

# Step 4: Verify Config
step_verify_config() {
    log_info "Step 4: Verify NGINX Configuration"
    
    local config_file="$1"
    local discovery_report="$2"
    
    # Test syntax (requires sudo)
    log_info "Testing NGINX configuration syntax..."
    if sudo nginx -t -c "$config_file" 2>/dev/null; then
        log_success "Configuration syntax is valid"
    else
        log_warning "Cannot test syntax without sudo (will test after deployment)"
    fi
    
    # Run full verification
    local verification_report="${WORK_DIR}/verification_report.json"
    
    python3 "${SCRIPT_DIR}/verify_nginx.py" \
        --config "$config_file" \
        --discovery-report "$discovery_report" \
        --base-domain "$BASE_DOMAIN" \
        --output "$verification_report" \
        $([ "$SSL_ENABLED" != "true" ] && echo "--no-https")
    
    log_success "Verification complete"
    echo "$verification_report"
}

# Step 5: Deploy
step_deploy() {
    log_info "Step 5: Deploy NGINX Configuration"
    
    local config_file="$1"
    
    # Enable site
    local enabled_link="${NGINX_ENABLED_DIR}/ai-services.conf"
    
    log_info "Enabling site..."
    if [ -L "$enabled_link" ]; then
        log_info "Removing existing symlink"
        sudo rm "$enabled_link"
    fi
    
    sudo ln -sf "$config_file" "$enabled_link"
    log_success "Site enabled: $enabled_link"
    
    # Test configuration
    log_info "Testing NGINX configuration..."
    if sudo nginx -t; then
        log_success "NGINX configuration test passed"
    else
        log_error "NGINX configuration test failed"
        log_info "Removing enabled link..."
        sudo rm "$enabled_link"
        exit 1
    fi
    
    # Reload NGINX
    log_info "Reloading NGINX..."
    if sudo systemctl reload nginx; then
        log_success "NGINX reloaded successfully"
    else
        log_error "NGINX reload failed"
        exit 1
    fi
}

# Main deployment flow
main() {
    echo "================================================================================"
    echo "Auto-Discovery NGINX Gateway Deployment"
    echo "================================================================================"
    echo ""
    echo "Base Domain: $BASE_DOMAIN"
    echo "SSL Enabled: $SSL_ENABLED"
    echo "Cloudflare Enabled: $CLOUDFLARE_ENABLED"
    echo "Work Directory: $WORK_DIR"
    echo ""
    
    # Check prerequisites
    check_prerequisites
    
    # Setup
    setup_work_dir
    
    # Step 1: Discovery
    discovery_report=$(step_discovery)
    
    # Step 2: Validation
    validation_report=$(step_validation "$discovery_report")
    
    # Step 3: Generate Config
    config_file=$(step_generate_config "$discovery_report")
    
    # Step 4: Verify
    verification_report=$(step_verify_config "$config_file" "$discovery_report")
    
    # Step 5: Deploy
    if [ "${DRY_RUN:-false}" != "true" ]; then
        step_deploy "$config_file"
        
        echo ""
        echo "================================================================================"
        log_success "DEPLOYMENT COMPLETE"
        echo "================================================================================"
        echo ""
        log_info "Reports saved in: $WORK_DIR"
        log_info "NGINX config: $config_file"
        echo ""
        log_info "Next steps:"
        echo "  1. Test endpoints via subdomains"
        echo "  2. Monitor logs: tail -f /var/log/nginx/*_access.log"
        echo "  3. Check service health: curl https://<subdomain>.$BASE_DOMAIN/health"
    else
        echo ""
        echo "================================================================================"
        log_info "DRY RUN COMPLETE (no changes deployed)"
        echo "================================================================================"
        echo ""
        log_info "To deploy, run without DRY_RUN=true"
    fi
}

# Run main
main "$@"
