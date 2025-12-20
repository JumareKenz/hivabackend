#!/usr/bin/env python3
"""
Test RunPod LLM connection
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.services.llm_client import llm_client
from app.core.config import settings


async def test_runpod():
    """Test RunPod LLM connection"""
    print("=" * 70)
    print("RUNPOD LLM CONNECTION TEST")
    print("=" * 70)
    print()
    
    print("📋 Configuration:")
    print(f"   Base URL: {settings.RUNPOD_BASE_URL}")
    print(f"   API Key: {'✅ Set' if settings.RUNPOD_API_KEY else '❌ Not set'}")
    print(f"   Model: {settings.LLM_MODEL}")
    print(f"   Timeout: {settings.LLM_TIMEOUT}s")
    print()
    
    if not settings.RUNPOD_API_KEY:
        print("⚠️  RUNPOD_API_KEY is not set in .env file")
        print("   Add it to /root/hiva/services/ai/.env:")
        print("   RUNPOD_API_KEY=your_api_key_here")
        print()
        return False
    
    try:
        endpoint_url = llm_client._get_endpoint_url()
        is_openai = llm_client._is_openai_compatible(endpoint_url)
        
        print(f"🔗 Endpoint URL: {endpoint_url}")
        print(f"   Format: {'OpenAI-compatible' if is_openai else 'Standard RunPod'}")
        if is_openai:
            print(f"   API Endpoint: {endpoint_url}/completions")
        print()
        
        print("🧪 Testing LLM generation with simple prompt...")
        test_prompt = "Generate a simple SQL SELECT query to get the first 10 rows from a table called 'users'."
        
        response = await llm_client.generate(
            prompt=test_prompt,
            temperature=0.1,
            max_tokens=200
        )
        
        print("✅ LLM Response received!")
        print()
        print("📝 Response:")
        print("-" * 70)
        print(response)
        print("-" * 70)
        print()
        print("✅ RunPod LLM connection is working!")
        return True
        
    except ValueError as e:
        print(f"❌ Configuration error: {e}")
        return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        print()
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_runpod())
    sys.exit(0 if success else 1)






