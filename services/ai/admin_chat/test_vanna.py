"""
Test Vanna AI SQL Generation
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.services.database_service import database_service
from app.services.vanna_service import vanna_service
from app.services.sql_generator import sql_generator


async def test_vanna():
    """Test Vanna AI SQL generation"""
    print("🧪 Testing Vanna AI Integration\n")
    
    # Initialize database
    print("1️⃣  Initializing database...")
    await database_service.initialize()
    
    if not database_service.pool:
        print("❌ Database not available")
        return
    
    print("✅ Database connected\n")
    
    # Initialize Vanna
    print("2️⃣  Initializing Vanna AI...")
    vanna_ready = await vanna_service.initialize()
    
    if not vanna_ready:
        print("❌ Vanna not available")
        return
    
    print("✅ Vanna AI ready\n")
    
    # Test queries
    test_queries = [
        "show me claims by status",
        "how many claims are there",
        "show me claims in Zamfara state",
    ]
    
    print("3️⃣  Testing SQL Generation\n")
    print("=" * 60)
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n📝 Test {i}: {query}")
        print("-" * 60)
        
        try:
            # Generate SQL using SQL generator (which uses Vanna)
            result = await sql_generator.generate_sql(
                natural_language_query=query,
                conversation_history=None
            )
            
            print(f"✅ Source: {result.get('source', 'unknown')}")
            print(f"✅ Confidence: {result.get('confidence', 0):.2f}")
            print(f"✅ SQL:\n{result.get('sql', 'N/A')}")
            print(f"✅ Explanation: {result.get('explanation', 'N/A')}")
            
            # Try to execute the query
            try:
                results = await database_service.execute_query(result['sql'])
                print(f"✅ Query executed successfully: {len(results)} rows returned")
                if results and len(results) > 0:
                    print(f"   Sample row: {list(results[0].keys())[:3]}...")
            except Exception as e:
                print(f"⚠️  Query execution error: {str(e)[:100]}")
            
        except Exception as e:
            print(f"❌ Error: {str(e)[:200]}")
        
        print("-" * 60)
    
    print("\n" + "=" * 60)
    print("✅ Testing complete!")
    
    # Close database
    await database_service.close()


if __name__ == "__main__":
    asyncio.run(test_vanna())




