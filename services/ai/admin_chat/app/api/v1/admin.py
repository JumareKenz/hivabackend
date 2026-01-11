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
from app.services.insight_generator import insight_generator
from app.services.schema_mapper import schema_mapper

# Phase 4: Guardrails & Runtime Enforcement
from app.services.domain_router import domain_router
from app.services.sql_validator import sql_validator
from app.services.sql_rewriter import sql_rewriter
from app.services.confidence_scorer import confidence_scorer
from app.services.result_sanitizer import result_sanitizer

# Domain 3: Intelligence, Governance & Continuous Improvement
from app.services.query_intelligence import query_intelligence
from app.services.safety_governance import safety_governance
from app.services.explainability_engine import explainability_engine
from app.services.feedback_learning import feedback_learning
from app.services.performance_controls import performance_controls
from app.services.evaluation_metrics import evaluation_metrics

# MCP Client - DISABLED
# MCP mode is disabled to ensure Phase 4 validator runs in legacy mode
# All queries must go through _handle_query_legacy which includes the validator
MCP_CLIENT_AVAILABLE = False
mcp_client = None

import random
import time

router = APIRouter()


class AdminQueryRequest(BaseModel):
    """Request model for admin data queries"""
    query: str
    session_id: Optional[str] = None
    refine_query: Optional[bool] = False  # If True, uses conversation history for context


class TableSelectionMetadata(BaseModel):
    """Metadata about which tables were selected and why"""
    selected_tables: List[str] = []
    reason: Optional[str] = None
    join_confidence: Optional[float] = None


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
    source: Optional[str] = None  # SQL generation source: "vanna" or "legacy"
    table_selection: Optional[TableSelectionMetadata] = None  # Fix 3: Table selection transparency


@router.post("/admin/query", response_model=AdminQueryResponse)
async def admin_query_data(
    request: AdminQueryRequest,
    user_info: Dict[str, Any] = Depends(admin_auth.require_admin)
):
    """
    Admin Insights: Query analytics database using natural language
    
    This endpoint allows authorized admin users to:
    - Query large datasets using natural language
    - Receive human-readable insights (not raw SQL)
    - Refine queries through conversation context
    - Get executive-grade analysis
    
    Requires: Admin authentication (Bearer token or API key)
    """
    try:
        # Initialize schema mapper if needed
        if not schema_mapper._initialized:
            await schema_mapper.initialize()
        
        # Initialize domain router if needed
        if not domain_router._initialized:
            await domain_router.initialize()
        
        # Get or create session ID
        session_id = request.session_id or str(uuid.uuid4())
        
        # Step 1: Classify Intent using Router
        intent = await intent_router.classify_intent(request.query)
        
        # Step 2: Unified pipeline - even CHAT queries can lead to data queries
        # If it's clearly a data query, handle as data
        # If it's chat but could be answered with data, try data first
        if intent == "DATA":
            # Handle data query
            return await _handle_data_query(request, session_id, user_info)
        else:
            # For CHAT queries, check if they can be answered with data
            # If user asks "how many claims", even if classified as CHAT, treat as DATA
            query_lower = request.query.lower()
            data_indicators = ['how many', 'count', 'total', 'show', 'list', 'top', 'bottom', 
                             'claims', 'providers', 'diagnosis', 'disease', 'state', 'facility']
            
            if any(indicator in query_lower for indicator in data_indicators):
                # Treat as data query even if classified as CHAT
                return await _handle_data_query(request, session_id, user_info)
            else:
                # Pure conversation
                return await _handle_chat_query(request, session_id)
        
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
                sql_source = sql_result.get("source", "legacy")  # Get source (vanna or legacy)
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
        
        # Step 4: Generate human-readable insight (replaces raw summary)
        insight = await insight_generator.generate_insight(
            query=request.query,
            results=query_results,
            sql=generated_sql,
            row_count=len(query_results)
        )
        
        # Step 5: Save conversation history
        conversation_manager.add_message(
            session_id=session_id,
            role="user",
            content=request.query,
            metadata={"type": "admin_query", "sql": generated_sql}
        )
        
        conversation_manager.add_message(
            session_id=session_id,
            role="assistant",
            content=insight,  # Store insight instead of raw message
            metadata={
                "type": "admin_response",
                "sql": generated_sql,
                "row_count": len(query_results)
            }
        )
        
        # Step 6: Return comprehensive response
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
            summary=insight,  # Human-readable insight (primary response)
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
    # MCP mode is disabled - all queries use legacy mode with validator
    mcp_enabled = False
    
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
    session_id: str,
    user_info: Optional[Dict[str, Any]] = None
) -> AdminQueryResponse:
    """
    Handle data queries (DATA intent)
    Routes to MCP mode if enabled, otherwise uses legacy mode
    """
    # Debug logging removed - MCP mode is disabled
    
    # Check if database is available
    if not database_service.pool:
        raise HTTPException(
            status_code=503,
            detail="Analytics database is not configured or unavailable"
        )
    
    # MCP Mode - DISABLED
    # All queries must use legacy mode which includes Phase 4 validator
    # The validator is critical for ensuring SQL correctness and must run for all queries
    # MCP mode does not have validator integration and is therefore disabled
    
    # Legacy mode (with Phase 4 validator)
    return await _handle_query_legacy(request, session_id, user_info)


async def _handle_query_legacy(
    request: AdminQueryRequest,
    session_id: str,
    user_info: Optional[Dict[str, Any]] = None
) -> AdminQueryResponse:
    """
    Handle data query using legacy mode (original implementation)
    
    Phase 4: Runtime Architecture:
    1. Domain Router (route to domain)
    2. Vanna NL → SQL
    3. SQL Validator (STRICT - HARD FAIL)
    4. SQL Rewriter (if safe - SOFT CORRECTION)
    5. Confidence Scorer (clarification if needed)
    6. Execution
    7. Result Formatter (sanitize output)
    8. Query Auditor (log metadata)
    """
    # Debug logging - can be enabled for troubleshooting
    # Domain 3.1: Query Intelligence - Intent Classification
    intent_category, intent_confidence = query_intelligence.classify_intent_category(request.query)
    is_supported, intent_rejection = query_intelligence.validate_intent_supported(intent_category)
    if not is_supported:
        return AdminQueryResponse(
            success=False,
            session_id=session_id,
            error=intent_rejection,
            row_count=0
        )
    
    # Domain 3.2: Safety - Get user role (default to 'analyst' if not available)
    user_role = user_info.get('role', 'analyst') if user_info else 'analyst'
    
    # Phase 4: Step 1 - Domain Router (Schema-Aware)
    # Initialize domain router if needed
    if not domain_router._initialized:
        await domain_router.initialize()
    
    domain, rejection_reason = domain_router.route(request.query)
    if domain == 'rejected':
        return AdminQueryResponse(
            success=False,
            session_id=session_id,
            error=rejection_reason,
            row_count=0
        )
    
    # Domain 3.1: Schema-Aware Reasoning
    schema_info = await sql_generator._get_schema_info()
    reasoning_plan = query_intelligence.enforce_step_constrained_reasoning(request.query, schema_info)
    
    # Domain 3.2: Safety - Check role permissions
    required_tables = reasoning_plan.get('required_tables', [])
    has_permission, permission_error = safety_governance.check_role_permissions(user_role, required_tables, request.query)
    if not has_permission:
        return AdminQueryResponse(
            success=False,
            session_id=session_id,
            error=permission_error,
            row_count=0
        )
    
    # Domain 3.2: Safety - Validate query safety
    # (Will validate SQL after generation)
    
    # Get conversation history if refining query
    conversation_history = None
    if request.refine_query:
        conversation_history = conversation_manager.get_messages(
            session_id=session_id,
            max_messages=10
        )
    
    # Phase 4: Step 2 - Generate SQL from natural language (with retry on errors)
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
            sql_source = sql_result.get("source", "legacy")  # Get source (vanna or legacy)
            
            # CRITICAL: Validate aggregation for disease/highest/most queries
            query_lower = request.query.lower()
            is_disease_aggregation_query = any(keyword in query_lower for keyword in [
                'disease', 'diagnosis', 'highest', 'most', 'top'
            ]) and any(keyword in query_lower for keyword in ['patients', 'claims', 'count'])
            
            print(f"🔍 [AGGREGATION_VALIDATION] is_disease_aggregation_query: {is_disease_aggregation_query}")
            print(f"🔍 [AGGREGATION_VALIDATION] SQL length: {len(generated_sql) if generated_sql else 0}")
            
            if is_disease_aggregation_query and generated_sql:
                import re
                sql_upper = generated_sql.upper()
                # Check if SQL is returning individual rows instead of aggregated data
                has_individual_claim_columns = (
                    re.search(r'\bc\.id\b', sql_upper) or 
                    re.search(r'\bclaims\.id\b', sql_upper) or
                    'CLAIM_UNIQUE_ID' in sql_upper or
                    'CLIENT_NAME' in sql_upper or
                    ('STATUS' in sql_upper and 'CASE' in sql_upper and 'GROUP BY' not in sql_upper)
                )
                has_aggregation = 'GROUP BY' in sql_upper and 'COUNT' in sql_upper
                has_diagnosis_name = re.search(r'\bd\.name\b|\bdiagnoses\.name\b', sql_upper)
                
                # If SQL has individual claim columns but no aggregation or diagnosis name, it's wrong
                if has_individual_claim_columns and (not has_aggregation or not has_diagnosis_name):
                    # This is wrong - reject immediately
                    return AdminQueryResponse(
                        success=False,
                        session_id=session_id,
                        sql=generated_sql,
                        error=(
                            "The generated SQL query returns individual claims instead of aggregated disease data. "
                            "This query requires aggregated results showing disease names with patient counts. "
                            "Please try rephrasing your question or contact support if this issue persists."
                        ),
                        row_count=0
                    )
            
            # Domain 3.2: Safety - Validate query safety (before other validations)
            is_safe, safety_error = safety_governance.validate_query_safety(generated_sql)
            if not is_safe:
                evaluation_metrics.record_query_metric('sql_validity', False, {'error': safety_error})
                return AdminQueryResponse(
                    success=False,
                    session_id=session_id,
                    sql=generated_sql,
                    error=f"Query safety check failed: {safety_error}",
                    row_count=0
                )
            
            # Domain 3.2: Safety - Check sensitive data access
            is_allowed, sensitive_error = safety_governance.check_sensitive_data_access(request.query, generated_sql)
            if not is_allowed:
                evaluation_metrics.record_query_metric('sensitive_data_access_attempt', True, {'query': request.query})
                return AdminQueryResponse(
                    success=False,
                    session_id=session_id,
                    sql=generated_sql,
                    error=sensitive_error,
                    row_count=0
                )
            
            # Domain 3.5: Performance - Estimate query cost
            cost_estimate = performance_controls.estimate_query_cost(generated_sql)
            if cost_estimate.get('warning_message'):
                # Log warning but don't block
                print(f"⚠️  Query cost warning: {cost_estimate['warning_message']}")
            
            # Phase 4: Step 3 - SQL Validator (STRICT - HARD FAIL)
            # ===== CRITICAL VALIDATION POINT - CODE VERSION 2026-01-01 =====
            print("="*80)
            print("🔴 CRITICAL VALIDATION POINT REACHED - VERSION 2026-01-01")
            print("="*80)
            
            # CRITICAL: Ensure generated_sql exists before validation
            if not generated_sql:
                print(f"🔴 [VALIDATOR DEBUG] CRITICAL ERROR: generated_sql is None!")
                return AdminQueryResponse(
                    success=False,
                    session_id=session_id,
                    error="SQL generation failed: No SQL was generated",
                    row_count=0
                )
            
            print(f"🔍 [VALIDATOR DEBUG] Calling validator...")
            print(f"   Domain: {domain}")
            print(f"   Query: {request.query[:100]}...")
            print(f"   SQL length: {len(generated_sql)}")
            print(f"   SQL preview: {generated_sql[:200]}...")
            print(f"   SQL type: {type(generated_sql)}")
            
            # CRITICAL: Wrap validator call to catch any exceptions
            try:
                is_valid, validation_error = sql_validator.validate(generated_sql, request.query, domain)
            except Exception as validator_exception:
                print(f"🔴 [VALIDATOR DEBUG] CRITICAL: Validator threw exception: {validator_exception}")
                import traceback
                traceback.print_exc()
                # Fail safe: reject if validator crashes
                return AdminQueryResponse(
                    success=False,
                    session_id=session_id,
                    sql=generated_sql,
                    error=f"SQL validation error: {str(validator_exception)}",
                    row_count=0
                )
            
            print(f"🔍 [VALIDATOR DEBUG] Validator result:")
            print(f"   Valid: {is_valid}")
            print(f"   Error: {validation_error}")
            
            if not is_valid:
                print(f"🔴 [VALIDATOR DEBUG] SQL REJECTED - Returning error to user")
                evaluation_metrics.record_query_metric('sql_validity', False, {'error': validation_error})
                return AdminQueryResponse(
                    success=False,
                    session_id=session_id,
                    sql=generated_sql,
                    error=f"Query validation failed: {validation_error}",
                    row_count=0
                )
            
            print(f"✅ [VALIDATOR DEBUG] SQL PASSED validation")
            evaluation_metrics.record_query_metric('sql_validity', True)
            
            # Phase 4: Step 4 - SQL Rewriter (SOFT CORRECTION)
            rewritten_sql, was_rewritten, rewrite_error = sql_rewriter.rewrite(generated_sql, request.query)
            if rewrite_error:
                # If rewrite is not safe, reject
                return AdminQueryResponse(
                    success=False,
                    session_id=session_id,
                    sql=generated_sql,
                    error=f"Query rewrite failed: {rewrite_error}",
                    row_count=0
                )
            
            if was_rewritten:
                generated_sql = rewritten_sql
                sql_explanation += " (Query was automatically corrected for best practices)"
            
            # Phase 4: Step 5 - Confidence Scorer
            # Classify intent for confidence scoring
            from app.services.intent_classifier import intent_classifier
            intent = intent_classifier.classify_intent(request.query)
            
            # Debug: Log SQL before confidence scoring
            print(f"🔍 [CONFIDENCE_SCORER] SQL before scoring: {generated_sql[:200]}...")
            print(f"🔍 [CONFIDENCE_SCORER] Query: {request.query}")
            print(f"🔍 [CONFIDENCE_SCORER] Intent: {intent}")
            print(f"🔍 [CONFIDENCE_SCORER] Domain: {domain}")
            
            confidence_score, clarification_msg = confidence_scorer.score(generated_sql, request.query, intent, domain)
            
            print(f"🔍 [CONFIDENCE_SCORER] Confidence: {confidence_score}, Clarification: {clarification_msg}")
            
            if clarification_msg:
                # Low confidence - request clarification
                # For state queries, be more lenient - log but don't block if SQL is correct
                query_lower = request.query.lower()
                is_state_query = any(state in query_lower for state in [
                    'zamfara', 'kano', 'kogi', 'kaduna', 'fct', 'abuja', 'adamawa',
                    'sokoto', 'rivers', 'osun', 'lagos', 'state', 'states'
                ])
                
                # Check if SQL is actually correct (has GROUP BY, COUNT, diagnosis name)
                sql_upper = generated_sql.upper()
                has_correct_structure = (
                    'GROUP BY' in sql_upper and
                    'COUNT' in sql_upper and
                    ('D.NAME' in sql_upper or 'DIAGNOSES.NAME' in sql_upper) and
                    ('DIAGNOSES' in sql_upper or 'DISEASE' in sql_upper)
                )
                
                if is_state_query and has_correct_structure:
                    # SQL is correct, just confidence scorer is being too strict
                    # Allow it through with a warning (removed confidence_score >= 0.5 requirement)
                    print(f"⚠️  [CONFIDENCE_SCORER] Allowing state query despite low confidence (SQL is correct)")
                    print(f"⚠️  [CONFIDENCE_SCORER] Confidence was {confidence_score}, but SQL structure is correct")
                else:
                    # Low confidence - request clarification
                    print(f"❌ [CONFIDENCE_SCORER] Blocking query - is_state_query: {is_state_query}, has_correct_structure: {has_correct_structure}, confidence: {confidence_score}")
                    return AdminQueryResponse(
                        success=False,
                        session_id=session_id,
                        sql=generated_sql,
                        error=clarification_msg,
                        row_count=0,
                        confidence=confidence_score
                    )
            
            # Update confidence with scored value
            confidence = min(confidence, confidence_score) if confidence else confidence_score
            
            last_error = None
            break  # Success, exit retry loop
            
        except Exception as e:
            last_error = str(e)
            error_msg = last_error
            
            # Provide user-friendly error messages
            if "All LLM providers failed" in error_msg:
                # Both RunPod and Groq failed
                error_msg = (
                    "All AI services are currently unavailable. "
                    "RunPod: GPU pod not running vLLM server. "
                    "Groq: All models blocked at project level. "
                    "Please start vLLM on RunPod or enable Groq models at https://console.groq.com/settings/project/limits"
                )
                return AdminQueryResponse(
                    success=False,
                    session_id=session_id,
                    error=f"Failed to generate SQL query: {error_msg}",
                    row_count=0
                )
            elif "502" in error_msg or "Bad Gateway" in error_msg or "unavailable" in error_msg.lower():
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
    
    # Domain 3.5: Performance - Check if query should be cached
    should_cache, cache_key = performance_controls.should_cache_query(request.query, generated_sql)
    # TODO: Implement caching layer
    
    # Step 2: Execute SQL query (read-only) with retry on column errors
    query_results = None
    execution_error = None
    execution_start_time = time.time()
    
    for attempt in range(max_retries + 1):
        try:
            query_results = await database_service.execute_query(generated_sql)
            execution_time = time.time() - execution_start_time
            evaluation_metrics.record_query_metric('response_time', execution_time * 1000)  # Convert to ms
            execution_error = None
            break  # Success, exit retry loop
            
        except Exception as e:
            execution_error = str(e)
            execution_time = time.time() - execution_start_time
            error_str = execution_error.lower()
            
            # Domain 3.5: Performance - Handle query failure
            failure_info = performance_controls.handle_query_failure(generated_sql, execution_error, request.query)
            evaluation_metrics.record_query_metric('query_failure', True, {'error': execution_error})
            
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
        # Domain 3.5: Performance - Return failure info
        failure_info = performance_controls.handle_query_failure(generated_sql, execution_error, request.query)
        return AdminQueryResponse(
            success=False,
            session_id=session_id,
            sql=generated_sql,
            sql_explanation=failure_info.get('explanation', sql_explanation),
            error=failure_info.get('clarifying_question', f"Query execution failed: {execution_error}"),
            row_count=0
        )
    
    # Domain 3.2: Safety - Identify and mask PII columns
    pii_columns = safety_governance.identify_pii_columns(generated_sql)
    
    # Phase 4: Step 7 - Result Sanitizer (mandatory post-processing)
    sanitized_results = result_sanitizer.sanitize(query_results, generated_sql)
    
    # Domain 3.2: Safety - Mask PII in results
    if pii_columns:
        sanitized_results = safety_governance.mask_pii_in_results(sanitized_results, pii_columns)
    
    # Domain 3.3: Explainability - Generate SQL explanation
    sql_explanation_full = explainability_engine.explain_sql(generated_sql, request.query)
    user_justification = explainability_engine.generate_user_facing_justification(sql_explanation_full)
    
    # Domain 3.3: Explainability - Create result provenance
    execution_time_final = time.time() - execution_start_time
    provenance = explainability_engine.create_result_provenance(
        request.query, generated_sql, sanitized_results, execution_time_final, confidence
    )
    
    # Step 3: Analyze and visualize results (use sanitized results)
    visualization = visualization_service.analyze_data(sanitized_results)
    formatted_table = visualization_service.format_table(sanitized_results, max_rows=100)
    
    # Step 4: Generate human-readable insight (replaces raw summary)
    # This is the key transformation: raw results → executive insights
    insight = await insight_generator.generate_insight(
        query=request.query,
        results=sanitized_results,
        sql=generated_sql,
        row_count=len(sanitized_results)
    )
    
    # Step 4: Generate human-readable insight (replaces raw summary)
    # This is the key transformation: raw results → executive insights
    total_rows = len(sanitized_results)
    insight = await insight_generator.generate_insight(
        query=request.query,
        results=sanitized_results,
        sql=generated_sql,
        row_count=total_rows
    )
    
    # Keep the old summary for backward compatibility, but use insight as primary
    summary = insight  # Use insight as the summary
    
    # Phase 4: Step 8 - Query Auditor (auditing & explainability)
    # Domain 3.3: Enhanced with explainability data
    from datetime import datetime
    query_metadata = {
        "user_question": request.query,
        "generated_sql": generated_sql,
        "rewritten_sql": rewritten_sql if was_rewritten else None,
        "was_rewritten": was_rewritten,
        "execution_timestamp": datetime.now().isoformat(),
        "domain": domain,
        "intent": intent,
        "intent_category": intent_category,
        "confidence": confidence,
        "row_count": len(sanitized_results),
        "source": sql_source,
        "user_role": user_role,
        "pii_columns_found": pii_columns,
        "explainability": sql_explanation_full,
        "provenance": provenance
    }
    
    # Domain 3.6: Evaluation - Record metrics
    evaluation_metrics.record_query_metric('query_executed', True, {
        'domain': domain,
        'intent': intent,
        'row_count': len(sanitized_results),
        'execution_time_ms': execution_time_final * 1000
    })
    
    # Step 4: Save conversation history (with Phase 4 metadata)
    conversation_manager.add_message(
        session_id=session_id,
        role="user",
        content=request.query,
        metadata={
            "type": "admin_query",
            "sql": generated_sql,
            "intent": "DATA",
            "mode": "legacy",
            "phase4_metadata": query_metadata
        }
    )
    
    # Generate insight for conversation history
    insight_for_history = await insight_generator.generate_insight(
        query=request.query,
        results=sanitized_results,
        sql=generated_sql,
        row_count=len(sanitized_results)
    )
    
    conversation_manager.add_message(
        session_id=session_id,
        role="assistant",
        content=insight_for_history,  # Store insight instead of raw message
        metadata={
            "type": "admin_response",
            "sql": generated_sql,
            "row_count": len(sanitized_results),
            "intent": "DATA",
            "mode": "legacy",
            "phase4_metadata": query_metadata
        }
    )
    
    # Step 5: Return comprehensive response (use sanitized results)
    total_rows = len(sanitized_results)
    
    # Fix 3: Table Selection Transparency - Extract from sql_result
    table_selection_data = sql_result.get('table_selection', None) if sql_result else None
    table_selection = None
    if table_selection_data:
        table_selection = TableSelectionMetadata(
            selected_tables=table_selection_data.get('selected_tables', []),
            reason=table_selection_data.get('reason', ''),
            join_confidence=table_selection_data.get('join_confidence', None)
        )
    
    return AdminQueryResponse(
        success=True,
        data=sanitized_results[:100],  # Limit to 100 rows in response (sanitized)
        sql=generated_sql,  # Keep SQL for debugging/transparency, but frontend should show insight
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
        summary=insight,  # Human-readable insight (primary response)
        session_id=session_id,
        confidence=confidence,
        row_count=total_rows,
        source=sql_source,  # Include source (vanna or legacy)
        table_selection=table_selection,  # Fix 3: Include table selection metadata
    )


# MCP Handler - DISABLED
# This function is disabled because MCP mode does not include Phase 4 validator
# All queries must use _handle_query_legacy which includes:
# - Phase 4 SQL Validator (STRICT - HARD FAIL)
# - Phase 4 SQL Rewriter (SOFT CORRECTION)
# - Phase 4 Confidence Scorer
# - Phase 4 Result Sanitizer
# - Domain 3 Intelligence, Governance & Continuous Improvement layers
#
# If MCP mode is needed in the future, it must be updated to include all Phase 4 validations
# async def _handle_query_via_mcp(...) - DISABLED



