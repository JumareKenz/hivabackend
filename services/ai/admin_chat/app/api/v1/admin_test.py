"""
Admin SQL Chat - Test Mode (No Database Required)
Allows testing SQL generation and chat functionality without live database connection
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any, List
import uuid
from pydantic import BaseModel

from app.services.sql_generator import sql_generator
from app.services.visualization_service import visualization_service
from app.services.conversation_manager import conversation_manager

router = APIRouter()


class AdminQueryRequest(BaseModel):
    """Request model for admin data queries (test mode)"""
    query: str
    session_id: Optional[str] = None
    refine_query: Optional[bool] = False


class AdminQueryResponse(BaseModel):
    """Response model for admin data queries"""
    success: bool
    data: Optional[List[Dict[str, Any]]] = None
    sql: Optional[str] = None
    sql_explanation: Optional[str] = None
    visualization: Optional[Dict[str, Any]] = None
    summary: Optional[str] = None
    session_id: str
    error: Optional[str] = None
    confidence: Optional[float] = None
    test_mode: bool = True  # Indicates this is test mode


# Mock database schema for testing
MOCK_SCHEMA = {
    "tables": [
        {
            "table_name": "users",
            "columns": [
                {"column_name": "id", "data_type": "int", "is_nullable": "NO"},
                {"column_name": "name", "data_type": "varchar(255)", "is_nullable": "NO"},
                {"column_name": "email", "data_type": "varchar(255)", "is_nullable": "NO"},
                {"column_name": "created_at", "data_type": "timestamp", "is_nullable": "YES"},
                {"column_name": "branch_id", "data_type": "varchar(50)", "is_nullable": "YES"},
            ]
        },
        {
            "table_name": "enrollments",
            "columns": [
                {"column_name": "id", "data_type": "int", "is_nullable": "NO"},
                {"column_name": "user_id", "data_type": "int", "is_nullable": "NO"},
                {"column_name": "plan_type", "data_type": "varchar(50)", "is_nullable": "NO"},
                {"column_name": "status", "data_type": "varchar(50)", "is_nullable": "NO"},
                {"column_name": "enrolled_at", "data_type": "timestamp", "is_nullable": "YES"},
            ]
        },
        {
            "table_name": "claims",
            "columns": [
                {"column_name": "id", "data_type": "int", "is_nullable": "NO"},
                {"column_name": "enrollment_id", "data_type": "int", "is_nullable": "NO"},
                {"column_name": "amount", "data_type": "decimal(10,2)", "is_nullable": "NO"},
                {"column_name": "status", "data_type": "varchar(50)", "is_nullable": "NO"},
                {"column_name": "submitted_at", "data_type": "timestamp", "is_nullable": "YES"},
            ]
        }
    ]
}


def generate_mock_data(sql: str) -> List[Dict[str, Any]]:
    """
    Generate mock data based on SQL query
    This simulates database results for testing
    """
    sql_lower = sql.lower()
    
    # Simple mock data generation based on query
    if "users" in sql_lower:
        return [
            {"id": 1, "name": "John Doe", "email": "john@example.com", "created_at": "2024-01-15", "branch_id": "kano"},
            {"id": 2, "name": "Jane Smith", "email": "jane@example.com", "created_at": "2024-02-20", "branch_id": "rivers"},
            {"id": 3, "name": "Bob Johnson", "email": "bob@example.com", "created_at": "2024-03-10", "branch_id": "kaduna"},
        ]
    elif "enrollments" in sql_lower:
        return [
            {"id": 1, "user_id": 1, "plan_type": "premium", "status": "active", "enrolled_at": "2024-01-20"},
            {"id": 2, "user_id": 2, "plan_type": "standard", "status": "active", "enrolled_at": "2024-02-25"},
            {"id": 3, "user_id": 3, "plan_type": "premium", "status": "pending", "enrolled_at": "2024-03-15"},
        ]
    elif "claims" in sql_lower:
        return [
            {"id": 1, "enrollment_id": 1, "amount": 5000.00, "status": "approved", "submitted_at": "2024-04-01"},
            {"id": 2, "enrollment_id": 2, "amount": 3000.00, "status": "pending", "submitted_at": "2024-04-05"},
            {"id": 3, "enrollment_id": 1, "amount": 7500.00, "status": "approved", "submitted_at": "2024-04-10"},
        ]
    elif "count" in sql_lower:
        return [{"count": 150}]
    elif "sum" in sql_lower or "total" in sql_lower:
        return [{"total": 15500.00}]
    else:
        # Generic mock data
        return [
            {"id": 1, "value": "Sample Data 1"},
            {"id": 2, "value": "Sample Data 2"},
        ]


@router.post("/admin/test/query", response_model=AdminQueryResponse)
async def admin_query_test(request: AdminQueryRequest):
    """
    Admin Insights Test Mode: Query SQL generation without database connection
    
    This endpoint allows testing:
    - SQL generation from natural language
    - Query explanation and confidence
    - Visualization and summary generation
    - Conversation context handling
    
    No authentication required for testing
    No database connection required
    """
    try:
        # Get or create session ID
        session_id = request.session_id or str(uuid.uuid4())
        
        # Get conversation history if refining query
        conversation_history = None
        if request.refine_query:
            conversation_history = conversation_manager.get_messages(
                session_id=session_id,
                max_messages=10
            )
        
        # Step 1: Generate SQL from natural language
        # Mock the schema context since database_service won't be available
        try:
            # Build mock schema context directly
            schema_text = "DATABASE SCHEMA:\n\n"
            for table in MOCK_SCHEMA.get("tables", []):
                table_name = table.get("table_name", "")
                columns = table.get("columns", [])
                
                schema_text += f"Table: {table_name}\n"
                schema_text += "Columns:\n"
                for col in columns:
                    col_name = col.get("column_name", "")
                    col_type = col.get("data_type", "")
                    nullable = "NULL" if col.get("is_nullable") == "YES" else "NOT NULL"
                    schema_text += f"  - {col_name} ({col_type}, {nullable})\n"
                schema_text += "\n"
            
            # Temporarily patch sql_generator's schema cache and database_service
            original_schema_cache = sql_generator._schema_cache
            sql_generator._schema_cache = MOCK_SCHEMA
            
            # Mock database_service.get_schema_info if needed
            try:
                from app.services import database_service
                original_get_schema_info = database_service.get_schema_info
                
                async def mock_get_schema_info(table_name=None):
                    return MOCK_SCHEMA
                
                database_service.get_schema_info = mock_get_schema_info
                database_service.db_type = "mysql"  # Set default DB type
                
            except:
                pass  # If database_service not available, that's fine
            
            try:
                sql_result = await sql_generator.generate_sql(
                    natural_language_query=request.query,
                    conversation_history=conversation_history
                )
                
                generated_sql = sql_result["sql"]
                sql_explanation = sql_result["explanation"]
                confidence = sql_result["confidence"]
                
            finally:
                # Restore original state
                sql_generator._schema_cache = original_schema_cache
                try:
                    database_service.get_schema_info = original_get_schema_info
                except:
                    pass
            
        except Exception as e:
            return AdminQueryResponse(
                success=False,
                session_id=session_id,
                error=f"Failed to generate SQL query: {str(e)}",
                test_mode=True
            )
        
        # Step 2: Generate mock query results (simulate database execution)
        try:
            query_results = generate_mock_data(generated_sql)
        except Exception as e:
            return AdminQueryResponse(
                success=False,
                session_id=session_id,
                sql=generated_sql,
                sql_explanation=sql_explanation,
                error=f"Mock data generation failed: {str(e)}",
                test_mode=True
            )
        
        # Step 3: Analyze and visualize results
        visualization = visualization_service.analyze_data(query_results)
        formatted_table = visualization_service.format_table(query_results, max_rows=100)
        summary = visualization_service.generate_summary(query_results, sql_explanation)
        
        # Step 4: Save conversation history
        conversation_manager.add_message(
            session_id=session_id,
            role="user",
            content=request.query,
            metadata={"type": "admin_query_test", "sql": generated_sql}
        )
        
        conversation_manager.add_message(
            session_id=session_id,
            role="assistant",
            content=f"Query executed successfully (TEST MODE). Returned {len(query_results)} mock results.",
            metadata={
                "type": "admin_response_test",
                "sql": generated_sql,
                "row_count": len(query_results),
                "test_mode": True
            }
        )
        
        # Step 5: Return comprehensive response
        return AdminQueryResponse(
            success=True,
            data=query_results[:100],  # Limit to 100 rows in response
            sql=generated_sql,
            sql_explanation=sql_explanation,
            visualization={
                "type": visualization["type"],
                "table": formatted_table,
                "suggestions": visualization.get("suggestions", []),
                "row_count": visualization["row_count"],
                "columns": visualization["columns"]
            },
            summary=summary,
            session_id=session_id,
            confidence=confidence,
            test_mode=True
        )
        
    except Exception as e:
        return AdminQueryResponse(
            success=False,
            session_id=request.session_id or "unknown",
            error=f"Unexpected error: {str(e)}",
            test_mode=True
        )


@router.get("/admin/test/schema")
async def get_test_schema():
    """
    Get mock database schema for testing
    
    No authentication required
    """
    return {
        "success": True,
        "schema": MOCK_SCHEMA,
        "test_mode": True,
        "note": "This is mock schema data for testing. No database connection required."
    }


@router.get("/admin/test/health")
async def admin_test_health():
    """
    Health check for admin test features
    
    No authentication required
    """
    return {
        "status": "healthy",
        "test_mode": True,
        "database_required": False,
        "features_available": [
            "SQL generation",
            "Query explanation",
            "Mock data generation",
            "Visualization",
            "Summary generation"
        ]
    }

