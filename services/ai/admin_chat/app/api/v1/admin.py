"""
Admin Insights API - Chat with Data endpoint for internal staff
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any, List
import uuid
from pydantic import BaseModel

from app.core.auth import admin_auth
from app.core.config import settings
from app.services.database_service import database_service
from app.services.sql_generator import sql_generator
from app.services.visualization_service import visualization_service
from app.services.conversation_manager import conversation_manager
from app.services.intent_router import intent_router
from app.services.chat_handler import chat_handler

# MCP Client (optional - only used if MCP mode is enabled)
try:
    from app.services.mcp_client import mcp_client
    MCP_CLIENT_AVAILABLE = True
except ImportError:
    MCP_CLIENT_AVAILABLE = False
    mcp_client = None

import random

router = APIRouter()


class AdminQueryRequest(BaseModel):
    """Request model for admin data queries"""
    query: str
    session_id: Optional[str] = None
    refine_query: Optional[bool] = False  # If True, uses conversation history for context


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
    row_count: Optional[int] = None  # Total number of rows returned


@router.post("/admin/query", response_model=AdminQueryResponse)
async def admin_query_data(
    request: AdminQueryRequest,
    user_info: Dict[str, Any] = Depends(admin_auth.require_admin)
):
    """
    Admin Insights: Query analytics database using natural language
    
    This endpoint allows authorized admin users to:
    - Query large datasets using natural language
    - Receive SQL queries, results, and visualizations
    - Refine queries through conversation context
    
    Requires: Admin authentication (Bearer token or API key)
    """
    try:
        # Get or create session ID
        session_id = request.session_id or str(uuid.uuid4())
        
        # Step 1: Classify Intent using Router
        intent = await intent_router.classify_intent(request.query)
        
        # Step 2: Route based on intent
        if intent == "CHAT":
            # Handle general conversation
            return await _handle_chat_query(request, session_id)
        else:
            # Handle data query (intent == "DATA")
            return await _handle_data_query(request, session_id)
        
        # Get conversation history if refining query
        conversation_history = None
        if request.refine_query:
            conversation_history = conversation_manager.get_messages(
                session_id=session_id,
                max_messages=10
            )
        
        # Step 1: Generate SQL from natural language (with retry on errors)
        max_retries = 2
        sql_result = None
        generated_sql = None
        sql_explanation = None
        confidence = None
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                # On retry, include the error in the query context
                query_with_context = request.query
                if attempt > 0 and last_error:
                    query_with_context = (
                        f"{request.query}\n\n"
                        f"PREVIOUS ATTEMPT FAILED: {last_error}\n"
                        f"Please correct the SQL query. Make sure to:\n"
                        f"- Use only columns that exist in the schema\n"
                        f"- Check relationships between tables (e.g., claims.user_id -> users.id)\n"
                        f"- If querying by state, join through users table: claims -> users -> state"
                    )
                
                sql_result = await sql_generator.generate_sql(
                    natural_language_query=query_with_context,
                    conversation_history=conversation_history
                )
                
                generated_sql = sql_result["sql"]
                sql_explanation = sql_result["explanation"]
                confidence = sql_result["confidence"]
                last_error = None
                break  # Success, exit retry loop
                
            except Exception as e:
                last_error = str(e)
                error_msg = last_error
                
                # Provide user-friendly error messages
                if "502" in error_msg or "Bad Gateway" in error_msg or "unavailable" in error_msg.lower():
                    error_msg = (
                        "The AI service (Groq API) is currently unavailable. "
                        "Please try again in a few minutes. "
                        "If the issue persists, check your Groq API configuration."
                    )
                    # Don't retry for service unavailable errors
                    return AdminQueryResponse(
                        success=False,
                        session_id=session_id,
                        error=f"Failed to generate SQL query: {error_msg}",
                        row_count=0
                    )
                elif "timeout" in error_msg.lower():
                    error_msg = (
                        "The AI service request timed out after 30+ seconds. "
                        "This may happen with complex queries. Try: "
                        "1) Simplifying your query (e.g., 'claims by status' instead of long descriptions), "
                        "2) Waiting a moment and retrying, "
                        "3) Breaking complex queries into smaller parts."
                    )
                    # Don't retry for timeout errors
                    return AdminQueryResponse(
                        success=False,
                        session_id=session_id,
                        error=f"Failed to generate SQL query: {error_msg}",
                        row_count=0
                    )
                elif "Network error" in error_msg:
                    error_msg = (
                        "Network error connecting to the AI service. "
                        "Please check your internet connection and try again."
                    )
                    # Don't retry for network errors
                    return AdminQueryResponse(
                        success=False,
                        session_id=session_id,
                        error=f"Failed to generate SQL query: {error_msg}",
                        row_count=0
                    )
                
                # For other errors, continue to retry if attempts remain
                if attempt == max_retries:
                    return AdminQueryResponse(
                        success=False,
                        session_id=session_id,
                        error=f"Failed to generate SQL query: {error_msg}",
                        row_count=0
                    )
        
        # Step 2: Execute SQL query (read-only) with retry on column errors
        query_results = None
        execution_error = None
        
        for attempt in range(max_retries + 1):
            try:
                query_results = await database_service.execute_query(generated_sql)
                execution_error = None
                break  # Success, exit retry loop
                
            except Exception as e:
                execution_error = str(e)
                error_str = execution_error.lower()
                
                # Check if it's a column error that we can retry
                if ("unknown column" in error_str or "column" in error_str) and attempt < max_retries:
                    # Retry SQL generation with error context
                    try:
                        error_context = (
                            f"The previous SQL query failed with error: {execution_error}\n"
                            f"SQL that failed: {generated_sql}\n"
                            f"Please generate a corrected SQL query. Make sure:\n"
                            f"- All column names exist in the schema\n"
                            f"- Use proper table relationships (e.g., claims.user_id -> users.id)\n"
                            f"- Check the schema carefully before using any column"
                        )
                        
                        sql_result = await sql_generator.generate_sql(
                            natural_language_query=f"{request.query}\n\nERROR CONTEXT: {error_context}",
                            conversation_history=conversation_history
                        )
                        
                        generated_sql = sql_result["sql"]
                        sql_explanation = sql_result["explanation"]
                        confidence = sql_result["confidence"] * 0.9  # Slightly lower confidence after retry
                        continue  # Retry execution with new SQL
                        
                    except Exception as retry_error:
                        # If retry generation fails, return original error
                        break
                else:
                    # Not a retryable error or out of retries
                    break
        
        if execution_error:
            return AdminQueryResponse(
                success=False,
                session_id=session_id,
                sql=generated_sql,
                sql_explanation=sql_explanation,
                error=f"Query execution failed: {execution_error}",
                row_count=0
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
            metadata={"type": "admin_query", "sql": generated_sql}
        )
        
        conversation_manager.add_message(
            session_id=session_id,
            role="assistant",
            content=f"Query executed successfully. Returned {len(query_results)} results.",
            metadata={
                "type": "admin_response",
                "sql": generated_sql,
                "row_count": len(query_results)
            }
        )
        
        # Step 5: Return comprehensive response
        total_rows = len(query_results)
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
                "columns": visualization["columns"],
                "chart_config": visualization.get("chart_config", {}),  # Plotly and Chart.js configs
                "chart_image": visualization.get("chart_image", {}),  # Base64 PNG image
                "metadata": visualization.get("metadata", {})  # Enhanced metadata (axes, colors, settings)
            },
            summary=summary,
            session_id=session_id,
            confidence=confidence,
            row_count=total_rows  # Add row_count at top level for frontend
        )
        
    except HTTPException:
        raise
    except Exception as e:
        return AdminQueryResponse(
            success=False,
            session_id=request.session_id or "unknown",
            error=f"Unexpected error: {str(e)}",
            row_count=0
        )


@router.get("/admin/schema")
async def get_database_schema(
    table_name: Optional[str] = None,
    user_info: Dict[str, Any] = Depends(admin_auth.require_admin)
):
    """
    Get database schema information
    
    Requires: Admin authentication
    """
    try:
        if not database_service.pool:
            raise HTTPException(
                status_code=503,
                detail="Analytics database is not configured or unavailable"
            )
        
        schema_info = await database_service.get_schema_info(table_name=table_name)
        return {
            "success": True,
            "schema": schema_info
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve schema: {str(e)}"
        )


@router.get("/admin/health")
async def admin_health_check(
    user_info: Dict[str, Any] = Depends(admin_auth.require_admin)
):
    """
    Health check for admin features
    
    Requires: Admin authentication
    """
    db_available = database_service.pool is not None
    mcp_enabled = settings.USE_MCP_MODE and MCP_CLIENT_AVAILABLE
    
    return {
        "status": "healthy",
        "database_available": db_available,
        "admin_features_enabled": True,
        "mcp_mode_enabled": mcp_enabled,
        "mcp_rollout_percentage": settings.MCP_GRADUAL_ROLLOUT if mcp_enabled else 0.0,
        "user": user_info.get("user_id", "unknown")
    }


async def _handle_chat_query(
    request: AdminQueryRequest,
    session_id: str
) -> AdminQueryResponse:
    """
    Handle general conversation queries (CHAT intent)
    Uses standard LLM without MCP tools
    """
    try:
        # Get conversation history
        conversation_history = conversation_manager.get_messages(
            session_id=session_id,
            max_messages=10
        )
        
        # Handle chat query
        chat_result = await chat_handler.handle_chat(
            user_query=request.query,
            session_id=session_id,
            conversation_history=conversation_history
        )
        
        if chat_result.get("success"):
            # Save conversation history
            conversation_manager.add_message(
                session_id=session_id,
                role="user",
                content=request.query,
                metadata={"type": "chat_query", "intent": "CHAT"}
            )
            
            conversation_manager.add_message(
                session_id=session_id,
                role="assistant",
                content=chat_result.get("response", ""),
                metadata={"type": "chat_response", "intent": "CHAT"}
            )
            
            return AdminQueryResponse(
                success=True,
                session_id=session_id,
                summary=chat_result.get("response", ""),
                row_count=0,
                confidence=1.0
            )
        else:
            return AdminQueryResponse(
                success=False,
                session_id=session_id,
                error=chat_result.get("error", "Chat handling failed"),
                row_count=0
            )
    
    except Exception as e:
        return AdminQueryResponse(
            success=False,
            session_id=session_id,
            error=f"Chat handling error: {str(e)}",
            row_count=0
        )


async def _handle_data_query(
    request: AdminQueryRequest,
    session_id: str
) -> AdminQueryResponse:
    """
    Handle data queries (DATA intent)
    Routes to MCP mode if enabled, otherwise uses legacy mode
    """
    # Check if database is available
    if not database_service.pool:
        raise HTTPException(
            status_code=503,
            detail="Analytics database is not configured or unavailable"
        )
    
    # Determine if we should use MCP mode
    use_mcp = False
    if settings.USE_MCP_MODE and MCP_CLIENT_AVAILABLE:
        # Check gradual rollout percentage
        if settings.MCP_GRADUAL_ROLLOUT >= 1.0:
            use_mcp = True
        elif settings.MCP_GRADUAL_ROLLOUT > 0.0:
            # Random selection based on rollout percentage
            use_mcp = random.random() < settings.MCP_GRADUAL_ROLLOUT
    
    # Try MCP mode if enabled, with fallback to legacy
    if use_mcp:
        try:
            return await _handle_query_via_mcp(request, session_id)
        except Exception as mcp_error:
            # Fallback to legacy if MCP fails and fallback is enabled
            if settings.MCP_FALLBACK_TO_LEGACY:
                print(f"⚠️ MCP mode failed, falling back to legacy: {str(mcp_error)}")
                # Continue to legacy mode below
            else:
                # Re-raise if fallback is disabled
                raise HTTPException(
                    status_code=500,
                    detail=f"MCP mode error: {str(mcp_error)}"
                )
    
    # Legacy mode (or fallback from MCP)
    return await _handle_query_legacy(request, session_id)


async def _handle_query_legacy(
    request: AdminQueryRequest,
    session_id: str
) -> AdminQueryResponse:
    """
    Handle data query using legacy mode (original implementation)
    """
    # Get conversation history if refining query
    conversation_history = None
    if request.refine_query:
        conversation_history = conversation_manager.get_messages(
            session_id=session_id,
            max_messages=10
        )
    
    # Step 1: Generate SQL from natural language (with retry on errors)
    max_retries = 2
    sql_result = None
    generated_sql = None
    sql_explanation = None
    confidence = None
    last_error = None
    
    for attempt in range(max_retries + 1):
        try:
            # On retry, include the error in the query context
            query_with_context = request.query
            if attempt > 0 and last_error:
                query_with_context = (
                    f"{request.query}\n\n"
                    f"PREVIOUS ATTEMPT FAILED: {last_error}\n"
                    f"Please correct the SQL query. Make sure to:\n"
                    f"- Use only columns that exist in the schema\n"
                    f"- Check relationships between tables (e.g., claims.user_id -> users.id)\n"
                    f"- If querying by state, join through users table: claims -> users -> state"
                )
            
            sql_result = await sql_generator.generate_sql(
                natural_language_query=query_with_context,
                conversation_history=conversation_history
            )
            
            generated_sql = sql_result["sql"]
            sql_explanation = sql_result["explanation"]
            confidence = sql_result["confidence"]
            last_error = None
            break  # Success, exit retry loop
            
        except Exception as e:
            last_error = str(e)
            error_msg = last_error
            
            # Provide user-friendly error messages
            if "502" in error_msg or "Bad Gateway" in error_msg or "unavailable" in error_msg.lower():
                error_msg = (
                    "The AI service (RunPod GPU) is currently unavailable. "
                    "The GPU pod may be down or restarting. Please try again in a few minutes. "
                    "If the issue persists, check your RunPod pod status."
                )
                return AdminQueryResponse(
                    success=False,
                    session_id=session_id,
                    error=f"Failed to generate SQL query: {error_msg}",
                    row_count=0
                )
            elif "timeout" in error_msg.lower():
                error_msg = (
                    "The AI service request timed out after 30+ seconds. "
                    "This may happen with complex queries. Try: "
                    "1) Simplifying your query (e.g., 'claims by status' instead of long descriptions), "
                    "2) Waiting a moment and retrying, "
                    "3) Breaking complex queries into smaller parts."
                )
                return AdminQueryResponse(
                    success=False,
                    session_id=session_id,
                    error=f"Failed to generate SQL query: {error_msg}",
                    row_count=0
                )
            elif "Network error" in error_msg:
                error_msg = (
                    "Network error connecting to the AI service. "
                    "Please check your internet connection and try again."
                )
                return AdminQueryResponse(
                    success=False,
                    session_id=session_id,
                    error=f"Failed to generate SQL query: {error_msg}",
                    row_count=0
                )
            
            # For other errors, continue to retry if attempts remain
            if attempt == max_retries:
                return AdminQueryResponse(
                    success=False,
                    session_id=session_id,
                    error=f"Failed to generate SQL query: {error_msg}",
                    row_count=0
                )
    
    # Step 2: Execute SQL query (read-only) with retry on column errors
    query_results = None
    execution_error = None
    
    for attempt in range(max_retries + 1):
        try:
            query_results = await database_service.execute_query(generated_sql)
            execution_error = None
            break  # Success, exit retry loop
            
        except Exception as e:
            execution_error = str(e)
            error_str = execution_error.lower()
            
            # Check if it's a column error that we can retry
            if ("unknown column" in error_str or "column" in error_str) and attempt < max_retries:
                # Retry SQL generation with error context
                try:
                    error_context = (
                        f"The previous SQL query failed with error: {execution_error}\n"
                        f"SQL that failed: {generated_sql}\n"
                        f"Please generate a corrected SQL query. Make sure:\n"
                        f"- All column names exist in the schema\n"
                        f"- Use proper table relationships (e.g., claims.user_id -> users.id)\n"
                        f"- Check the schema carefully before using any column"
                    )
                    
                    sql_result = await sql_generator.generate_sql(
                        natural_language_query=f"{request.query}\n\nERROR CONTEXT: {error_context}",
                        conversation_history=conversation_history
                    )
                    
                    generated_sql = sql_result["sql"]
                    sql_explanation = sql_result["explanation"]
                    confidence = sql_result["confidence"] * 0.9  # Slightly lower confidence after retry
                    continue  # Retry execution with new SQL
                    
                except Exception as retry_error:
                    # If retry generation fails, return original error
                    break
            else:
                # Not a retryable error or out of retries
                break
    
    if execution_error:
        return AdminQueryResponse(
            success=False,
            session_id=session_id,
            sql=generated_sql,
            sql_explanation=sql_explanation,
            error=f"Query execution failed: {execution_error}",
            row_count=0
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
        metadata={"type": "admin_query", "sql": generated_sql, "intent": "DATA", "mode": "legacy"}
    )
    
    conversation_manager.add_message(
        session_id=session_id,
        role="assistant",
        content=f"Query executed successfully. Returned {len(query_results)} results.",
        metadata={
            "type": "admin_response",
            "sql": generated_sql,
            "row_count": len(query_results),
            "intent": "DATA",
            "mode": "legacy"
        }
    )
    
    # Step 5: Return comprehensive response
    total_rows = len(query_results)
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
            "columns": visualization["columns"],
            "chart_config": visualization.get("chart_config", {}),
            "chart_image": visualization.get("chart_image", {}),
            "metadata": visualization.get("metadata", {})
        },
        summary=summary,
        session_id=session_id,
        confidence=confidence,
        row_count=total_rows
    )


async def _handle_query_via_mcp(
    request: AdminQueryRequest,
    session_id: str
) -> AdminQueryResponse:
    """
    Handle query via MCP client (MCP-compatible mode)
    
    This function provides the same interface as legacy mode but uses MCP client
    """
    # Initialize MCP client
    await mcp_client.initialize()
    
    # Generate SQL via MCP
    sql_result = await mcp_client.generate_sql(
        query=request.query,
        session_id=session_id,
        refine_query=request.refine_query
    )
    
    if not sql_result.get("success"):
        return AdminQueryResponse(
            success=False,
            session_id=session_id,
            error=f"Failed to generate SQL: {sql_result.get('error', 'Unknown error')}",
            row_count=0
        )
    
    generated_sql = sql_result["sql"]
    sql_explanation = sql_result.get("explanation", "Query generated successfully")
    confidence = sql_result.get("confidence", 0.8)
    
    # Execute query via MCP
    execution_result = await mcp_client.execute_query(
        sql=generated_sql
    )
    
    if not execution_result.get("success"):
        return AdminQueryResponse(
            success=False,
            session_id=session_id,
            sql=generated_sql,
            sql_explanation=sql_explanation,
            error=f"Query execution failed: {execution_result.get('error', 'Unknown error')}",
            row_count=0
        )
    
    # Save conversation history
    conversation_manager.add_message(
        session_id=session_id,
        role="user",
        content=request.query,
        metadata={"type": "admin_query", "sql": generated_sql, "intent": "DATA", "mode": "mcp"}
    )
    
    conversation_manager.add_message(
        session_id=session_id,
        role="assistant",
        content=f"Query executed successfully. Returned {execution_result['row_count']} results.",
        metadata={
            "type": "admin_response",
            "sql": generated_sql,
            "row_count": execution_result["row_count"],
            "intent": "DATA",
            "mode": "mcp"
        }
    )
    
    # Format response (same structure as legacy mode)
    return AdminQueryResponse(
        success=True,
        data=execution_result.get("data", [])[:100],  # Limit to 100 rows
        sql=generated_sql,
        sql_explanation=sql_explanation,
        visualization=execution_result.get("visualization", {}),
        summary=execution_result.get("summary", "Query executed successfully"),
        session_id=session_id,
        confidence=confidence,
        row_count=execution_result.get("row_count", 0)
    )



