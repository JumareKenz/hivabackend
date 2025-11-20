# Chrome DevTools 404 - Not an Error

## What You're Seeing

```
GET /.well-known/appspecific/com.chrome.devtools.json 404 in 452ms
```

## This is Normal!

This is **NOT an error** with your chatbot. It's a request that Chrome DevTools makes automatically when you have the browser developer tools open.

### Why It Happens

- Chrome DevTools automatically requests this file to check for developer tools configuration
- Your server doesn't have this file (which is fine)
- It returns a 404 (not found), which is expected
- This doesn't affect your chatbot functionality at all

### How to Ignore It

1. **In Next.js**: Add this to your `next.config.js` to suppress the warning:

```javascript
module.exports = {
  async rewrites() {
    return [
      {
        source: '/.well-known/:path*',
        destination: '/api/404',
      },
    ];
  },
};
```

2. **Or simply ignore it**: It's harmless and doesn't affect functionality

### Check Your Actual Chatbot

The 404 is unrelated to your chatbot. To test if your chatbot is working:

```bash
curl -X POST http://YOUR_SERVER_IP:8000/api/v1/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "hello", "session_id": "test123"}'
```

If you get a response, your chatbot is working fine!

## Real Errors to Watch For

If you see errors like:
- `500 Internal Server Error`
- `Network error`
- `Failed to fetch`
- `Connection refused`

Those are actual errors that need fixing. The Chrome DevTools 404 is not one of them.

