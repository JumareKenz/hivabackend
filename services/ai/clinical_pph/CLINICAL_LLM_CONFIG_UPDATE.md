# Clinical PPH - Approved LLM Configuration Update

**Date:** January 7, 2026  
**Status:** Configuration Update Required

---

## Approved Clinical Models

Based on Groq GPU setup configuration for clinical systems, the **approved models** are:

1. **`openai/gpt-oss-20b`** - Smaller, faster, higher rate limits
2. **`openai/gpt-oss-120b`** - Larger, higher quality, lower rate limits (8000 TPM)

---

## Current Configuration Issue

**Current Model:** `Qwen/Qwen2.5-7B-Instruct-GPTQ-Int4`  
**Status:** ❌ NOT APPROVED for clinical use

**Error:** Model not available or not approved for clinical systems

---

## Recommended Configuration

### Option 1: GPT OSS 120B (Recommended for Quality)

**Best for:** High-quality clinical responses, complex queries

```bash
LLM_API_URL=https://api.groq.com/openai/v1
LLM_MODEL=openai/gpt-oss-120b
LLM_API_KEY=<your-groq-api-key>
```

**Characteristics:**
- ✅ Highest quality responses
- ✅ Better clinical reasoning
- ⚠️ Lower rate limit: 8000 TPM (tokens per minute)
- ⚠️ Slightly slower (but still fast on Groq)

### Option 2: GPT OSS 20B (Recommended for Speed/Volume)

**Best for:** Higher throughput, faster responses, cost efficiency

```bash
LLM_API_URL=https://api.groq.com/openai/v1
LLM_MODEL=openai/gpt-oss-20b
LLM_API_KEY=<your-groq-api-key>
```

**Characteristics:**
- ✅ Higher rate limits
- ✅ Faster responses
- ✅ More cost-effective
- ⚠️ Slightly lower quality than 120B (still excellent)

---

## Update Steps

### 1. Update .env File

```bash
cd /root/hiva/services/ai

# Edit .env file
nano .env  # or use your preferred editor

# Change this line:
# LLM_MODEL=Qwen/Qwen2.5-7B-Instruct-GPTQ-Int4

# To one of these:
LLM_MODEL=openai/gpt-oss-120b  # Recommended for quality
# OR
LLM_MODEL=openai/gpt-oss-20b   # Recommended for speed/volume
```

### 2. Restart API Service

```bash
# Find and kill existing process
pkill -f "uvicorn.*8000"

# Restart with new configuration
cd /root/hiva/services/ai
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 &
```

### 3. Verify Configuration

```bash
cd /root/hiva/services/ai
source .venv/bin/activate
python3 -c "from app.core.config import settings; print(f'Model: {settings.LLM_MODEL}')"
```

**Expected output:**
```
Model: openai/gpt-oss-120b
# OR
Model: openai/gpt-oss-20b
```

### 4. Test Endpoint

```bash
curl -X POST http://localhost:8000/api/v1/clinical-pph/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "What is postpartum hemorrhage?"}'
```

---

## Performance Comparison

| Model | Quality | Speed | Rate Limit | Cost | Best For |
|-------|---------|-------|------------|------|----------|
| **gpt-oss-120b** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 8000 TPM | Medium | High-quality clinical responses |
| **gpt-oss-20b** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Higher | Lower | High-volume, fast responses |
| **qwen2.5:3b (local)** | ⭐⭐⭐ | ⭐⭐ | Unlimited | Free | Development, privacy |

---

## Recommendation

### For Clinical Pilot: **Use `openai/gpt-oss-120b`**

**Rationale:**
- ✅ Approved for clinical use
- ✅ Highest quality responses (critical for clinical safety)
- ✅ Better reasoning for complex clinical queries
- ✅ Rate limit (8000 TPM) sufficient for 5-10 user pilot
- ✅ Fast enough on Groq GPU infrastructure

**If rate limits become an issue**, switch to `openai/gpt-oss-20b` for higher throughput.

---

## Model Availability Check

To verify which models are available with your API key:

```bash
cd /root/hiva/services/ai
source .venv/bin/activate
python3 << 'EOF'
import requests
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env
load_dotenv(Path(".env"))

api_key = os.getenv("GROQ_API_KEY") or os.getenv("LLM_API_KEY")
if not api_key:
    print("No API key found")
    exit(1)

approved_models = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b"
]

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

for model in approved_models:
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json={
                "model": model,
                "messages": [{"role": "user", "content": "Test"}],
                "max_tokens": 5
            },
            timeout=10
        )
        
        if response.status_code == 200:
            print(f"✅ {model}: AVAILABLE")
        elif response.status_code == 404:
            print(f"❌ {model}: NOT FOUND")
        elif response.status_code == 429:
            print(f"⚠️  {model}: RATE LIMITED (but available)")
        else:
            error = response.json().get("error", {}).get("message", "Unknown")
            print(f"⚠️  {model}: {response.status_code} - {error[:60]}")
    except Exception as e:
        print(f"❌ {model}: ERROR - {str(e)[:60]}")
EOF
```

---

## Next Steps

1. ✅ **Update .env** with approved model
2. ✅ **Restart API** service
3. ✅ **Verify** configuration
4. ✅ **Test** endpoint
5. ✅ **Re-run** endpoint validation tests

---

**Status:** Ready for configuration update  
**Action Required:** Update `.env` file with approved model  
**Recommended Model:** `openai/gpt-oss-120b` for clinical pilot
