# Production Hardening Notes

## 🔒 Security Checklist

### Pre-Deployment

- [ ] SSL certificates installed and valid
- [ ] Firewall rules configured
- [ ] NGINX user permissions verified
- [ ] Log rotation configured
- [ ] Monitoring/alerting setup

### Post-Deployment

- [ ] All endpoints accessible via HTTPS
- [ ] Security headers present in responses
- [ ] Rate limiting active
- [ ] Unknown hosts rejected
- [ ] Service-specific logs working

## 🚨 Security Features

### Rate Limiting

Each service has independent rate limiting:
- **Normal rate**: 10 requests/second
- **Burst**: 20 requests
- **Zone size**: 10MB per service

Adjust in generated config if needed:

```nginx
limit_req_zone $binary_remote_addr zone=limit_service:10m rate=10r/s;
limit_req zone=limit_service burst=20 nodelay;
```

### Request Size Limits

- **Max body size**: 10MB
- **Buffer size**: 128KB

Adjust if services need larger payloads:

```nginx
client_max_body_size 50M;
client_body_buffer_size 256k;
```

### Timeouts

- **Connect**: 60s
- **Send**: 300s
- **Read**: 300s
- **Keep-alive**: 60s

Adjust for long-running requests:

```nginx
proxy_read_timeout 600s;
proxy_send_timeout 600s;
```

## 📊 Monitoring

### Health Checks

Monitor service health:

```bash
# Check all services
for svc in hiva-ai hiva-admin-chat dcal-ai-engine; do
    curl -s https://${svc}.hiva.chat/health | jq .
done
```

### Log Monitoring

Set up log rotation:

```bash
# /etc/logrotate.d/nginx-ai-services
/var/log/nginx/*_access.log
/var/log/nginx/*_error.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    sharedscripts
    postrotate
        systemctl reload nginx > /dev/null 2>&1 || true
    endscript
}
```

### Metrics

Monitor NGINX metrics:

```bash
# Active connections
ss -tn | grep :443 | wc -l

# Request rate
tail -f /var/log/nginx/*_access.log | pv -l > /dev/null
```

## 🔄 Maintenance

### Regular Tasks

1. **Weekly**: Review access logs for anomalies
2. **Monthly**: Verify SSL certificate expiration
3. **Quarterly**: Review and update rate limits
4. **As needed**: Update service discovery

### Certificate Renewal

Let's Encrypt certificates auto-renew, but verify:

```bash
# Check expiration
openssl x509 -in /etc/letsencrypt/live/hiva.chat/fullchain.pem -noout -dates

# Test renewal
certbot renew --dry-run
```

### Service Updates

When services are updated:

1. Run discovery: `python3 discover_services.py`
2. Validate: `python3 validate_services.py`
3. Regenerate config: `python3 generate_nginx_config.py`
4. Deploy: `./deploy_gateway.sh`

## 🚨 Incident Response

### Service Down

1. Check service directly: `curl http://localhost:<port>/health`
2. Check NGINX logs: `tail -f /var/log/nginx/<subdomain>_error.log`
3. Check upstream: `nginx -T | grep -A 5 upstream`
4. Restart service if needed

### NGINX Issues

1. Test config: `sudo nginx -t`
2. Check error log: `tail -f /var/log/nginx/error.log`
3. Rollback if needed: `./rollback.sh`
4. Restart NGINX: `sudo systemctl restart nginx`

### Security Incident

1. Review access logs: `grep <IP> /var/log/nginx/*_access.log`
2. Check for rate limit violations
3. Block IP if needed: `iptables -A INPUT -s <IP> -j DROP`
4. Update firewall rules

## 📈 Performance Tuning

### Connection Pooling

Adjust keepalive settings:

```nginx
upstream backend {
    keepalive 64;  # Increase for high traffic
    keepalive_requests 1000;
    keepalive_timeout 120s;
}
```

### Buffering

Optimize buffering for large responses:

```nginx
proxy_buffering on;
proxy_buffer_size 8k;
proxy_buffers 16 8k;
proxy_busy_buffers_size 16k;
```

### Worker Processes

Tune NGINX workers in `/etc/nginx/nginx.conf`:

```nginx
worker_processes auto;
worker_connections 4096;
```

## ✅ Verification Checklist

After deployment, verify:

- [ ] All services discoverable
- [ ] All services validated
- [ ] NGINX config syntax valid
- [ ] All endpoints accessible
- [ ] SSL certificates valid
- [ ] Security headers present
- [ ] Rate limiting active
- [ ] Logs separated per service
- [ ] Unknown hosts rejected
- [ ] Rollback procedure tested

## 📞 Emergency Contacts

- **NGINX Admin**: Check system administrator
- **SSL Issues**: Check Let's Encrypt status
- **Service Issues**: Check individual service logs
