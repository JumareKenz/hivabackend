#!/usr/bin/env python3
"""
Test script to verify MySQL database connection
"""
import asyncio
import sys
from pathlib import Path

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.database_service import database_service


async def test_connection():
    """Test database connection and execute a simple query"""
    print("=" * 60)
    print("DATABASE CONNECTION TEST")
    print("=" * 60)
    print()
    
    try:
        # Initialize the database connection
        print("1. Initializing database connection pool...")
        await database_service.initialize()
        
        if not database_service.pool:
            print("❌ Database pool not initialized. Check configuration.")
            return False
        
        print("✅ Database pool initialized successfully")
        print()
        
        # Test a simple query
        print("2. Testing simple query (SELECT 1 as test)...")
        result = await database_service.execute_query("SELECT 1 as test, DATABASE() as current_db")
        
        if result:
            print("✅ Query executed successfully!")
            print(f"   Result: {result[0]}")
        else:
            print("⚠️  Query executed but returned no results")
        print()
        
        # Test getting database version
        print("3. Getting database version...")
        version_result = await database_service.execute_query("SELECT VERSION() as version")
        if version_result:
            print(f"✅ MySQL Version: {version_result[0].get('version', 'Unknown')}")
        print()
        
        # Test listing tables
        print("4. Listing available tables...")
        schema_info = await database_service.get_schema_info()
        if schema_info and 'tables' in schema_info:
            tables = schema_info['tables']
            print(f"✅ Found {len(tables)} tables:")
            for table in tables[:10]:  # Show first 10 tables
                table_name = table.get('table_name', 'Unknown')
                col_count = len(table.get('columns', []))
                print(f"   - {table_name} ({col_count} columns)")
            if len(tables) > 10:
                print(f"   ... and {len(tables) - 10} more tables")
        else:
            print("⚠️  No tables found or schema info unavailable")
        print()
        
        # Close the connection
        print("5. Closing database connection...")
        await database_service.close()
        print("✅ Connection closed successfully")
        print()
        
        print("=" * 60)
        print("✅ ALL TESTS PASSED - Database connection is working!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"❌ Error during test: {e}")
        print()
        print("=" * 60)
        print("❌ CONNECTION TEST FAILED")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_connection())
    sys.exit(0 if success else 1)

