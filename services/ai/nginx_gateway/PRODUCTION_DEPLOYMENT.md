# Production Deployment Guide - Cloudflare Integration

## 🎯 Overview

This guide covers production deployment of the auto-discovery NGINX gateway with Cloudflare endpoint `api.hiva.chat`.

## 📋 Prerequisites

### 1. Cloudflare Configuration

Ensure your domain is configured in Cloudflare:
- DNS A/AAAA records point to your server IP
- SSL/TLS mode: **Full (strict)** or **Full** (recommended: Full strict)
- Proxy status: **Proxied** (orange cloud)

### 2. Server Requirements

- NGINX installed and running
- SSL certificates (Let's Encrypt) for `api.hiva.chat`
- Python 3.8+ with dependencies installed
- Root/sudo access

### 3. Firewall Configuration

Allow Cloudflare IPs only (recommended for production):

```bash
# Allow Cloudflare IPs
for ip in $(curl -s https://www.cloudflare.com/ips-v4); do
    ufw allow from $ip to any port 80,443
done

for ip in $(curl -s https://www.cloudflare.com/ips-v6); do
    ufw allow from $ip to any port 80,443
done

# Deny direct access (optional but recommended)
ufw deny 80/tcp
ufw deny 443/tcp
```

## 🚀 Deployment Steps

### Step 1: Install Dependencies

```bash
cd /root/hiva/services/ai/nginx_gateway
pip3 install --break-system-packages -r requirements.txt
```

### Step 2: Configure SSL Certificate

```bash
# Install certbot if not already installed
sudo apt-get update
sudo apt-get install certbot python3-certbot-nginx -y

# Obtain certificate for api.hiva.chat
sudo certbot certonly --nginx -d api.hiva.chat

# Verify certificate
sudo certbot certificates
```

### Step 3: Discover Services

```bash
cd /root/hiva/services/ai/nginx_gateway
python3 discover_services.py \
    --base-domain api.hiva.chat \
    --output .work/discovery_report.json
```

Expected output:
```
Service Name              Port     Subdomain                      Health     Method         
----------------------------------------------------------------------------------------------------
hiva-ai                   8000     hiva-ai                        ✅ Healthy  package_name   
hiva-admin-chat           8001     hiva-admin-chat                ✅ Healthy  package_name   
dcal-ai-engine            8300     dcal-ai-engine                 ✅ Healthy  package_name   
```

### Step 4: Validate Services

```bash
python3 validate_services.py \
    --discovery-report .work/discovery_report.json \
    --output .work/validation_report.json \
    --fail-on-error
```

### Step 5: Generate NGINX Configuration

```bash
python3 generate_nginx_config.py \
    --discovery-report .work/discovery_report.json \
    --output /etc/nginx/sites-available/ai-services.conf \
    --base-domain api.hiva.chat
```

### Step 6: Review Configuration

```bash
# Review the generated config
sudo cat /etc/nginx/sites-available/ai-services.conf

# Check for Cloudflare configuration
sudo grep -A 5 "Cloudflare" /etc/nginx/sites-available/ai-services.conf
```

### Step 7: Test Configuration

```bash
# Test NGINX syntax
sudo nginx -t

# If successful, you should see:
# nginx: configuration file /etc/nginx/nginx.conf test is successful
```

### Step 8: Deploy Configuration

```bash
# Enable the site
sudo ln -sf /etc/nginx/sites-available/ai-services.conf /etc/nginx/sites-enabled/

# Remove default site if it conflicts
sudo rm -f /etc/nginx/sites-enabled/default

# Reload NGINX
sudo systemctl reload nginx

# Check status
sudo systemctl status nginx
```

### Step 9: Verify Deployment

```bash
# Test endpoints via Cloudflare
curl -I https://hiva-ai.api.hiva.chat/health
curl -I https://hiva-admin-chat.api.hiva.chat/health
curl -I https://dcal-ai-engine.api.hiva.chat/health

# Check logs
sudo tail -f /var/log/nginx/hiva-ai_access.log
```

## 🔧 Automated Deployment

Use the deployment script:

```bash
cd /root/hiva/services/ai/nginx_gateway

# Set environment variables
export BASE_DOMAIN=api.hiva.chat
export SSL_ENABLED=true
export CLOUDFLARE_ENABLED=true

# Run deployment
sudo ./deploy_gateway.sh
```

## 🌐 Cloudflare DNS Configuration

Configure DNS records in Cloudflare:

### Option 1: Subdomain per Service (Recommended)

```
Type    Name                    Content         Proxy
A       hiva-ai                 <server-ip>     Proxied
A       hiva-admin-chat         <server-ip>     Proxied
A       dcal-ai-engine          <server-ip>     Proxied
```

### Option 2: Wildcard (Alternative)

```
Type    Name                    Content         Proxy
A       *                       <server-ip>     Proxied
```

## 🔒 Security Configuration

### Cloudflare SSL/TLS Settings

1. Go to Cloudflare Dashboard → SSL/TLS
2. Set encryption mode: **Full (strict)**
3. Enable **Always Use HTTPS**
4. Enable **Automatic HTTPS Rewrites**

### NGINX Security Headers

The generated configuration includes:
- `Strict-Transport-Security`
- `X-Frame-Options: DENY`
- `X-Content-Type-Options: nosniff`
- `X-XSS-Protection`
- `Content-Security-Policy`

### Rate Limiting

Each service has independent rate limiting:
- **Normal rate**: 10 requests/second
- **Burst**: 20 requests

Adjust in generated config if needed.

## 📊 Monitoring

### Check Service Health

```bash
# Health check script
for service in hiva-ai hiva-admin-chat dcal-ai-engine; do
    echo "Checking $service..."
    curl -s https://${service}.api.hiva.chat/health | jq .
done
```

### Monitor Logs

```bash
# All services
sudo tail -f /var/log/nginx/*_access.log

# Specific service
sudo tail -f /var/log/nginx/hiva-ai_access.log

# Errors only
sudo tail -f /var/log/nginx/*_error.log
```

### Check Real IP

Verify Cloudflare real IP is working:

```bash
# Check access log for CF-Connecting-IP
sudo tail -n 100 /var/log/nginx/hiva-ai_access.log | grep -o 'CF-Connecting-IP=[^ ]*'
```

## 🔄 Maintenance

### Update Service Discovery

When services are added/removed:

```bash
cd /root/hiva/services/ai/nginx_gateway
sudo ./deploy_gateway.sh
```

### Rollback

If something goes wrong:

```bash
sudo ./rollback.sh
```

### SSL Certificate Renewal

Certbot auto-renews, but verify:

```bash
# Test renewal
sudo certbot renew --dry-run

# Manual renewal
sudo certbot renew
sudo systemctl reload nginx
```

## 🐛 Troubleshooting

### Services Not Accessible

1. **Check Cloudflare DNS**: Verify DNS records are correct
2. **Check SSL Mode**: Ensure "Full (strict)" is enabled
3. **Check NGINX**: `sudo nginx -t` and `sudo systemctl status nginx`
4. **Check Logs**: `sudo tail -f /var/log/nginx/*_error.log`

### Real IP Not Working

1. **Verify Cloudflare IPs**: Check if server IP is in Cloudflare ranges
2. **Check Headers**: `curl -H "CF-Connecting-IP: 1.2.3.4" https://api.hiva.chat/health`
3. **Review Config**: `sudo grep -A 10 "real_ip" /etc/nginx/sites-available/ai-services.conf`

### SSL Certificate Issues

1. **Check Certificate**: `sudo certbot certificates`
2. **Renew Certificate**: `sudo certbot renew`
3. **Verify Path**: Ensure certificate path matches in config

## ✅ Verification Checklist

After deployment, verify:

- [ ] All services discoverable
- [ ] All services validated
- [ ] NGINX config syntax valid
- [ ] SSL certificates valid
- [ ] Services accessible via Cloudflare
- [ ] Real IP detection working
- [ ] Security headers present
- [ ] Rate limiting active
- [ ] Logs separated per service
- [ ] Health checks passing

## 📞 Support

For issues:
1. Check logs: `/var/log/nginx/*.log`
2. Review discovery reports: `.work/*.json`
3. Test endpoints directly: `curl http://localhost:<port>/health`
4. Verify Cloudflare settings in dashboard

---

**Production Ready**: ✅  
**Cloudflare Integration**: ✅  
**SSL/TLS**: ✅  
**Security Hardened**: ✅
