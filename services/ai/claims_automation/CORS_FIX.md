# CORS Fix Applied - Frontend Integration

## ✅ Changes Made

### 1. FastAPI CORS Configuration Updated
**File**: `src/api/main.py`

- Explicitly allows `http://localhost:3000` and other development origins
- Added proper CORS headers including `Access-Control-Allow-Credentials`
- Configured to handle OPTIONS preflight requests correctly
- Added `max_age=3600` to cache preflight responses

### 2. NGINX Configuration Generator Updated
**File**: `/root/hiva/services/ai/nginx_gateway/generate_nginx_config.py`

- Added OPTIONS request handling in HTTP server block (before redirect)
- Added CORS headers to HTTPS server block
- Prevents redirect of OPTIONS requests (which breaks CORS preflight)

## 🔧 Cloudflare Configuration (If Applicable)

If you're using Cloudflare in front of your API:

### Option 1: Disable "Always Use HTTPS" for Development
1. Go to Cloudflare Dashboard → SSL/TLS
2. Set **Always Use HTTPS** to **Off** (for development)
3. Or create a Page Rule to exclude OPTIONS requests from redirect

### Option 2: Use HTTPS in Frontend (Recommended)
Update your frontend to use `https://api.hiva.chat` instead of `http://api.hiva.chat`

### Option 3: Cloudflare Page Rule
Create a Page Rule:
- **URL Pattern**: `*api.hiva.chat/api/*`
- **Setting**: **Disable Always Use HTTPS** (for OPTIONS requests)

## 🧪 Testing

### Test CORS Preflight
```bash
curl -X OPTIONS http://localhost:8300/api/queues/summary \
  -H "Origin: http://localhost:3000" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: Authorization" \
  -v
```

Expected response:
- Status: 204 No Content
- Headers: `Access-Control-Allow-Origin`, `Access-Control-Allow-Methods`, etc.

### Test Actual Request
```bash
TOKEN="your-bearer-token"
curl -X GET http://localhost:8300/api/queues/summary \
  -H "Origin: http://localhost:3000" \
  -H "Authorization: Bearer $TOKEN" \
  -v
```

## 📝 Frontend Configuration

### Update API Base URL
If using HTTPS:
```typescript
const API_BASE_URL = 'https://api.hiva.chat';
```

If using HTTP (development only):
```typescript
const API_BASE_URL = 'http://api.hiva.chat';
```

### Fetch Example
```typescript
const response = await fetch(`${API_BASE_URL}/api/queues/summary`, {
  method: 'GET',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
  },
  credentials: 'include', // Important for CORS with credentials
});
```

## 🚀 Next Steps

1. **Restart FastAPI Server** (already done)
2. **Regenerate NGINX Config** (if using nginx):
   ```bash
   cd /root/hiva/services/ai/nginx_gateway
   python3 generate_nginx_config.py \
     --discovery-report .work/discovery_report.json \
     --output /etc/nginx/sites-available/ai-services.conf
   sudo nginx -t
   sudo systemctl reload nginx
   ```
3. **Update Cloudflare Settings** (if applicable)
4. **Test from Frontend** - The CORS error should be resolved

## ⚠️ Important Notes

- **Development**: CORS allows all origins (`*`) for flexibility
- **Production**: CORS is restricted to specific allowed origins
- **Credentials**: `allow_credentials=True` requires specific origins (not `*`)
- **HTTPS**: Always use HTTPS in production for security

## 🔍 Troubleshooting

If CORS errors persist:

1. **Check Browser Console** - Look for specific CORS error messages
2. **Verify Headers** - Use browser DevTools → Network → Headers
3. **Test Directly** - Use `curl` to test API without browser CORS
4. **Check Cloudflare** - Verify redirect settings if using Cloudflare
5. **Check NGINX Logs** - `sudo tail -f /var/log/nginx/*_error.log`

## ✅ Verification Checklist

- [x] FastAPI CORS middleware updated
- [x] NGINX config generator updated
- [x] FastAPI server restarted
- [ ] NGINX config regenerated (if using nginx)
- [ ] Cloudflare settings updated (if using Cloudflare)
- [ ] Frontend updated to use correct API URL
- [ ] CORS preflight test passes
- [ ] Actual API request works from frontend
