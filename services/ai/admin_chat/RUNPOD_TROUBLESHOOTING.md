# RunPod Endpoint Troubleshooting

## Current Issue: 502 Bad Gateway

The RunPod GPU endpoint is returning a **502 Bad Gateway** error, which typically means:

1. **GPU Pod is Down**: The RunPod pod may have stopped or crashed
2. **Pod is Restarting**: The pod may be in the process of restarting
3. **Network Issues**: There may be connectivity issues between Cloudflare and the RunPod pod

## Error Details

- **Endpoint**: `https://rqkn8nbdstooo3-8000.proxy.runpod.net/v1/`
- **Error**: 502 Bad Gateway (Cloudflare error page)
- **Model**: `Qwen/Qwen2.5-14B-Instruct-GPTQ-Int4`

## Solutions

### 1. Check RunPod Pod Status

1. Log into your RunPod account
2. Go to **Pods** section
3. Find the pod with endpoint ID: `rqkn8nbdstooo3`
4. Check if the pod is:
   - **Running** (green status)
   - **Stopped** (needs to be started)
   - **Error** (may need to be restarted)

### 2. Restart the Pod

If the pod is stopped or in error state:
1. Click on the pod
2. Click **Stop** (if running)
3. Wait a few seconds
4. Click **Start** to restart the pod
5. Wait for the pod to fully start (usually 1-2 minutes)

### 3. Verify Endpoint URL

Make sure the endpoint URL in `.env` is correct:
```bash
RUNPOD_BASE_URL=https://rqkn8nbdstooo3-8000.proxy.runpod.net/v1/
```

### 4. Test Endpoint Directly

Test if the endpoint is accessible:
```bash
curl -X POST "https://rqkn8nbdstooo3-8000.proxy.runpod.net/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-xxx" \
  -d '{
    "model": "Qwen/Qwen2.5-14B-Instruct-GPTQ-Int4",
    "messages": [{"role": "user", "content": "test"}]
  }'
```

If you get a 502 error, the pod is definitely down.

### 5. Check Pod Logs

In RunPod dashboard:
1. Go to your pod
2. Click **Logs** or **Terminal**
3. Check for any error messages
4. Look for startup errors or crashes

## Automatic Retry Logic

The service now includes automatic retry logic:
- **3 retry attempts** with exponential backoff
- **2s, 4s, 8s** delays between retries
- **User-friendly error messages** when all retries fail

## Alternative: Use a Different Endpoint

If the current endpoint is unreliable, you can:
1. Create a new RunPod pod
2. Update `RUNPOD_BASE_URL` in `.env`
3. Restart the admin chat service

## Service Status Check

Check if the service is handling errors gracefully:
```bash
curl http://194.163.168.161:8001/health
```

The service should still respond even if RunPod is down (it will return errors for queries but remain operational).





