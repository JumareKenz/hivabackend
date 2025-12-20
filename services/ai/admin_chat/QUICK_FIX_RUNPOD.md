# Quick Fix: RunPod Endpoint Down

## Current Status

The RunPod GPU endpoint is returning **502 Bad Gateway** errors, which means the GPU pod is down or not responding.

## Quick Fix Steps

### 1. Check RunPod Dashboard

1. Go to: **https://www.runpod.io/console/pods**
2. Log in to your RunPod account
3. Find the pod with endpoint ID: **rqkn8nbdstooo3**

### 2. Check Pod Status

Look for the pod status:
- 🟢 **Green/Running**: Pod is active (if still getting 502, wait a minute)
- 🔴 **Red/Stopped**: Pod needs to be started
- 🟡 **Yellow/Starting**: Pod is starting up (wait 1-2 minutes)

### 3. Restart the Pod

If the pod is stopped:
1. Click on the pod
2. Click **"Stop"** button (if it's running)
3. Wait 5-10 seconds
4. Click **"Start"** button
5. Wait 1-2 minutes for the pod to fully start

### 4. Verify Pod is Running

After starting, check:
- Pod status shows **"Running"** (green)
- Pod logs show the model is loaded
- No error messages in logs

### 5. Test the Endpoint

Run this command to test:
```bash
cd /root/hiva/services/ai/admin_chat
source venv/bin/activate
python3 check_runpod_status.py
```

You should see: `✅ Endpoint is UP and responding!`

### 6. Test from Admin Dashboard

Once the pod is running, try your query again from the admin dashboard. The service will automatically retry if there are temporary issues.

## Alternative: Create New Pod

If the current pod keeps having issues:

1. **Create a new pod** in RunPod dashboard
2. **Select the same model**: `Qwen/Qwen2.5-14B-Instruct-GPTQ-Int4`
3. **Get the new endpoint URL** (format: `https://XXXXX-8000.proxy.runpod.net/v1/`)
4. **Update `.env` file**:
   ```bash
   cd /root/hiva/services/ai
   nano .env
   # Update RUNPOD_BASE_URL with new endpoint
   ```
5. **Restart the service**:
   ```bash
   sudo systemctl restart hiva-admin-chat
   ```

## Service Status

The admin chat service is running and will:
- ✅ Automatically retry failed requests (3 attempts)
- ✅ Provide clear error messages when the pod is down
- ✅ Work immediately once the pod is back online

## Check Service Logs

To see retry attempts and errors:
```bash
sudo journalctl -u hiva-admin-chat -f
```

Look for messages like:
- `⚠️ RunPod endpoint returned 502 (attempt 1/3). Retrying in 2s...`
- `✅ Query successful` (when pod is back online)





