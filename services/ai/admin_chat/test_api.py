#!/usr/bin/env python3
"""
Test Admin Chat API endpoints
"""
import asyncio
import aiohttp
import json
from app.core.config import settings


async def test_api():
    """Test the admin chat API"""
    base_url = f"http://{settings.HOST}:{settings.PORT}"
    
    print("=" * 70)
    print("ADMIN CHAT API TEST")
    print("=" * 70)
    print()
    print(f"Testing API at: {base_url}")
    print()
    
    # Test 1: Health check
    print("1️⃣  Testing health endpoint...")
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{base_url}/health") as resp:
            if resp.status == 200:
                data = await resp.json()
                print(f"✅ Health check passed: {data}")
            else:
                print(f"❌ Health check failed: {resp.status}")
    print()
    
    # Test 2: Natural language query
    print("2️⃣  Testing natural language query endpoint...")
    query_data = {
        "query": "Show me the top 5 facilities by claim volume",
        "session_id": "test-session-123"
    }
    
    headers = {}
    if settings.ADMIN_API_KEY:
        headers["X-API-Key"] = settings.ADMIN_API_KEY
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{base_url}/api/v1/admin/query",
            json=query_data,
            headers=headers
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                print("✅ Query successful!")
                print(f"   SQL: {data.get('sql', 'N/A')[:100]}...")
                print(f"   Rows returned: {len(data.get('data', []))}")
                print(f"   Summary: {data.get('summary', 'N/A')[:100]}...")
            else:
                error_text = await resp.text()
                print(f"❌ Query failed: {resp.status}")
                print(f"   Error: {error_text[:200]}")
    print()
    
    # Test 3: Follow-up query with context
    print("3️⃣  Testing follow-up query (with conversation context)...")
    followup_data = {
        "query": "What about facilities in Osun State?",
        "session_id": "test-session-123",
        "refine_query": True
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{base_url}/api/v1/admin/query",
            json=followup_data,
            headers=headers
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                print("✅ Follow-up query successful!")
                sql = data.get('sql') or 'N/A'
                print(f"   SQL: {sql[:100] if isinstance(sql, str) else sql}...")
                result_data = data.get('data') or []
                print(f"   Rows returned: {len(result_data) if result_data else 0}")
            else:
                error_text = await resp.text()
                print(f"❌ Follow-up query failed: {resp.status}")
                print(f"   Error: {error_text[:200]}")
    print()
    
    # Test 4: Schema endpoint
    print("4️⃣  Testing schema endpoint...")
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{base_url}/api/v1/admin/schema",
            headers=headers
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                print("✅ Schema retrieved!")
                print(f"   Tables: {len(data.get('tables', []))}")
                if data.get('tables'):
                    print(f"   Sample table: {data['tables'][0].get('table_name', 'N/A')}")
            else:
                error_text = await resp.text()
                print(f"❌ Schema retrieval failed: {resp.status}")
                print(f"   Error: {error_text[:200]}")
    print()
    
    print("=" * 70)
    print("✅ API TEST COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_api())

