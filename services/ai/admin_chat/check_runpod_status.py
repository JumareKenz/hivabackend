#!/usr/bin/env python3
"""
Check RunPod endpoint status
"""
import asyncio
import aiohttp
from app.core.config import settings


async def check_runpod_status():
    """Check if RunPod endpoint is accessible"""
    print("=" * 70)
    print("RUNPOD ENDPOINT STATUS CHECK")
    print("=" * 70)
    print()
    
    endpoint_url = settings.RUNPOD_BASE_URL
    if not endpoint_url:
        print("❌ RUNPOD_BASE_URL is not set in configuration")
        return
    
    print(f"Endpoint: {endpoint_url}")
    print(f"Model: {settings.LLM_MODEL}")
    print(f"API Key: {'Set' if settings.RUNPOD_API_KEY else 'Not set'}")
    print()
    
    # Test endpoint
    api_url = f"{endpoint_url.rstrip('/')}/chat/completions"
    payload = {
        "model": settings.LLM_MODEL,
        "messages": [{"role": "user", "content": "Hello, are you working?"}],
        "max_tokens": 10
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.RUNPOD_API_KEY or 'sk-xxx'}"
    }
    
    print("Testing endpoint...")
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.post(api_url, json=payload, headers=headers) as response:
                status = response.status
                print(f"Status Code: {status}")
                
                if status == 200:
                    print("✅ Endpoint is UP and responding!")
                    result = await response.json()
                    print(f"Response: {result.get('choices', [{}])[0].get('message', {}).get('content', 'N/A')[:100]}")
                elif status in [502, 503, 504]:
                    error_text = await response.text()
                    print(f"❌ Endpoint is DOWN (Status {status})")
                    if "<!DOCTYPE html>" in error_text:
                        print("   Cloudflare error page detected - GPU pod is not responding")
                    else:
                        print(f"   Error: {error_text[:200]}")
                    print()
                    print("🔧 ACTION REQUIRED:")
                    print("   1. Go to https://www.runpod.io/console/pods")
                    print("   2. Find pod with endpoint: rqkn8nbdstooo3")
                    print("   3. Check if pod is running (green) or stopped")
                    print("   4. If stopped, click 'Start' to restart the pod")
                    print("   5. Wait 1-2 minutes for pod to fully start")
                else:
                    error_text = await response.text()
                    print(f"⚠️ Unexpected status {status}")
                    print(f"   Error: {error_text[:200]}")
                    
    except asyncio.TimeoutError:
        print("❌ Request timed out - endpoint may be overloaded or down")
    except Exception as e:
        print(f"❌ Error: {str(e)}")
    
    print()
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(check_runpod_status())





