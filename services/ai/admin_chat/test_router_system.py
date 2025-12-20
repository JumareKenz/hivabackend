"""
Test script for Router System
Tests intent classification and routing
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.services.intent_router import intent_router
from app.services.chat_handler import chat_handler


async def test_intent_classification():
    """Test intent router classification"""
    print("=" * 60)
    print("Intent Router Test")
    print("=" * 60)
    
    test_cases = [
        # CHAT cases
        ("hello", "CHAT"),
        ("hi there", "CHAT"),
        ("how are you", "CHAT"),
        ("what can you do", "CHAT"),
        ("who are you", "CHAT"),
        
        # DATA cases
        ("show me total number of claims", "DATA"),
        ("claims by status", "DATA"),
        ("list all users", "DATA"),
        ("top 10 providers", "DATA"),
        ("statistics for last month", "DATA"),
    ]
    
    print("\nTesting Intent Classification:")
    print("-" * 60)
    
    passed = 0
    failed = 0
    
    for query, expected in test_cases:
        try:
            result = await intent_router.classify_intent(query)
            status = "✅" if result == expected else "❌"
            
            if result == expected:
                passed += 1
            else:
                failed += 1
            
            print(f"{status} Query: '{query}'")
            print(f"   Expected: {expected}, Got: {result}")
            
        except Exception as e:
            print(f"❌ Query: '{query}' - Error: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


async def test_chat_handler():
    """Test chat handler"""
    print("\n" + "=" * 60)
    print("Chat Handler Test")
    print("=" * 60)
    
    test_queries = [
        "hello",
        "how are you",
        "what can you do",
    ]
    
    print("\nTesting Chat Handler:")
    print("-" * 60)
    
    for query in test_queries:
        try:
            result = await chat_handler.handle_chat(query)
            
            if result.get("success"):
                print(f"✅ Query: '{query}'")
                print(f"   Response: {result.get('response', '')[:100]}...")
            else:
                print(f"❌ Query: '{query}' - Failed: {result.get('error')}")
        
        except Exception as e:
            print(f"❌ Query: '{query}' - Error: {e}")
    
    print("\n" + "=" * 60)
    print("Chat Handler Test Complete")
    print("=" * 60)


async def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("Router System Test Suite")
    print("=" * 60)
    
    # Test intent classification
    intent_test = await test_intent_classification()
    
    # Test chat handler
    await test_chat_handler()
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    if intent_test:
        print("✅ All tests passed!")
        return 0
    else:
        print("❌ Some tests failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

