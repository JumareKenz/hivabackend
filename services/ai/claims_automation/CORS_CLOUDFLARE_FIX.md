# CORS Error Fix - Cloudflare Redirect Issue

## 🔴 Problem

The error `"Redirect is not allowed for a preflight request"` occurs because:
1. Frontend sends OPTIONS preflight to `http://api.hiva.chat`
2. Cloudflare's "Always Use HTTPS" redirects HTTP → HTTPS
3. Browser cannot follow redirects for preflight requests (security feature)
4. CORS check fails

## ✅ Solutions

### Solution 1: Use HTTPS in Frontend (RECOMMENDED - Immediate Fix)

**Update your frontend API base URL:**

```typescript
// Before (causes CORS error)
const API_BASE_URL = 'http://api.hiva.chat';

// After (works correctly)
const API_BASE_URL = 'https://api.hiva.chat';
```

**Why this works:**
- No redirect needed (already HTTPS)
- Preflight request goes directly to HTTPS endpoint
- CORS headers are returned correctly

### Solution 2: Configure Cloudflare Page Rule

If you must use HTTP for development:

1. Go to Cloudflare Dashboard → Rules → Page Rules
2. Create a new Page Rule:
   - **URL Pattern**: `*api.hiva.chat/api/*`
   - **Setting**: **Disable Always Use HTTPS**
   - **Priority**: Higher than default "Always Use HTTPS" rule

**Note**: This allows HTTP but is less secure. Use only for development.

### Solution 3: Disable "Always Use HTTPS" Globally (NOT RECOMMENDED)

1. Cloudflare Dashboard → SSL/TLS → Edge Certificates
2. Set **Always Use HTTPS** to **Off**

**Warning**: This disables HTTPS redirects for all domains. Not recommended for production.

## 🧪 Verification

### Test HTTPS Endpoint
```bash
curl -X OPTIONS https://api.hiva.chat/api/queues/summary \
  -H "Origin: http://localhost:3000" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: Authorization" \
  -v
```

Expected: 204 No Content with CORS headers

### Test with Bearer Token
```bash
TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
curl -X GET https://api.hiva.chat/api/queues/summary \
  -H "Origin: http://localhost:3000" \
  -H "Authorization: Bearer $TOKEN" \
  -v
```

## 📝 Frontend Code Update

### Update API Client

**File**: `dcal-client.ts` or your API client file

```typescript
// Update base URL to use HTTPS
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.hiva.chat';

// Or for development with local server:
// const API_BASE_URL = process.env.NODE_ENV === 'production' 
//   ? 'https://api.hiva.chat' 
//   : 'http://localhost:8300';
```

### Update Environment Variables

**.env.local** or **.env**:
```bash
NEXT_PUBLIC_API_URL=https://api.hiva.chat
```

## 🔧 Backend CORS Configuration (Already Fixed)

The FastAPI server now properly handles CORS:
- ✅ Allows `http://localhost:3000`
- ✅ Handles OPTIONS preflight requests
- ✅ Returns proper CORS headers
- ✅ Supports credentials

## 🚀 Quick Fix Steps

1. **Update Frontend API URL** to use `https://api.hiva.chat`
2. **Test the endpoint** - CORS error should be resolved
3. **Verify in browser console** - No more CORS errors

## ⚠️ Important Notes

- **HTTPS is required** when using Cloudflare with "Always Use HTTPS" enabled
- **HTTP works locally** (localhost:8300) but not through Cloudflare
- **Credentials require HTTPS** in production
- **CORS preflight cannot follow redirects** - this is a browser security feature

## 🔍 Troubleshooting

If errors persist after switching to HTTPS:

1. **Check SSL Certificate**: Ensure `api.hiva.chat` has valid SSL certificate
2. **Check Cloudflare SSL Mode**: Should be "Full (strict)" or "Full"
3. **Verify CORS Headers**: Use browser DevTools → Network → Headers
4. **Test Directly**: Use `curl` to test without browser CORS restrictions

## ✅ Status

- [x] FastAPI CORS configuration updated
- [x] OPTIONS preflight handling verified
- [ ] Frontend updated to use HTTPS
- [ ] Cloudflare configuration verified (if needed)
- [ ] End-to-end test from frontend

---

**Next Action**: Update your frontend to use `https://api.hiva.chat` instead of `http://api.hiva.chat`
