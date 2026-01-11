# Clinical PPH - Frontend Connection Guide

**Date:** January 7, 2026  
**Status:** Ready for Frontend Integration

---

## 🔗 API Endpoint

### Base URL

**Local Development:**
```
http://localhost:8000
```

**Production (if configured):**
```
https://api.hiva.chat
# or
http://194.163.168.161:8000
```

### Clinical PPH Endpoint

**Main Query Endpoint:**
```
POST /api/v1/clinical-pph/ask
```

**Full URL Examples:**
- Local: `http://localhost:8000/api/v1/clinical-pph/ask`
- Production: `https://api.hiva.chat/api/v1/clinical-pph/ask`

---

## 📡 Request Format

### POST Request

**Endpoint:** `POST /api/v1/clinical-pph/ask`

**Headers:**
```javascript
{
  "Content-Type": "application/json"
}
```

**Request Body:**
```json
{
  "query": "What are the risk factors for postpartum hemorrhage?",
  "session_id": "optional-session-id",  // Optional, auto-generated if not provided
  "top_k": 5                            // Optional, default: 5
}
```

**Parameters:**
- `query` (required): The clinical question
- `session_id` (optional): For conversation context
- `top_k` (optional): Number of documents to retrieve (default: 5)

---

## 📥 Response Format

### Success Response

```json
{
  "answer": "Risk factors for postpartum hemorrhage include...",
  "session_id": "session-id",
  "kb_id": "clinical_pph",
  "kb_name": "Clinical PPH (Postpartum Hemorrhage)"
}
```

### Error Response

```json
{
  "error": "Error message here",
  "session_id": "session-id"
}
```

---

## 💻 Frontend Integration Examples

### React/Next.js Example

```javascript
// utils/clinicalPPH.js
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function askClinicalPPH(query, sessionId = null) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/clinical-pph/ask`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        query,
        session_id: sessionId,
        top_k: 5
      }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Request failed');
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Clinical PPH API error:', error);
    throw error;
  }
}

// Usage in component
import { askClinicalPPH } from '@/utils/clinicalPPH';

async function handleQuery(userQuery) {
  try {
    const result = await askClinicalPPH(userQuery, 'user-session-123');
    console.log('Answer:', result.answer);
    return result.answer;
  } catch (error) {
    console.error('Error:', error.message);
    return 'Sorry, I encountered an error. Please try again.';
  }
}
```

### Vue.js Example

```javascript
// composables/useClinicalPPH.js
import { ref } from 'vue';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export function useClinicalPPH() {
  const loading = ref(false);
  const error = ref(null);

  const ask = async (query, sessionId = null) => {
    loading.value = true;
    error.value = null;

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/clinical-pph/ask`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query,
          session_id: sessionId,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Request failed');
      }

      const data = await response.json();
      return data;
    } catch (err) {
      error.value = err.message;
      throw err;
    } finally {
      loading.value = false;
    }
  };

  return {
    ask,
    loading,
    error,
  };
}

// Usage in component
<script setup>
import { useClinicalPPH } from '@/composables/useClinicalPPH';

const { ask, loading, error } = useClinicalPPH();

async function handleSubmit() {
  try {
    const result = await ask(userQuery.value, sessionId.value);
    answer.value = result.answer;
  } catch (err) {
    console.error('Error:', err);
  }
}
</script>
```

### Vanilla JavaScript Example

```javascript
// clinicalPPH.js
const API_BASE_URL = 'http://localhost:8000';

async function askClinicalPPH(query, sessionId = null) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/clinical-pph/ask`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        query: query,
        session_id: sessionId,
      }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Request failed');
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Clinical PPH API error:', error);
    throw error;
  }
}

// Usage
askClinicalPPH('What is postpartum hemorrhage?', 'user-123')
  .then(result => {
    console.log('Answer:', result.answer);
  })
  .catch(error => {
    console.error('Error:', error);
  });
```

---

## 🌐 CORS Configuration

The backend is configured to allow these origins:

- ✅ `https://hiva.chat`
- ✅ `https://api.hiva.chat`
- ✅ `http://localhost:3000` (Next.js default)
- ✅ `http://localhost:5173` (Vite default)
- ✅ `https://hiva-two.vercel.app`

**If your frontend domain is not listed**, add it to `/root/hiva/services/ai/app/core/config.py`:

```python
ALLOWED_ORIGINS: list = [
    "https://hiva.chat",
    "https://your-frontend-domain.com",  # Add your domain here
    # ...
]
```

Then restart the API service.

---

## 🔧 Environment Variables

### For Next.js/Vercel

**`.env.local` or Vercel Environment Variables:**
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
# or for production:
NEXT_PUBLIC_API_URL=https://api.hiva.chat
```

### For Vite

**`.env.local`:**
```bash
VITE_API_URL=http://localhost:8000
# or for production:
VITE_API_URL=https://api.hiva.chat
```

---

## 🏥 Health Check Endpoint

**Endpoint:** `GET /api/v1/clinical-pph/health`

**Example:**
```javascript
async function checkHealth() {
  const response = await fetch('http://localhost:8000/api/v1/clinical-pph/health');
  const data = await response.json();
  console.log('Status:', data.status);
  console.log('Collection count:', data.collection_count);
  return data;
}
```

**Response:**
```json
{
  "status": "healthy",
  "kb_id": "clinical_pph",
  "kb_name": "Clinical PPH (Postpartum Hemorrhage)",
  "collection_count": 9,
  "cache_stats": {
    "cache_size": 0,
    "max_cache_size": 256,
    "cache_utilization": 0.0
  }
}
```

---

## ⚡ Performance Considerations

### Response Time
- **Average:** 1-3 seconds
- **Model:** Groq GPT OSS 120B (approved clinical model)
- **Rate Limit:** 8,000 TPM (sufficient for 5-10 users)

### Best Practices
1. **Show loading state** during query (1-3 seconds)
2. **Handle errors gracefully** (rate limits, network errors)
3. **Use session_id** for conversation context
4. **Cache responses** for repeated queries (optional)

---

## 🚨 Error Handling

### Common Errors

**429 Rate Limit:**
```json
{
  "error": "Rate limit reached. Please try again in a few seconds."
}
```
**Solution:** Wait and retry, or implement exponential backoff.

**500 Server Error:**
```json
{
  "error": "Internal server error"
}
```
**Solution:** Check API logs, verify model configuration.

**400 Bad Request:**
```json
{
  "answer": "Please provide a query.",
  "session_id": "session-id"
}
```
**Solution:** Ensure `query` field is provided and not empty.

---

## 📝 Example: Complete React Component

```jsx
import { useState } from 'react';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function ClinicalPPHChat() {
  const [query, setQuery] = useState('');
  const [answer, setAnswer] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [sessionId] = useState(() => `session-${Date.now()}`);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError(null);
    setAnswer('');

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/clinical-pph/ask`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: query,
          session_id: sessionId,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Request failed');
      }

      const data = await response.json();
      setAnswer(data.answer);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="clinical-pph-chat">
      <form onSubmit={handleSubmit}>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask a clinical question about PPH..."
          disabled={loading}
        />
        <button type="submit" disabled={loading || !query.trim()}>
          {loading ? 'Asking...' : 'Ask'}
        </button>
      </form>

      {error && <div className="error">Error: {error}</div>}

      {loading && <div className="loading">Loading...</div>}

      {answer && (
        <div className="answer">
          <h3>Answer:</h3>
          <p>{answer}</p>
        </div>
      )}
    </div>
  );
}
```

---

## ✅ Quick Start Checklist

- [ ] Set API base URL in environment variables
- [ ] Add CORS origin if using custom domain
- [ ] Implement error handling
- [ ] Add loading states
- [ ] Test with sample query
- [ ] Verify health endpoint
- [ ] Monitor rate limits (if high volume)

---

## 📞 Support

**API Endpoint:** `POST /api/v1/clinical-pph/ask`  
**Health Check:** `GET /api/v1/clinical-pph/health`  
**Base URL:** `http://localhost:8000` (local) or `https://api.hiva.chat` (production)

**Documentation:**
- Implementation: `/root/hiva/services/ai/clinical_pph/IMPLEMENTATION_COMPLETE.md`
- Configuration: `/root/hiva/services/ai/clinical_pph/CLINICAL_LLM_CONFIG_UPDATE.md`

---

**Status:** ✅ Ready for Frontend Integration  
**Model:** Groq GPT OSS 120B (Approved Clinical Model)  
**Response Time:** 1-3 seconds average
