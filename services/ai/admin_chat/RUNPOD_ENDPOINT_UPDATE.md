# RunPod Endpoint Configuration Update

## ✅ Configuration Complete

The admin/vanna LLM endpoint has been updated to use the RunPod proxy endpoint.

## 📋 Configuration Details

### Endpoint URL
```
https://eg34f72dqqrmi1-8000.proxy.runpod.net/v1/chat/completions
```

### Configuration Files Updated

1. **`app/core/config.py`**
   - Added `RUNPOD_BASE_URL` with default value: `https://eg34f72dqqrmi1-8000.proxy.runpod.net/v1`
   - Added `RUNPOD_API_KEY` setting
   - Set `LLM_MODEL` to `Qwen/Qwen2.5-14B-Instruct-GPTQ-Int4` (adjust if needed)
   - Groq API kept as fallback option

2. **`app/services/llm_client.py`**
   - Updated to prioritize RunPod endpoint if configured
   - Falls back to Groq API if RunPod not configured
   - Handles endpoint URL construction correctly (handles both base URL and full endpoint URL)

## 🔧 Environment Variables Required

Add to `/root/hiva/services/ai/.env`:

```bash
# RunPod GPU LLM Configuration (Primary)
RUNPOD_API_KEY=your_runpod_api_key_here
RUNPOD_BASE_URL=https://eg34f72dqqrmi1-8000.proxy.runpod.net/v1
LLM_MODEL=Qwen/Qwen2.5-14B-Instruct-GPTQ-Int4

# Groq API Configuration (Fallback - optional)
GROQ_API_KEY=your_groq_api_key_here  # Only needed if RunPod is unavailable
```

## 🚀 How It Works

1. **Primary**: If `RUNPOD_BASE_URL` and `RUNPOD_API_KEY` are set, the system uses RunPod endpoint
2. **Fallback**: If RunPod is not configured, it falls back to Groq API (if `GROQ_API_KEY` is set)

## ✅ Verification

To verify the configuration:

1. Check that the server loads without errors
2. Test a query through the `/api/v1/admin/query` endpoint
3. Check server logs for which provider is being used

## 📝 Notes

- The endpoint URL already includes `/v1`, so the client will append `/chat/completions` to create the full endpoint
- The model name (`Qwen/Qwen2.5-14B-Instruct-GPTQ-Int4`) may need to be adjusted based on what's actually deployed on the RunPod endpoint
- If you need to switch back to Groq, simply remove or comment out `RUNPOD_API_KEY` and `RUNPOD_BASE_URL` in the `.env` file


