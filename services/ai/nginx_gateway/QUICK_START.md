# Quick Start Guide

## 🚀 5-Minute Setup

### 1. Install Dependencies

```bash
cd /root/hiva/services/ai/nginx_gateway
pip3 install --break-system-packages -r requirements.txt
```

### 2. Run Discovery (Test)

```bash
python3 discover_services.py --base-domain hiva.chat
```

Expected output:
```
Service Name              Port     Subdomain                      Health     Method         
----------------------------------------------------------------------------------------------------
hiva-ai                   8000     hiva-ai                        ✅ Healthy  package_name   
hiva-admin-chat           8001     hiva-admin-chat                ✅ Healthy  package_name   
dcal-ai-engine            8300     dcal-ai-engine                 ✅ Healthy  package_name   
```

### 3. Deploy (Dry Run)

```bash
DRY_RUN=true ./deploy_gateway.sh
```

### 4. Deploy (Production)

```bash
sudo ./deploy_gateway.sh
```

## ✅ Verification

After deployment, test endpoints:

```bash
# Health checks
curl https://hiva-ai.hiva.chat/health
curl https://hiva-admin-chat.hiva.chat/health
curl https://dcal-ai-engine.hiva.chat/health
```

## 🔄 Rollback

If something goes wrong:

```bash
sudo ./rollback.sh
```

## 📋 Common Commands

```bash
# Discover services
python3 discover_services.py --base-domain hiva.chat

# Validate services
python3 validate_services.py --discovery-report .work/discovery_report.json

# Generate config (dry run)
python3 generate_nginx_config.py \
    --discovery-report .work/discovery_report.json \
    --dry-run

# Verify config
python3 verify_nginx.py \
    --config /etc/nginx/sites-available/ai-services.conf \
    --discovery-report .work/discovery_report.json
```

## 🐛 Troubleshooting

**No services discovered?**
- Check services are running: `ss -tlnp | grep LISTEN`
- Verify HTTP responses: `curl http://localhost:8000/health`

**NGINX config error?**
- Test syntax: `sudo nginx -t`
- Check logs: `sudo tail -f /var/log/nginx/error.log`

**Services not accessible?**
- Check service is running: `curl http://localhost:<port>/health`
- Check NGINX logs: `tail -f /var/log/nginx/<subdomain>_error.log`
