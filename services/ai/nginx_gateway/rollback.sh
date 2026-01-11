#!/bin/bash
#
# NGINX Gateway Rollback Script
# Safely rolls back to previous NGINX configuration
#

set -euo pipefail

# Configuration
NGINX_CONFIG_DIR="${NGINX_CONFIG_DIR:-/etc/nginx/sites-available}"
NGINX_ENABLED_DIR="${NGINX_ENABLED_DIR:-/etc/nginx/sites-enabled}"
CONFIG_FILE="${NGINX_CONFIG_DIR}/ai-services.conf"
ENABLED_LINK="${NGINX_ENABLED_DIR}/ai-services.conf"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

# Find backup files
find_backups() {
    local backups=()
    if [ -f "$CONFIG_FILE" ]; then
        local dir=$(dirname "$CONFIG_FILE")
        local base=$(basename "$CONFIG_FILE")
        for backup in "$dir"/"${base}".backup.*; do
            if [ -f "$backup" ]; then
                backups+=("$backup")
            fi
        done
    fi
    printf '%s\n' "${backups[@]}" | sort -r
}

# Main rollback
main() {
    echo "================================================================================"
    echo "NGINX Gateway Rollback"
    echo "================================================================================"
    echo ""
    
    # Check if config exists
    if [ ! -f "$CONFIG_FILE" ]; then
        log_error "Configuration file not found: $CONFIG_FILE"
        exit 1
    fi
    
    # Find backups
    local backups=($(find_backups))
    
    if [ ${#backups[@]} -eq 0 ]; then
        log_warning "No backup files found"
        log_info "Options:"
        echo "  1. Remove enabled link (disable auto-generated config)"
        echo "  2. Exit without changes"
        echo ""
        read -p "Choose option (1 or 2): " choice
        
        if [ "$choice" = "1" ]; then
            if [ -L "$ENABLED_LINK" ]; then
                log_info "Removing enabled link..."
                sudo rm "$ENABLED_LINK"
                log_success "Enabled link removed"
                
                log_info "Reloading NGINX..."
                if sudo systemctl reload nginx; then
                    log_success "NGINX reloaded"
                else
                    log_error "NGINX reload failed"
                    exit 1
                fi
            else
                log_info "No enabled link to remove"
            fi
        fi
        exit 0
    fi
    
    # Show backups
    log_info "Found ${#backups[@]} backup file(s):"
    for i in "${!backups[@]}"; do
        local backup="${backups[$i]}"
        local timestamp=$(basename "$backup" | sed 's/.*backup\.//')
        echo "  $((i+1)). $backup (${timestamp})"
    done
    echo ""
    
    # Select backup
    read -p "Select backup to restore (1-${#backups[@]}) or 'q' to quit: " choice
    
    if [ "$choice" = "q" ] || [ "$choice" = "Q" ]; then
        log_info "Rollback cancelled"
        exit 0
    fi
    
    local backup_index=$((choice - 1))
    if [ $backup_index -lt 0 ] || [ $backup_index -ge ${#backups[@]} ]; then
        log_error "Invalid selection"
        exit 1
    fi
    
    local selected_backup="${backups[$backup_index]}"
    
    log_info "Restoring from: $selected_backup"
    
    # Backup current config
    local current_backup="${CONFIG_FILE}.rollback.$(date +%Y%m%d_%H%M%S)"
    cp "$CONFIG_FILE" "$current_backup"
    log_success "Current config backed up to: $current_backup"
    
    # Restore backup
    cp "$selected_backup" "$CONFIG_FILE"
    log_success "Configuration restored"
    
    # Test configuration
    log_info "Testing NGINX configuration..."
    if sudo nginx -t; then
        log_success "Configuration test passed"
    else
        log_error "Configuration test failed - restoring previous config"
        cp "$current_backup" "$CONFIG_FILE"
        exit 1
    fi
    
    # Reload NGINX
    log_info "Reloading NGINX..."
    if sudo systemctl reload nginx; then
        log_success "NGINX reloaded successfully"
    else
        log_error "NGINX reload failed - restoring previous config"
        cp "$current_backup" "$CONFIG_FILE"
        sudo systemctl reload nginx
        exit 1
    fi
    
    echo ""
    echo "================================================================================"
    log_success "ROLLBACK COMPLETE"
    echo "================================================================================"
    echo ""
    log_info "Configuration restored from: $selected_backup"
    log_info "Previous config backed up to: $current_backup"
}

# Run main
main "$@"
