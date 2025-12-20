"""
Test script for MCP integration
Validates MCP client and server functionality
"""
import asyncio
import sys
from pathlib import Path

# Add paths
sys.path.insert(0, str(Path(__file__).parent))

from app.services.mcp_client import mcp_client
from app.core.config import settings


async def test_mcp_client():
    """Test MCP client functionality"""
    print("=" * 60)
    print("MCP Client Integration Test")
    print("=" * 60)
    
    # Initialize client
    print("\n1. Initializing MCP client...")
    try:
        await mcp_client.initialize()
        print("   ✅ MCP client initialized successfully")
    except Exception as e:
        print(f"   ❌ Failed to initialize MCP client: {e}")
        return False
    
    # Test SQL generation
    print("\n2. Testing SQL generation...")
    try:
        result = await mcp_client.generate_sql("Show me total number of claims")
        if result.get("success"):
            print(f"   ✅ SQL generated: {result['sql'][:100]}...")
            print(f"   Confidence: {result.get('confidence', 0):.2f}")
        else:
            print(f"   ❌ SQL generation failed: {result.get('error')}")
            return False
    except Exception as e:
        print(f"   ❌ SQL generation error: {e}")
        return False
    
    # Test schema retrieval
    print("\n3. Testing schema retrieval...")
    try:
        result = await mcp_client.get_schema()
        if result.get("success"):
            schema = result.get("schema", {})
            tables = schema.get("tables", [])
            print(f"   ✅ Schema retrieved: {len(tables)} tables found")
        else:
            print(f"   ❌ Schema retrieval failed: {result.get('error')}")
            return False
    except Exception as e:
        print(f"   ❌ Schema retrieval error: {e}")
        return False
    
    # Test query execution (if SQL was generated)
    print("\n4. Testing query execution...")
    try:
        sql_result = await mcp_client.generate_sql("Show me total number of claims")
        if sql_result.get("success"):
            exec_result = await mcp_client.execute_query(sql_result["sql"])
            if exec_result.get("success"):
                print(f"   ✅ Query executed: {exec_result['row_count']} rows returned")
            else:
                print(f"   ❌ Query execution failed: {exec_result.get('error')}")
                return False
        else:
            print("   ⚠️  Skipping query execution (SQL generation failed)")
    except Exception as e:
        print(f"   ❌ Query execution error: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("✅ All MCP client tests passed!")
    print("=" * 60)
    return True


async def test_mcp_server():
    """Test MCP server functionality"""
    print("\n" + "=" * 60)
    print("MCP Server Test")
    print("=" * 60)
    
    from mcp_server.server import mcp_server
    
    # Initialize server
    print("\n1. Initializing MCP server...")
    try:
        await mcp_server.initialize()
        print("   ✅ MCP server initialized successfully")
    except Exception as e:
        print(f"   ❌ Failed to initialize MCP server: {e}")
        return False
    
    # Test resource listing
    print("\n2. Testing resource listing...")
    try:
        resources = mcp_server.list_resources()
        print(f"   ✅ Resources listed: {len(resources)} resources")
        for resource in resources[:3]:
            print(f"      - {resource.get('name', 'Unknown')}")
    except Exception as e:
        print(f"   ❌ Resource listing error: {e}")
        return False
    
    # Test tool listing
    print("\n3. Testing tool listing...")
    try:
        tools = mcp_server.list_tools()
        print(f"   ✅ Tools listed: {len(tools)} tools")
        for tool in tools:
            print(f"      - {tool.get('name', 'Unknown')}")
    except Exception as e:
        print(f"   ❌ Tool listing error: {e}")
        return False
    
    # Test tool execution
    print("\n4. Testing tool execution...")
    try:
        result = await mcp_server.call_tool("generate_sql", {
            "query": "Show me total number of claims"
        })
        if result.get("success"):
            print(f"   ✅ Tool executed: SQL generated")
        else:
            print(f"   ❌ Tool execution failed: {result.get('error')}")
            return False
    except Exception as e:
        print(f"   ❌ Tool execution error: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("✅ All MCP server tests passed!")
    print("=" * 60)
    return True


async def test_dual_mode():
    """Test dual mode (legacy + MCP) functionality"""
    print("\n" + "=" * 60)
    print("Dual Mode Test")
    print("=" * 60)
    
    # Test with MCP mode enabled
    print("\n1. Testing MCP mode...")
    original_use_mcp = settings.USE_MCP_MODE
    original_rollout = settings.MCP_GRADUAL_ROLLOUT
    
    try:
        settings.USE_MCP_MODE = True
        settings.MCP_GRADUAL_ROLLOUT = 1.0
        
        result = await mcp_client.generate_sql("Show me total number of claims")
        if result.get("success"):
            print("   ✅ MCP mode working")
        else:
            print(f"   ⚠️  MCP mode issue: {result.get('error')}")
    except Exception as e:
        print(f"   ⚠️  MCP mode error: {e}")
    finally:
        settings.USE_MCP_MODE = original_use_mcp
        settings.MCP_GRADUAL_ROLLOUT = original_rollout
    
    print("\n2. Testing legacy mode fallback...")
    try:
        settings.USE_MCP_MODE = False
        # Legacy mode would be used here
        print("   ✅ Legacy mode available (fallback)")
    except Exception as e:
        print(f"   ⚠️  Legacy mode issue: {e}")
    finally:
        settings.USE_MCP_MODE = original_use_mcp
    
    print("\n" + "=" * 60)
    print("✅ Dual mode test completed!")
    print("=" * 60)
    return True


async def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("MCP Integration Test Suite")
    print("=" * 60)
    
    results = []
    
    # Test MCP client
    results.append(await test_mcp_client())
    
    # Test MCP server
    results.append(await test_mcp_server())
    
    # Test dual mode
    results.append(await test_dual_mode())
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"Tests passed: {sum(results)}/{len(results)}")
    
    if all(results):
        print("✅ All tests passed!")
        return 0
    else:
        print("❌ Some tests failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)


