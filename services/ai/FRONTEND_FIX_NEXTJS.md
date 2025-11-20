# Next.js Frontend Streaming Fix

## 🐛 Error

```
Error: failed to pipe response
TypeError [ERR_INVALID_STATE]: Invalid state: Controller is already closed
```

This happens when the ReadableStream controller is closed multiple times or the stream handling is incorrect.

## ✅ Fixed Next.js API Route

Replace your `app/api/chat/route.ts` with this corrected version:

```typescript
import { NextRequest } from 'next/server';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { query, session_id, branch_id } = body;

    // Forward request to backend
    const backendResponse = await fetch(`${API_BASE_URL}/api/v1/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        query,
        session_id: session_id || crypto.randomUUID(),
        branch_id,
      }),
    });

    if (!backendResponse.ok) {
      return new Response(
        JSON.stringify({ error: 'Backend request failed' }),
        { status: backendResponse.status }
      );
    }

    // Create a ReadableStream to pipe the backend response
    const stream = new ReadableStream({
      async start(controller) {
        const reader = backendResponse.body?.getReader();
        const decoder = new TextDecoder();

        if (!reader) {
          controller.close();
          return;
        }

        try {
          while (true) {
            const { done, value } = await reader.read();
            
            if (done) {
              controller.close();
              break;
            }

            // Encode and push the chunk
            controller.enqueue(value);
          }
        } catch (error) {
          // Only close if not already closed
          try {
            controller.close();
          } catch (e) {
            // Controller already closed, ignore
          }
        } finally {
          // Clean up reader
          try {
            reader.releaseLock();
          } catch (e) {
            // Already released, ignore
          }
        }
      },
      cancel() {
        // Handle cancellation
      },
    });

    return new Response(stream, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no',
      },
    });
  } catch (error) {
    console.error('Stream error:', error);
    return new Response(
      JSON.stringify({ error: 'Internal server error' }),
      { status: 500 }
    );
  }
}
```

## 🔧 Alternative: Simpler Version (Recommended)

This version is simpler and less error-prone:

```typescript
import { NextRequest } from 'next/server';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { query, session_id, branch_id } = body;

    // Forward request to backend
    const backendResponse = await fetch(`${API_BASE_URL}/api/v1/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        query,
        session_id: session_id || crypto.randomUUID(),
        branch_id,
      }),
    });

    if (!backendResponse.ok) {
      return new Response(
        JSON.stringify({ error: 'Backend request failed' }),
        { status: backendResponse.status }
      );
    }

    // Simply pipe the backend response
    return new Response(backendResponse.body, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no',
      },
    });
  } catch (error) {
    console.error('Stream error:', error);
    return new Response(
      JSON.stringify({ error: 'Internal server error' }),
      { status: 500 }
    );
  }
}
```

## 🎯 Even Better: Direct Connection (No Proxy)

Instead of proxying through Next.js, connect directly from the frontend:

```typescript
// In your frontend component
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

async function streamChat(query: string, sessionId: string, branchId?: string) {
  const response = await fetch(`${API_URL}/api/v1/stream`, {
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

  if (!response.ok) {
    throw new Error('Request failed');
  }

  const reader = response.body?.getReader();
  const decoder = new TextDecoder();

  if (!reader) {
    throw new Error('No reader available');
  }

  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const data = JSON.parse(line.slice(6));
          if (data.type === 'chunk') {
            // Handle chunk
            onChunk(data.content);
          } else if (data.type === 'done') {
            return;
          } else if (data.type === 'error') {
            throw new Error(data.error);
          }
        } catch (e) {
          console.error('Parse error:', e);
        }
      }
    }
  }
}
```

## 🔍 Key Fixes

1. **No double closing**: Check if controller is already closed before closing
2. **Proper error handling**: Wrap in try-catch and handle cleanup
3. **Reader cleanup**: Release lock in finally block
4. **Simpler approach**: Direct pipe instead of manual stream handling

## 🚀 Recommended Solution

**Use direct connection** (no Next.js proxy):
- Simpler code
- Fewer errors
- Better performance
- Less latency

Just make sure CORS is configured (which we already did).

## 📝 Environment Variables

Make sure you have:

```bash
# .env.local
NEXT_PUBLIC_API_URL=http://YOUR_SERVER_IP:8000
```

## 🧪 Testing

Test the fixed route:

```bash
curl -X POST http://localhost:3000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "session_id": "test123"}'
```

Or test direct connection:

```bash
curl -X POST http://YOUR_SERVER_IP:8000/api/v1/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "session_id": "test123"}'
```

