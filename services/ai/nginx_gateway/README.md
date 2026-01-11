# Auto-Discovery NGINX Gateway

A fully automated NGINX reverse-proxy gateway that dynamically discovers all running AI services, identifies their listening ports, and exposes each service through a clean, isolated subdomain.

## 🎯 Features

- **Auto-Discovery**: Automatically detects all running AI services
- **Service Identification**: Resolves service names from environment variables, package names, or FastAPI titles
- **Subdomain Generation**: Creates clean, hyphenated subdomains for each service
- **Security Hardening**: Production-ready security headers, rate limiting, and request validation
- **Failure Isolation**: Each service operates independently with isolated upstreams
- **Verification**: Comprehensive validation and testing before deployment
- **Rollback Support**: Safe rollback to previous configurations

## 📋 Prerequisites

### System Requirements

- Linux system with NGINX installed
- Python 3.8+
- `ss` command (from iproute2 package)
- sudo/root access for NGINX configuration

### Python Dependencies

```bash
pip3 install httpx psutil
```

Or install from requirements file:

```bash
pip3 install -r requirements.txt
```

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd /root/hiva/services/ai/nginx_gateway
pip3 install -r requirements.txt
```

### 2. Run Discovery (Dry Run)

```bash
# Discover services
python3 discover_services.py --base-domain hiva.chat --output discovery_report.json

# Validate services
python3 validate_services.py --discovery-report discovery_report.json

# Generate NGINX config (dry run)
python3 generate_nginx_config.py \
    --discovery-report discovery_report.json \
    --output /tmp/ai-services.conf \
    --dry-run
```

### 3. Deploy

```bash
# Full deployment (with all safety checks)
./deploy_gateway.sh

# Or with custom domain
BASE_DOMAIN=api.example.com ./deploy_gateway.sh

# Dry run (no changes)
DRY_RUN=true ./deploy_gateway.sh
```

## 📖 Detailed Usage

### Step 1: Auto-Discovery

The discovery script scans active listening ports and probes HTTP services:

```bash
python3 discover_services.py \
    --base-domain hiva.chat \
    --timeout 2.0 \
    --output discovery_report.json
```

**Service Name Resolution (Priority Order):**
1. Environment variable `SERVICE_NAME`
2. Python package/directory name
3. FastAPI `app.title`
4. Fallback: `ai-service-<port>`

**Subdomain Convention:**
- Lowercase only
- Hyphenated (underscores/spaces → hyphens)
- No collisions (port appended if conflict)

### Step 2: Service Validation

Validates each discovered service:

```bash
python3 validate_services.py \
    --discovery-report discovery_report.json \
    --output validation_report.json \
    --timeout 5.0 \
    --retries 3 \
    --fail-on-error
```

**Validation Checks:**
- ✅ HTTP 200 response
- ✅ Response stability (multiple requests)
- ✅ Service isolation (concurrent requests)
- ✅ Response time (< 1 second)

### Step 3: Generate NGINX Configuration

Generates production-safe NGINX configuration:

```bash
python3 generate_nginx_config.py \
    --discovery-report discovery_report.json \
    --output /etc/nginx/sites-available/ai-services.conf \
    --base-domain hiva.chat \
    --no-ssl  # Optional: disable SSL config
```

**Security Features:**
- SSL/TLS configuration (Let's Encrypt)
- Security headers (HSTS, X-Frame-Options, CSP, etc.)
- Rate limiting per service
- Method allow-list (GET, POST only)
- Request size limits
- Unknown host rejection
- Header injection prevention
- Service-specific logging

### Step 4: Verify Configuration

Verifies NGINX configuration and tests endpoints:

```bash
python3 verify_nginx.py \
    --config /etc/nginx/sites-available/ai-services.conf \
    --discovery-report discovery_report.json \
    --base-domain hiva.chat \
    --output verification_report.json
```

**Verification Checks:**
- ✅ NGINX configuration syntax
- ✅ Endpoint accessibility via subdomains
- ✅ Log separation per service
- ✅ Graceful failure handling

### Step 5: Deploy

The deployment script orchestrates all steps:

```bash
./deploy_gateway.sh
```

**Deployment Process:**
1. Prerequisites check
2. Service discovery
3. Service validation
4. NGINX config generation
5. Configuration verification
6. NGINX reload

## 🔧 Configuration

### Environment Variables

```bash
# Base domain for subdomains
export BASE_DOMAIN=hiva.chat

# SSL configuration
export SSL_ENABLED=true  # or false

# NGINX paths
export NGINX_CONFIG_DIR=/etc/nginx/sites-available
export NGINX_ENABLED_DIR=/etc/nginx/sites-enabled

# Work directory for reports
export WORK_DIR=/root/hiva/services/ai/nginx_gateway/.work
```

### NGINX Configuration Location

- **Generated Config**: `/etc/nginx/sites-available/ai-services.conf`
- **Enabled Link**: `/etc/nginx/sites-enabled/ai-services.conf`
- **Backups**: `/etc/nginx/sites-available/ai-services.conf.backup.*`

## 🔄 Rollback

Rollback to a previous configuration:

```bash
./rollback.sh
```

The script will:
1. List available backup files
2. Prompt for selection
3. Backup current config
4. Restore selected backup
5. Test and reload NGINX

## 📊 Service Discovery Rules

A service qualifies if:
- ✅ Listening on a TCP port (8000-8999 or 8300)
- ✅ Exposes FastAPI-style HTTP interface
- ✅ Responds successfully to `/health`, `/status`, or `/`

**Service Name Resolution:**
1. `SERVICE_NAME` environment variable
2. Python package/directory name
3. FastAPI `app.title`
4. Fallback: `ai-service-<port>`

**Subdomain Generation:**
- `hiva-ai` → `hiva-ai.hiva.chat`
- `hiva-admin-chat` → `hiva-admin-chat.hiva.chat`
- `dcal-ai-engine` → `dcal-ai-engine.hiva.chat`

## 🔒 Security Features

### Request Security
- Method allow-list (GET, POST, OPTIONS, HEAD)
- Request size limits (10MB)
- Rate limiting per service (10 req/s, burst 20)
- Unknown host rejection (444)

### Headers
- `Strict-Transport-Security`
- `X-Frame-Options: DENY`
- `X-Content-Type-Options: nosniff`
- `X-XSS-Protection`
- `Referrer-Policy`
- `Content-Security-Policy`

### Proxy Security
- Header injection prevention
- Request smuggling protection
- Proper `X-Forwarded-*` headers
- Request ID for tracing

### Isolation
- Independent upstreams per service
- Service-specific logging
- No shared retry loops
- Circuit breaking ready

## 📝 Logging

Service-specific logs are created:

- **Access Logs**: `/var/log/nginx/<subdomain>_access.log`
- **Error Logs**: `/var/log/nginx/<subdomain>_error.log`

Monitor logs:

```bash
# All services
tail -f /var/log/nginx/*_access.log

# Specific service
tail -f /var/log/nginx/hiva-ai_access.log
```

## 🧪 Testing

### Test Discovery

```bash
python3 discover_services.py --base-domain hiva.chat
```

### Test Validation

```bash
python3 validate_services.py \
    --discovery-report .work/discovery_report.json \
    --fail-on-error
```

### Test Endpoints

```bash
# Health check
curl https://hiva-ai.hiva.chat/health

# Root endpoint
curl https://hiva-ai.hiva.chat/
```

### Test Unknown Host

```bash
# Should return 444 or connection refused
curl https://nonexistent.hiva.chat/health
```

## 🐛 Troubleshooting

### No Services Discovered

**Problem**: Discovery finds no services

**Solutions**:
- Check if services are running: `ss -tlnp | grep LISTEN`
- Verify services respond to HTTP: `curl http://localhost:8000/health`
- Check port range (8000-8999 or 8300)

### NGINX Config Syntax Error

**Problem**: `nginx -t` fails

**Solutions**:
- Review generated config: `cat /etc/nginx/sites-available/ai-services.conf`
- Check for missing SSL certificates (if SSL enabled)
- Verify base domain matches SSL certificate

### Services Not Accessible

**Problem**: Subdomains return 502/503

**Solutions**:
- Check service is running: `curl http://localhost:<port>/health`
- Check NGINX error logs: `tail -f /var/log/nginx/<subdomain>_error.log`
- Verify upstream configuration in NGINX config
- Check firewall rules

### SSL Certificate Issues

**Problem**: SSL handshake fails

**Solutions**:
- Verify certificate exists: `ls /etc/letsencrypt/live/<domain>/`
- Check certificate validity: `openssl x509 -in /etc/letsencrypt/live/<domain>/fullchain.pem -text -noout`
- Regenerate certificate if needed: `certbot certonly --nginx -d <domain>`

## 📚 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Auto-Discovery Script                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Port Scanner │→ │ HTTP Probe   │→ │ Name Resolver│      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                  Service Validator                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Health Check │→ │ Stability    │→ │ Isolation   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│              NGINX Config Generator                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Server Blocks│→ │ Security     │→ │ Rate Limits │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                    NGINX Gateway                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Service 1    │  │ Service 2    │  │ Service 3    │      │
│  │ subdomain1   │  │ subdomain2   │  │ subdomain3   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

## 📄 License

This project is part of the HIVA AI platform.

## 🤝 Support

For issues or questions:
1. Check troubleshooting section
2. Review logs: `/var/log/nginx/*.log`
3. Check discovery reports: `.work/*.json`
