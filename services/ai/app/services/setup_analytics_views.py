"""
Utility script to set up analytics views with PII masking.
Run this once to create the analytics_view_* views in your database.
"""
import asyncio
import re
from app.services.database_service import database_service
from app.services.analytics_view_service import analytics_view_service


async def setup_analytics_views():
    """
    Create analytics views with PII masking.
    This should be run once to set up the view layer.
    """
    print("Setting up analytics views with PII masking...")
    
    # Initialize database connection
    await database_service.initialize()
    
    if not database_service.pool:
        print("❌ Database not available. Please check your database configuration.")
        return
    
    print("✅ Database connection established")
    
    # Generate DDL statements
    print("Generating DDL statements for analytics views...")
    ddl_statements = await analytics_view_service.generate_analytics_views_ddl()
    
    if not ddl_statements:
        print("⚠️  No DDL statements generated. Check if schema information is available.")
        return
    
    print(f"Generated {len(ddl_statements)} view creation statements")
    
    # Execute DDL statements
    print("\nCreating views...")
    success_count = 0
    error_count = 0
    
    for i, ddl in enumerate(ddl_statements, 1):
        try:
            # Use _execute_schema_query to bypass analytics_view validation for CREATE VIEW
            # We need to temporarily allow CREATE statements for view setup
            async with database_service.get_connection() as conn:
                if database_service.db_type == "postgresql":
                    await conn.execute(ddl)
                elif database_service.db_type == "mysql":
                    async with conn.cursor() as cursor:
                        await cursor.execute(ddl)
                    await conn.commit()
            
            # Extract view name from DDL
            view_name_match = re.search(r'CREATE.*?VIEW\s+(\w+)', ddl, re.IGNORECASE)
            view_name = view_name_match.group(1) if view_name_match else f"view_{i}"
            print(f"  ✅ Created {view_name}")
            success_count += 1
            
        except Exception as e:
            view_name_match = re.search(r'CREATE.*?VIEW\s+(\w+)', ddl, re.IGNORECASE)
            view_name = view_name_match.group(1) if view_name_match else f"view_{i}"
            print(f"  ❌ Failed to create {view_name}: {str(e)}")
            error_count += 1
    
    print(f"\n✅ Setup complete: {success_count} views created, {error_count} errors")
    print("\nNote: You can now use the enhanced SQL generator which will automatically")
    print("      use these analytics_view_* tables for all queries.")


if __name__ == "__main__":
    asyncio.run(setup_analytics_views())

