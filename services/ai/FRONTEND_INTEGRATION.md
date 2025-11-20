# Frontend Integration Guide

## 🔗 Connecting Your Vercel Frontend

Your frontend at **https://hiva-two.vercel.app/** is now configured to connect to the backend API.

## 📡 API Endpoints

### Base URL
```
http://YOUR_SERVER_IP:8000
# or
https://your-domain.com  (if you have SSL)
```

### Available Endpoints

#### 1. Streaming Chat (Recommended)
```javascript
POST /api/v1/stream
```

#### 2. Non-Streaming Chat
```javascript
POST /api/v1/ask
```

#### 3. Health Check
```javascript
GET /health
```

## 💻 Frontend Integration Examples

### React/Next.js Example

```javascript
// api.js or utils/api.js
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://YOUR_SERVER_IP:8000';

export async function streamChat(query, sessionId, branchId = null) {
  const response = await fetch(`${API_BASE_URL}/api/v1/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      query,
      session_id: sessionId,
      branch_id: branchId, // Optional
    }),
  });

  if (!response.ok) {
    throw new Error('Stream request failed');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  return {
    async *[Symbol.asyncIterator]() {
      let buffer = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop(); // Keep incomplete line in buffer

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.type === 'chunk') {
                yield data.content;
              } else if (data.type === 'done') {
                return;
              }
            } catch (e) {
              console.error('Parse error:', e);
            }
          }
        }
      }
    }
  };
}

// Usage in component
export default function ChatComponent() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [sessionId] = useState(() => crypto.randomUUID());
  const [branchId, setBranchId] = useState(null);

  const handleSend = async () => {
    if (!input.trim()) return;

    const userMessage = { role: 'user', content: input };
    setMessages(prev => [...prev, userMessage]);
    setInput('');

    const assistantMessage = { role: 'assistant', content: '' };
    setMessages(prev => [...prev, assistantMessage]);

    try {
      const stream = await streamChat(input, sessionId, branchId);
      
      for await (const chunk of stream) {
        setMessages(prev => {
          const newMessages = [...prev];
          newMessages[newMessages.length - 1].content += chunk;
          return newMessages;
        });
      }
    } catch (error) {
      console.error('Error:', error);
    }
  };

  return (
    <div>
      {/* Your chat UI */}
      <input 
        value={input} 
        onChange={(e) => setInput(e.target.value)}
        onKeyPress={(e) => e.key === 'Enter' && handleSend()}
      />
      <button onClick={handleSend}>Send</button>
      
      {messages.map((msg, i) => (
        <div key={i}>
          <strong>{msg.role}:</strong> {msg.content}
        </div>
      ))}
    </div>
  );
}
```

### Vue.js Example

```javascript
// composables/useChat.js
import { ref } from 'vue';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://YOUR_SERVER_IP:8000';

export function useChat() {
  const messages = ref([]);
  const sessionId = ref(crypto.randomUUID());
  const branchId = ref(null);

  async function sendMessage(query) {
    const response = await fetch(`${API_BASE_URL}/api/v1/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query,
        session_id: sessionId.value,
        branch_id: branchId.value,
      }),
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    messages.value.push({ role: 'user', content: query });
    messages.value.push({ role: 'assistant', content: '' });

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n\n');
      buffer = lines.pop();

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = JSON.parse(line.slice(6));
          if (data.type === 'chunk') {
            messages.value[messages.value.length - 1].content += data.content;
          }
        }
      }
    }
  }

  return { messages, sendMessage, branchId };
}
```

### Vanilla JavaScript Example

```javascript
// Simple fetch-based streaming
async function streamChat(query, sessionId, branchId = null) {
  const response = await fetch('http://YOUR_SERVER_IP:8000/api/v1/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      query,
      session_id: sessionId,
      branch_id: branchId,
    }),
  });

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n\n');
    buffer = lines.pop();

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = JSON.parse(line.slice(6));
        if (data.type === 'chunk') {
          // Append chunk to UI
          appendToChat(data.content);
        } else if (data.type === 'done') {
          return;
        }
      }
    }
  }
}
```

## 🔧 Environment Variables

### For Vercel Deployment

Add to your Vercel project settings:

```bash
NEXT_PUBLIC_API_URL=http://YOUR_SERVER_IP:8000
# or
NEXT_PUBLIC_API_URL=https://your-domain.com
```

### For Local Development

Create `.env.local`:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## 🌐 CORS Configuration

The backend is configured to allow:
- ✅ `https://hiva-two.vercel.app`
- ✅ `http://localhost:3000` (Next.js default)
- ✅ `http://localhost:5173` (Vite default)

To add more origins, edit `app/core/config.py`:

```python
ALLOWED_ORIGINS: list = [
    "https://hiva-two.vercel.app",
    "https://your-other-domain.com",
    # ...
]
```

## 🔒 Security Considerations

### 1. Use HTTPS in Production

If exposing your API publicly, use:
- Nginx reverse proxy with SSL
- Cloudflare tunnel
- API Gateway with SSL

### 2. API Key Authentication (Optional)

Add API key validation:

```python
# In your endpoints
API_KEY = os.getenv("API_KEY")

@router.post("/stream")
async def stream_endpoint(request: Request):
    api_key = request.headers.get("X-API-Key")
    if api_key != API_KEY:
        raise HTTPException(401, "Invalid API key")
    # ... rest of code
```

### 3. Rate Limiting

Consider adding rate limiting for production.

## 📊 Request/Response Format

### Request
```json
{
  "query": "What is the enrollment process?",
  "session_id": "user-123",  // Optional, auto-generated if not provided
  "branch_id": "kano"         // Optional, auto-detected if not provided
}
```

### Response (Streaming)
```
data: {"type": "chunk", "content": "Enrollment is", "session_id": "user-123"}

data: {"type": "chunk", "content": " open to all", "session_id": "user-123"}

data: {"type": "done", "session_id": "user-123"}
```

### Response (Non-Streaming)
```json
{
  "answer": "Enrollment is open to all residents...",
  "session_id": "user-123"
}
```

## 🐛 Troubleshooting

### CORS Errors

**Error**: `Access to fetch at '...' from origin '...' has been blocked by CORS policy`

**Solution**: 
1. Check your origin is in `ALLOWED_ORIGINS`
2. Restart the backend server
3. Check browser console for exact origin

### Connection Refused

**Error**: `Failed to fetch` or `Connection refused`

**Solution**:
1. Check backend is running: `curl http://YOUR_SERVER_IP:8000/health`
2. Check firewall allows port 8000
3. Verify API URL in frontend

### Streaming Not Working

**Error**: Stream stops or doesn't start

**Solution**:
1. Check browser supports ReadableStream
2. Verify CORS allows streaming
3. Check network tab for errors
4. Try non-streaming endpoint first

## 🚀 Deployment Checklist

- [ ] Backend server is running and accessible
- [ ] CORS configured for your frontend domain
- [ ] API URL set in frontend environment variables
- [ ] Test streaming endpoint works
- [ ] Test branch detection works
- [ ] Monitor for errors in production

## 📞 API Testing

Test your API:

```bash
# Health check
curl http://YOUR_SERVER_IP:8000/health

# Test streaming
curl -X POST http://YOUR_SERVER_IP:8000/api/v1/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "session_id": "test123"}'

# Test non-streaming
curl -X POST http://YOUR_SERVER_IP:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "session_id": "test123"}'
```

Your frontend should now be able to connect! 🎉

