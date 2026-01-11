#!/usr/bin/env python3
"""
NGINX Configuration Generator
Generates production-safe NGINX configuration for discovered AI services.
"""

import json
import sys
from pathlib import Path
from typing import List, Dict
from dataclasses import dataclass


@dataclass
class ServiceConfig:
    """Service configuration for NGINX"""
    subdomain: str
    port: int
    service_name: str
    health_endpoint: str


class NGINXConfigGenerator:
    """Generates secure NGINX configuration"""
    
    def __init__(self, base_domain: str = "api.hiva.chat", ssl_enabled: bool = True, cloudflare_enabled: bool = True):
        self.base_domain = base_domain
        self.ssl_enabled = ssl_enabled
        self.cloudflare_enabled = cloudflare_enabled
        
        # Cloudflare IP ranges (IPv4 and IPv6)
        self.cloudflare_ips_v4 = [
            "173.245.48.0/20",
            "103.21.244.0/22",
            "103.22.200.0/22",
            "103.31.4.0/22",
            "141.101.64.0/18",
            "108.162.192.0/18",
            "190.93.240.0/20",
            "188.114.96.0/20",
            "197.234.240.0/22",
            "198.41.128.0/17",
            "162.158.0.0/15",
            "104.16.0.0/13",
            "104.24.0.0/14",
            "172.64.0.0/13",
            "131.0.72.0/22"
        ]
        
        self.cloudflare_ips_v6 = [
            "2400:cb00::/32",
            "2606:4700::/32",
            "2803:f800::/32",
            "2405:b500::/32",
            "2405:8100::/32",
            "2a06:98c0::/29",
            "2c0f:f248::/32"
        ]
        
    def generate_server_block(self, service: ServiceConfig) -> str:
        """Generate a server block for a single service"""
        # If base_domain is api.hiva.chat, create subdomains like hiva-ai.api.hiva.chat
        # Otherwise use standard subdomain.base_domain format
        if self.base_domain.startswith("api."):
            server_name = f"{service.subdomain}.{self.base_domain}"
        else:
            server_name = f"{service.subdomain}.{self.base_domain}"
        upstream_name = f"backend_{service.subdomain.replace('-', '_')}"
        
        config = f"""
# ============================================================================
# Service: {service.service_name}
# Port: {service.port}
# Subdomain: {service.subdomain}.{self.base_domain}
# ============================================================================

upstream {upstream_name} {{
    server 127.0.0.1:{service.port};
    keepalive 32;
    keepalive_requests 100;
    keepalive_timeout 60s;
}}

server {{
    listen 80;
    server_name {server_name};
    
    # Handle OPTIONS preflight requests BEFORE redirect (CORS requirement)
    location / {{
        if ($request_method = OPTIONS) {{
            add_header Access-Control-Allow-Origin "$http_origin" always;
            add_header Access-Control-Allow-Methods "GET, POST, PUT, DELETE, OPTIONS, PATCH" always;
            add_header Access-Control-Allow-Headers "Authorization, Content-Type, Accept, Origin, X-Requested-With" always;
            add_header Access-Control-Allow-Credentials "true" always;
            add_header Access-Control-Max-Age "3600" always;
            add_header Content-Length "0";
            add_header Content-Type "text/plain";
            return 204;
        }}
        
        # Redirect HTTP to HTTPS if SSL is enabled (but not for OPTIONS)
        {'return 301 https://$server_name$request_uri;' if self.ssl_enabled else 'return 404;'}
    }}
}}

"""
        
        if self.ssl_enabled:
            config += f"""
server {{
    listen 443 ssl http2;
    server_name {server_name};
    
    # SSL Configuration
    # Note: With Cloudflare, use 'api.hiva.chat' for certificate path
    # Cloudflare handles SSL termination, so this is for direct connections
    ssl_certificate /etc/letsencrypt/live/api.hiva.chat/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.hiva.chat/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384';
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
"""
            
            # Add SSL stapling based on Cloudflare
            if self.cloudflare_enabled:
                config += "    # SSL stapling disabled for Cloudflare (handled by Cloudflare)\n"
            else:
                config += "    ssl_stapling on;\n"
                config += "    ssl_stapling_verify on;\n"
            
            # Build headers based on Cloudflare
            real_ip_header = "proxy_set_header X-Real-IP $cf_connecting_ip;" if self.cloudflare_enabled else "proxy_set_header X-Real-IP $remote_addr;"
            forwarded_for_header = "proxy_set_header X-Forwarded-For $cf_connecting_ip;" if self.cloudflare_enabled else "proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;"
            cf_headers = ""
            if self.cloudflare_enabled:
                cf_headers = """        proxy_set_header CF-Connecting-IP $cf_connecting_ip;
        proxy_set_header CF-Ray $cf_ray;
        proxy_set_header CF-Country $cf_country;
"""
            
            limit_zone = service.subdomain.replace('-', '_')
            
            config += f"""    
    # CORS Headers - Handle preflight OPTIONS requests first
    # This must be before other location blocks to catch OPTIONS early
    if ($request_method = OPTIONS) {{
        add_header Access-Control-Allow-Origin "$http_origin" always;
        add_header Access-Control-Allow-Methods "GET, POST, PUT, DELETE, OPTIONS, PATCH, HEAD" always;
        add_header Access-Control-Allow-Headers "Authorization, Content-Type, X-Requested-With, Accept, Origin" always;
        add_header Access-Control-Allow-Credentials "true" always;
        add_header Access-Control-Max-Age "3600" always;
        add_header Content-Length "0";
        add_header Content-Type "text/plain";
        return 204;
    }}
    
    # CORS Headers for all responses
    add_header Access-Control-Allow-Origin "$http_origin" always;
    add_header Access-Control-Allow-Credentials "true" always;
    add_header Access-Control-Expose-Headers "*" always;
    
    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline';" always;
    
    # Rate Limiting Zone (per service)
    limit_req_zone $binary_remote_addr zone=limit_{limit_zone}:10m rate=10r/s;
    limit_req zone=limit_{limit_zone} burst=20 nodelay;
    
    # Request size limits
    client_max_body_size 10M;
    client_body_buffer_size 128k;
    
    # Timeouts
    proxy_connect_timeout 60s;
    proxy_send_timeout 300s;
    proxy_read_timeout 300s;
    send_timeout 300s;
    
    # Logging (service-specific)
    access_log /var/log/nginx/{service.subdomain}_access.log;
    error_log /var/log/nginx/{service.subdomain}_error.log;
    
    # Handle OPTIONS preflight requests
    location / {{
        if ($request_method = OPTIONS) {{
            add_header Access-Control-Allow-Origin "$http_origin" always;
            add_header Access-Control-Allow-Methods "GET, POST, PUT, DELETE, OPTIONS, PATCH" always;
            add_header Access-Control-Allow-Headers "Authorization, Content-Type, Accept, Origin, X-Requested-With" always;
            add_header Access-Control-Allow-Credentials "true" always;
            add_header Access-Control-Max-Age "3600" always;
            add_header Content-Length "0";
            add_header Content-Type "text/plain";
            return 204;
        }}
        
        # Method allow-list (GET, POST, OPTIONS, HEAD)
        if ($request_method !~ ^(GET|POST|OPTIONS|HEAD)$) {{
            return 405;
        }}
        
        # Rate limiting
        limit_req zone=limit_{limit_zone} burst=20 nodelay;
        
        # Proxy configuration
        proxy_pass http://{upstream_name};
        proxy_http_version 1.1;
        
        # Connection management
        proxy_set_header Connection "";
        proxy_set_header Host $host;
        
        # Real IP handling (Cloudflare-aware)
        {real_ip_header}
        {forwarded_for_header}
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Request-ID $request_id;
        
        # Cloudflare headers (if enabled)
{cf_headers}        # Prevent header injection
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Server $host;
        
        # Buffering
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
        proxy_busy_buffers_size 8k;
        
        # No caching for API endpoints
        proxy_cache_bypass $http_upgrade;
        add_header Cache-Control "no-store, no-cache, must-revalidate" always;
    }}
    
    # Block internal paths and metadata
    location ~ ^/(\\.|internal|admin|debug|metrics|healthz|readyz) {{
        deny all;
        return 404;
    }}
    
    # Health check endpoint (allow)
    location = /health {{
        proxy_pass http://{upstream_name}/health;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host $host;
        {real_ip_header}
        {forwarded_for_header}
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Request-ID $request_id;
        
        # Health checks should be fast
        proxy_connect_timeout 5s;
        proxy_read_timeout 5s;
        
        access_log off;
    }}
    
    # Reject unknown hosts
    if ($host !~ ^({server_name})$ ) {{
        return 444;
    }}
}}
"""
        
        return config
    
    def generate_cloudflare_config(self) -> str:
        """Generate Cloudflare-specific configuration"""
        if not self.cloudflare_enabled:
            return ""
        
        # Build set_real_ip_from directives
        set_real_ip_from = ""
        for ip in self.cloudflare_ips_v4:
            set_real_ip_from += f"    set_real_ip_from {ip};\n"
        for ip in self.cloudflare_ips_v6:
            set_real_ip_from += f"    set_real_ip_from {ip};\n"
        
        return f"""
# ============================================================================
# Cloudflare Configuration
# ============================================================================

# Cloudflare Real IP Configuration
real_ip_header CF-Connecting-IP;
{set_real_ip_from}
real_ip_recursive on;

# Map Cloudflare headers
map $http_cf_connecting_ip $cf_connecting_ip {{
    default $http_cf_connecting_ip;
    "" $remote_addr;
}}

map $http_cf_ray $cf_ray {{
    default $http_cf_ray;
    "" "-";
}}

map $http_cf_country $cf_country {{
    default $http_cf_country;
    "" "-";
}}

"""
    
    def generate_main_api_server_block(self, services: List[ServiceConfig]) -> str:
        """Generate main api.hiva.chat server block that routes to services"""
        # Find dcal-ai-engine service for /api/queues/* routing
        dcal_service = None
        for service in services:
            if 'dcal' in service.service_name.lower() or 'dcal' in service.subdomain.lower():
                dcal_service = service
                break
        
        if not dcal_service:
            return ""
        
        upstream_name = f"backend_{dcal_service.subdomain.replace('-', '_')}"
        real_ip_header = "proxy_set_header X-Real-IP $cf_connecting_ip;" if self.cloudflare_enabled else "proxy_set_header X-Real-IP $remote_addr;"
        forwarded_for_header = "proxy_set_header X-Forwarded-For $cf_connecting_ip;" if self.cloudflare_enabled else "proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;"
        cf_headers = ""
        if self.cloudflare_enabled:
            cf_headers = """        proxy_set_header CF-Connecting-IP $cf_connecting_ip;
        proxy_set_header CF-Ray $cf_ray;
        proxy_set_header CF-Country $cf_country;
"""
        
        config = f"""
# ============================================================================
# Main API Server Block: {self.base_domain}
# Routes /api/queues/* to dcal-ai-engine service
# ============================================================================

server {{
    listen 80;
    server_name {self.base_domain};
    
    # Handle OPTIONS preflight requests BEFORE redirect (CORS requirement)
    location / {{
        if ($request_method = OPTIONS) {{
            add_header Access-Control-Allow-Origin "$http_origin" always;
            add_header Access-Control-Allow-Methods "GET, POST, PUT, DELETE, OPTIONS, PATCH" always;
            add_header Access-Control-Allow-Headers "Authorization, Content-Type, Accept, Origin, X-Requested-With" always;
            add_header Access-Control-Allow-Credentials "true" always;
            add_header Access-Control-Max-Age "3600" always;
            add_header Content-Length "0";
            add_header Content-Type "text/plain";
            return 204;
        }}
        
        # Redirect HTTP to HTTPS if SSL is enabled (but not for OPTIONS)
        {'return 301 https://$server_name$request_uri;' if self.ssl_enabled else 'return 404;'}
    }}
}}

"""
        
        if self.ssl_enabled:
            config += f"""
server {{
    listen 443 ssl http2;
    server_name {self.base_domain};
    
    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/api.hiva.chat/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.hiva.chat/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384';
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
"""
            
            if self.cloudflare_enabled:
                config += "    # SSL stapling disabled for Cloudflare (handled by Cloudflare)\n"
            else:
                config += "    ssl_stapling on;\n"
                config += "    ssl_stapling_verify on;\n"
            
            config += "    # Security Headers\n"
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    
    # CORS Headers (for cross-origin requests)
    add_header Access-Control-Allow-Origin "$http_origin" always;
    add_header Access-Control-Allow-Methods "GET, POST, PUT, DELETE, OPTIONS, PATCH" always;
    add_header Access-Control-Allow-Headers "Authorization, Content-Type, Accept, Origin, X-Requested-With" always;
    add_header Access-Control-Allow-Credentials "true" always;
    
    # Request size limits
    client_max_body_size 10M;
    client_body_buffer_size 128k;
    
    # Timeouts
    proxy_connect_timeout 60s;
    proxy_send_timeout 300s;
    proxy_read_timeout 300s;
    send_timeout 300s;
    
    # Logging
    access_log /var/log/nginx/api_hiva_chat_access.log;
    error_log /var/log/nginx/api_hiva_chat_error.log;
    
    # Route /api/queues/* to dcal-ai-engine service
    location /api/queues {{
        # Handle OPTIONS preflight requests
        if ($request_method = OPTIONS) {{
            add_header Access-Control-Allow-Origin "$http_origin" always;
            add_header Access-Control-Allow-Methods "GET, POST, PUT, DELETE, OPTIONS, PATCH" always;
            add_header Access-Control-Allow-Headers "Authorization, Content-Type, Accept, Origin, X-Requested-With" always;
            add_header Access-Control-Allow-Credentials "true" always;
            add_header Access-Control-Max-Age "3600" always;
            add_header Content-Length "0";
            add_header Content-Type "text/plain";
            return 204;
        }}
        
        # Proxy to dcal-ai-engine
        proxy_pass http://{upstream_name};
        proxy_http_version 1.1;
        
        # Connection management
        proxy_set_header Connection "";
        proxy_set_header Host $host;
        
        # Real IP handling (Cloudflare-aware)
        {real_ip_header}
        {forwarded_for_header}
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Request-ID $request_id;
        
        # Cloudflare headers (if enabled)
{cf_headers}        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Server $host;
        
        # Buffering
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
        proxy_busy_buffers_size 8k;
        
        # No caching for API endpoints
        proxy_cache_bypass $http_upgrade;
        add_header Cache-Control "no-store, no-cache, must-revalidate" always;
    }}
    
    # Default location - return 404 for other paths
    location / {{
        return 404;
    }}
}}
"""
        
        return config
    
    def generate_main_config(self, services: List[ServiceConfig]) -> str:
        """Generate main NGINX configuration"""
        cloudflare_config = self.generate_cloudflare_config()
        
        config = f"""# ============================================================================
# Auto-Generated NGINX Configuration for AI Services
# Base Domain: {self.base_domain}
# Services: {len(services)}
# Cloudflare: {'Enabled' if self.cloudflare_enabled else 'Disabled'}
# Generated: {self._get_timestamp()}
# ============================================================================
# 
# WARNING: This file is auto-generated. Manual edits may be overwritten.
# To regenerate, run: python3 generate_nginx_config.py
#
# ============================================================================

{cloudflare_config}
# Global rate limiting
limit_req_zone $binary_remote_addr zone=global_limit:10m rate=50r/s;

# Request ID for tracing
map $request_id $request_id {{
    default $request_id;
    "" $uuid;
}}

# Logging format (includes Cloudflare info)
log_format service_log '$remote_addr - $remote_user [$time_local] '
                       '"$request" $status $body_bytes_sent '
                       '"$http_referer" "$http_user_agent" '
                       '$request_id $request_time $upstream_response_time '
                       '$cf_connecting_ip $cf_ray $cf_country';
"""

# Default server block (reject unknown hosts)
server {{
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
    
    # Reject all unknown hosts
    return 444;
}}

"""
        
        if self.ssl_enabled:
            config += """
server {
    listen 443 ssl http2 default_server;
    listen [::]:443 ssl http2 default_server;
    server_name _;
    
    # Reject all unknown hosts
    return 444;
}

"""
        
        # Generate main api.hiva.chat server block (if base_domain is api.hiva.chat)
        if self.base_domain == "api.hiva.chat":
            config += self.generate_main_api_server_block(services)
        
        # Generate server blocks for each service
        for service in services:
            config += self.generate_server_block(service)
        
        return config
    
    def _get_timestamp(self) -> str:
        """Get current timestamp"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def generate_config(self, services: List[ServiceConfig], output_path: Path) -> None:
        """Generate and write NGINX configuration"""
        config_content = self.generate_main_config(services)
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(config_content)
        
        print(f"✅ NGINX configuration generated: {output_path}")
        print(f"   Services configured: {len(services)}")
        print(f"   Base domain: {self.base_domain}")


def load_discovery_report(report_path: Path) -> List[ServiceConfig]:
    """Load services from discovery report"""
    with open(report_path, 'r') as f:
        report = json.load(f)
    
    services = []
    for svc_data in report.get('services', []):
        services.append(ServiceConfig(
            subdomain=svc_data['subdomain'],
            port=svc_data['port'],
            service_name=svc_data['service_name'],
            health_endpoint=svc_data['health_endpoint']
        ))
    
    return services


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate NGINX configuration")
    parser.add_argument("--discovery-report", required=True, help="Path to discovery report JSON")
    parser.add_argument("--output", default="/etc/nginx/sites-available/ai-services.conf", 
                       help="Output NGINX config path")
    parser.add_argument("--base-domain", default="api.hiva.chat", help="Base domain")
    parser.add_argument("--no-ssl", action="store_true", help="Disable SSL configuration")
    parser.add_argument("--no-cloudflare", action="store_true", help="Disable Cloudflare configuration")
    parser.add_argument("--dry-run", action="store_true", help="Don't write file, print to stdout")
    
    args = parser.parse_args()
    
    # Load discovery report
    report_path = Path(args.discovery_report)
    if not report_path.exists():
        print(f"❌ Discovery report not found: {report_path}", file=sys.stderr)
        sys.exit(1)
    
    services = load_discovery_report(report_path)
    
    if not services:
        print("❌ No services found in discovery report", file=sys.stderr)
        sys.exit(1)
    
    # Generate configuration
    generator = NGINXConfigGenerator(
        base_domain=args.base_domain,
        ssl_enabled=not args.no_ssl,
        cloudflare_enabled=not args.no_cloudflare
    )
    
    if args.dry_run:
        config = generator.generate_main_config(services)
        print(config)
    else:
        output_path = Path(args.output)
        generator.generate_config(services, output_path)
        print(f"\n📝 Next steps:")
        print(f"   1. Review the configuration: {output_path}")
        print(f"   2. Test syntax: sudo nginx -t")
        print(f"   3. Enable site: sudo ln -sf {output_path} /etc/nginx/sites-enabled/")
        print(f"   4. Reload NGINX: sudo systemctl reload nginx")


if __name__ == "__main__":
    main()
