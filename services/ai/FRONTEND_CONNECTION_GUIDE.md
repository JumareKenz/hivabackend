# Frontend Connection Guide - HIVA AI

## 🔗 Quick Start

Your backend is running at: **http://194.163.168.161:8000**

## 📡 API Endpoints

### Base URL
```
http://194.163.168.161:8000
# or (if you have a domain configured)
https://api.hiva.chat
```

### Main Endpoints

1. **Streaming Chat** (Recommended for real-time responses)
   ```
   POST /api/v1/stream
   ```

2. **Non-Streaming Chat** (Simple request/response)
   ```
   POST /api/v1/ask
   ```

3. **Health Check**
   ```
   GET /health
   ```

## 💻 Frontend Integration Examples

### React/Next.js Example

```javascript
// utils/api.js
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://194.163.168.161:8000';

// Streaming Chat Function
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

// Usage in React Component
import { useState } from 'react';
import { streamChat } from '@/utils/api';

export default function ChatComponent() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [sessionId] = useState(() => `session-${Date.now()}`);

  const handleSend = async () => {
    if (!input.trim()) return;

    const userMessage = { role: 'user', content: input };
    setMessages(prev => [...prev, userMessage]);
    setInput('');

    const assistantMessage = { role: 'assistant', content: '' };
    setMessages(prev => [...prev, assistantMessage]);

    try {
      for await (const chunk of streamChat(input, sessionId)) {
        setMessages(prev => {
          const newMessages = [...prev];
          newMessages[newMessages.length - 1].content += chunk;
          return newMessages;
        });
      }
    } catch (error) {
      console.error('Chat error:', error);
      setMessages(prev => {
        const newMessages = [...prev];
        newMessages[newMessages.length - 1].content = 'Error: ' + error.message;
        return newMessages;
      });
    }
  };

  return (
    <div className="chat-container">
      <div className="messages">
        {messages.map((msg, idx) => (
          <div key={idx} className={`message ${msg.role}`}>
            {msg.content}
          </div>
        ))}
      </div>
      <div className="input-area">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && handleSend()}
          placeholder="Type your message..."
        />
        <button onClick={handleSend}>Send</button>
      </div>
    </div>
  );
}
```

### Simple Fetch Example (Non-Streaming)

```javascript
async function sendMessage(query, sessionId) {
  const response = await fetch('http://194.163.168.161:8000/api/v1/ask', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      query,
      session_id: sessionId,
    }),
  });

  const data = await response.json();
  return data.answer;
}

// Usage
const answer = await sendMessage('What is enrollment?', 'user-123');
console.log(answer);
```

## 🌐 CORS Configuration

The backend is already configured to allow these origins:
- ✅ `https://hiva.chat`
- ✅ `https://api.hiva.chat`
- ✅ `https://hiva-two.vercel.app`
- ✅ `http://localhost:3000` (Next.js)
- ✅ `http://localhost:5173` (Vite)
- ✅ `http://localhost:8080`

If your frontend domain is not listed, add it to `/root/hiva/services/ai/app/core/config.py`:

```python
ALLOWED_ORIGINS: list = [
    "https://hiva.chat",
    "https://your-frontend-domain.com",  # Add your domain here
    # ...
]
```

Then restart the service:
```bash
systemctl restart hiva.service
```

## 🔧 Environment Variables

### For Vercel/Production

Add to your Vercel project settings or `.env.production`:

```bash
NEXT_PUBLIC_API_URL=http://194.163.168.161:8000
# or if you have a domain:
NEXT_PUBLIC_API_URL=https://api.hiva.chat
```

### For Local Development

Create `.env.local`:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## 📊 Request/Response Format

### Request Format

```json
{
  "query": "What is the enrollment process?",
  "session_id": "user-123",  // Optional, auto-generated if not provided
  "branch_id": "kano"         // Optional, for branch-specific context
}
```

### Streaming Response Format

```
data: {"type": "chunk", "content": "Enrollment is", "session_id": "user-123"}

data: {"type": "chunk", "content": " open to all", "session_id": "user-123"}

data: {"type": "done", "session_id": "user-123"}
```

### Non-Streaming Response Format

```json
{
  "answer": "Enrollment is open to all residents...",
  "session_id": "user-123"
}
```

## 🧪 Testing the Connection

### Test Health Endpoint

```bash
curl http://194.163.168.161:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "model": "openai/gpt-oss-20b",
  "backend": "Groq API",
  "endpoint": "https://api.groq.com/openai/v1"
}
```

### Test Streaming Endpoint

```bash
curl -X POST http://194.163.168.161:8000/api/v1/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "Hello", "session_id": "test123"}'
```

### Test Non-Streaming Endpoint

```bash
curl -X POST http://194.163.168.161:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "Hello", "session_id": "test123"}'
```

## 🐛 Troubleshooting

### CORS Errors

**Error**: `Access to fetch at '...' from origin '...' has been blocked by CORS policy`

**Solution**:
1. Check your frontend origin is in `ALLOWED_ORIGINS` in `app/core/config.py`
2. Restart the backend: `systemctl restart hiva.service`
3. Check browser console for the exact origin being blocked

### Connection Refused

**Error**: `Failed to fetch` or `Connection refused`

**Solution**:
1. Verify backend is running: `systemctl status hiva.service`
2. Check if port 8000 is open: `curl http://194.163.168.161:8000/health`
3. Verify firewall allows port 8000
4. Check API URL in frontend matches the server IP

### Empty Responses

If you get empty responses, the model might be returning reasoning content. The client handles this automatically, but you can check the raw response in browser DevTools Network tab.

## 🔒 Security Recommendations

1. **Use HTTPS in Production**: Set up SSL/TLS for your API endpoint
2. **Add Rate Limiting**: Consider adding rate limiting for production use
3. **API Key Authentication**: Add API key validation if needed (currently optional)

## 📝 Quick Checklist

- [ ] Backend is running at `http://194.163.168.161:8000`
- [ ] Health endpoint returns `{"status": "healthy"}`
- [ ] Frontend domain is in `ALLOWED_ORIGINS`
- [ ] `NEXT_PUBLIC_API_URL` is set in frontend environment
- [ ] Test streaming endpoint works
- [ ] Test non-streaming endpoint works

## 🚀 Next Steps

1. Add your frontend domain to CORS if needed
2. Set `NEXT_PUBLIC_API_URL` in your frontend environment
3. Implement the streaming chat component
4. Test with a simple query
5. Monitor for errors in production

Your frontend should now be able to connect! 🎉


