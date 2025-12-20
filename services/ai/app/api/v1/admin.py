"""
Admin Insights API - Chat with Data endpoint for internal staff
Enhanced with robust intent routing and fail-safe guards
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any, List
import uuid
import random
import logging
from pydantic import BaseModel

from app.core.auth import admin_auth
from app.services.database_service import database_service
from app.services.enhanced_sql_generator import enhanced_sql_generator
from app.services.privacy_service import privacy_service
from app.services.pii_validator import pii_validator
from app.services.analytical_summary_service import analytical_summary_service
from app.services.visualization_service import visualization_service
from app.services.conversation_manager import conversation_manager
from app.services.schema_rag_service import schema_rag_service
from app.services.intent_router import intent_router, IntentType
from app.services.narrative_analyzer import narrative_analyzer

logger = logging.getLogger(__name__)

router = APIRouter()


class AdminQueryRequest(BaseModel):
    """Request model for admin data queries"""
    query: str
    session_id: Optional[str] = None
    refine_query: Optional[bool] = False  # If True, uses conversation history for context


class AdminQueryResponse(BaseModel):
    """Response model for admin data queries with enhanced formatting"""
    success: bool
    data: Optional[List[Dict[str, Any]]] = None
    sql_query: Optional[str] = None  # Renamed from 'sql' for clarity
    sql_explanation: Optional[str] = None
    analytical_summary: Optional[str] = None  # High-level professional narrative
    viz_suggestion: Optional[Dict[str, Any]] = None  # Visualization recommendation
    visualization: Optional[Dict[str, Any]] = None  # Legacy field for backward compatibility
    summary: Optional[str] = None  # Legacy field for backward compatibility
    session_id: str
    error: Optional[str] = None
    confidence: Optional[float] = None
    correction_attempts: Optional[int] = None  # Number of self-correction attempts
    privacy_blocked: Optional[bool] = False  # Whether query was blocked for privacy
    privacy_warning: Optional[str] = None  # Privacy warning message if PII detected
    pii_detected: Optional[List[str]] = None  # List of detected PII types


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
        # Check if database is available
        if not database_service.pool:
            raise HTTPException(
                status_code=503,
                detail="Analytics database is not configured or unavailable"
            )
        
        # STEP 0: Validate user input for PII/PHI patterns
        is_safe, redacted_query, detected_pii = pii_validator.validate_user_query(request.query)
        
        if not is_safe:
            # Block queries that attempt to identify individuals
            if 'individual_identification_query' in detected_pii:
                return AdminQueryResponse(
                    success=False,
                    session_id=request.session_id or str(uuid.uuid4()),
                    error="For privacy compliance, I only provide insights at the cohort level. I cannot identify specific individuals or answer 'who' questions about patients.",
                    privacy_blocked=True,
                    privacy_warning=pii_validator.get_privacy_warning(detected_pii),
                    pii_detected=detected_pii
                )
            # For other PII, warn but allow (data is already masked in views)
            privacy_warning = pii_validator.get_privacy_warning(detected_pii)
        else:
            privacy_warning = None
            detected_pii = []
        
        # Get or create session ID
        session_id = request.session_id or str(uuid.uuid4())
        
        # Get conversation history (always use it for context)
        conversation_history = conversation_manager.get_messages(
            session_id=session_id,
            max_messages=10
        )
        
        # Check if we have previous query results
        previous_results = conversation_manager.get_last_query_results(session_id)
        has_previous_results = previous_results is not None
        
        # STEP 1: Intent Router - Classify user intent
        intent_result = await intent_router.classify_intent(
            user_query=request.query,
            conversation_history=conversation_history,
            has_previous_results=has_previous_results
        )
        
        intent = intent_result.get("intent")
        requires_sql = intent_result.get("requires_sql", True)
        requires_previous_data = intent_result.get("requires_previous_data", False)
        intent_confidence = intent_result.get("confidence", 0.7)
        
        logger.info(
            f"Intent classified: {intent} (confidence: {intent_confidence:.2f}), "
            f"requires_sql: {requires_sql}, requires_previous_data: {requires_previous_data}"
        )
        
        # CRITICAL: Save user message to conversation history FIRST (for all intents)
        conversation_manager.add_message(
            session_id=session_id,
            role="user",
            content=request.query,
            metadata={
                "type": "admin_query",
                "intent": intent.value if intent else "unknown",
                "intent_confidence": intent_confidence
            }
        )
        
        # Handle GREETING intent - NO SQL generation
        if intent == IntentType.GREETING:
            greetings = [
                "Hello! I'm your data analytics assistant. I can help you explore your healthcare data. What would you like to know?",
                "Hi there! I'm here to help you analyze your data. Try asking something like 'Show me the total number of claims' or 'Compare claim volumes by state'.",
                "Hello! I can help you query and analyze your data. What insights are you looking for today?",
                "Hi! I'm your data assistant. Ask me anything about your claims, transactions, or other data. For example: 'What are the total claims for April in Zamfara?'",
                "Greetings! I'm ready to help you explore your data. What would you like to discover today?",
                "Hello! Welcome to the data analytics assistant. I can help you find insights in your healthcare data. What questions do you have?"
            ]
            greeting_msg = random.choice(greetings)
            
            # Save assistant response
            conversation_manager.add_message(
                session_id=session_id,
                role="assistant",
                content=greeting_msg,
                metadata={"type": "greeting_response", "intent": "greeting"}
            )
            
            logger.info(f"Greeting response sent for session: {session_id}")
            return AdminQueryResponse(
                success=True,
                session_id=session_id,
                analytical_summary=greeting_msg,
                summary=greeting_msg,
                data=[],
                sql_query=None,
                confidence=intent_confidence
            )
        
        # Handle NARRATIVE intent - analyze previous results, NO SQL
        if intent == IntentType.NARRATIVE:
            if not has_previous_results:
                # No previous results available, but user wants narrative
                # Fall back to asking for clarification or treating as data query
                logger.warning(f"Narrative intent but no previous results for session: {session_id}")
                clarification_msg = (
                    "I'd be happy to provide analysis! However, I don't have any previous query results to analyze. "
                    "Could you ask a specific data question first? For example: 'Show me the total number of claims' "
                    "or 'Compare claim volumes by state'."
                )
                
                conversation_manager.add_message(
                    session_id=session_id,
                    role="assistant",
                    content=clarification_msg,
                    metadata={"type": "narrative_fallback", "intent": "narrative"}
                )
                
                return AdminQueryResponse(
                    success=True,
                    session_id=session_id,
                    analytical_summary=clarification_msg,
                    summary=clarification_msg,
                    data=[],
                    sql_query=None,
                    confidence=0.8
                )
            
            try:
                logger.info(f"Processing narrative analysis for session: {session_id}")
                narrative_result = await narrative_analyzer.analyze_results(
                    results=previous_results.get("results", []),
                    original_query=previous_results.get("query", ""),
                    sql_query=previous_results.get("sql"),
                    conversation_context=conversation_history
                )
                
                # Build response text
                response_text = narrative_result.get("narrative", "")
                insights = narrative_result.get("insights", [])
                suggestions = narrative_result.get("suggestions", [])
                
                if insights:
                    response_text += "\n\n**Key Insights:**\n" + "\n".join(f"• {insight}" for insight in insights[:3])
                if suggestions:
                    response_text += "\n\n**You might also want to:**\n" + "\n".join(f"• {suggestion}" for suggestion in suggestions[:3])
                
                # Save assistant response
                conversation_manager.add_message(
                    session_id=session_id,
                    role="assistant",
                    content=response_text,
                    metadata={
                        "type": "narrative_response",
                        "intent": "narrative",
                        "original_query": previous_results.get("query", "")
                    }
                )
                
                logger.info(f"Narrative analysis completed for session: {session_id}")
                return AdminQueryResponse(
                    success=True,
                    session_id=session_id,
                    analytical_summary=response_text,
                    summary=response_text,
                    data=previous_results.get("results", [])[:10],  # Include sample data
                    sql_query=previous_results.get("sql"),  # Show previous SQL for context
                    confidence=0.95
                )
            except Exception as e:
                logger.error(f"Narrative analysis failed: {e}", exc_info=True)
                # Fall through to normal query processing with a helpful message
                error_msg = (
                    "I encountered an issue analyzing the previous results. "
                    "Let me try to answer your question with a new query instead."
                )
                # Note: We'll continue to SQL generation below
        
        # Handle CLARIFICATION intent - NO SQL generation
        if intent == IntentType.CLARIFICATION:
            clarification_msg = (
                "I'd be happy to clarify! Could you provide more details about what you'd like to know? "
                "For example, you could ask about:\n"
                "• Specific states or regions (e.g., 'Show me claims in Zamfara')\n"
                "• Time periods (e.g., 'Claims for October 2025')\n"
                "• Metrics or comparisons (e.g., 'Compare claim volumes by state')\n"
                "• Aggregations (e.g., 'Total number of claims')\n\n"
                "What specific information are you looking for?"
            )
            
            conversation_manager.add_message(
                session_id=session_id,
                role="assistant",
                content=clarification_msg,
                metadata={"type": "clarification_response", "intent": "clarification"}
            )
            
            logger.info(f"Clarification response sent for session: {session_id}")
            return AdminQueryResponse(
                success=True,
                session_id=session_id,
                analytical_summary=clarification_msg,
                summary=clarification_msg,
                data=[],
                sql_query=None,
                confidence=0.9
            )
        
        # FAIL-SAFE GUARD: If intent doesn't require SQL, don't generate SQL
        if not requires_sql:
            logger.warning(
                f"Intent {intent} marked as requires_sql=False, but reached SQL generation. "
                f"This should not happen. Returning friendly message."
            )
            friendly_msg = (
                "I understand your question, but I'm not sure how to process it as a data query. "
                "Could you rephrase it? For example: 'Show me the total number of claims' or "
                "'Compare claim volumes by state'."
            )
            
            conversation_manager.add_message(
                session_id=session_id,
                role="assistant",
                content=friendly_msg,
                metadata={"type": "fallback_response", "intent": intent.value if intent else "unknown"}
            )
            
            return AdminQueryResponse(
                success=True,
                session_id=session_id,
                analytical_summary=friendly_msg,
                summary=friendly_msg,
                data=[],
                sql_query=None,
                confidence=0.7
            )
        
        # For DATA_QUERY and FOLLOW_UP_QUERY, continue with SQL generation below
        logger.info(f"Proceeding with SQL generation for intent: {intent}")
        
        # Step 1: Schema-RAG - Map user entities to database columns
        entity_mappings = await schema_rag_service.map_entities_to_columns(request.query)
        
        # Step 2: Generate SQL from natural language using enhanced generator
        # Use redacted query if PII was detected
        query_to_process = redacted_query if redacted_query != request.query else request.query
        try:
            import asyncio
            # Add timeout for SQL generation (25 seconds to leave buffer for API timeout)
            sql_result = await asyncio.wait_for(
                enhanced_sql_generator.generate_sql(
                    natural_language_query=query_to_process,
                    conversation_history=conversation_history
                ),
                timeout=25.0
            )
            
            # Check if query was blocked for privacy
            if sql_result.get("privacy_blocked", False) or sql_result.get("sql") is None:
                error_msg = sql_result.get("explanation", "Query blocked for privacy compliance")
                if not error_msg:
                    error_msg = "For privacy compliance, I only provide insights at the cohort level. I cannot identify specific individuals or answer questions about specific patients."
                
                return AdminQueryResponse(
                    success=False,
                    session_id=session_id,
                    error=error_msg,
                    privacy_blocked=True,
                    privacy_warning=privacy_warning or pii_validator.get_privacy_warning(detected_pii),
                    pii_detected=detected_pii if detected_pii else None
                )
            
            generated_sql = sql_result["sql"]
            sql_explanation = sql_result["explanation"]
            confidence = sql_result["confidence"]
            correction_attempts = sql_result.get("correction_attempts", 0)
            
            # Log the generated SQL for debugging
            logger.debug(f"Generated SQL for query '{request.query[:50]}...': {generated_sql[:200]}...")
            
        except asyncio.TimeoutError:
            logger.error(f"SQL generation timeout for session: {session_id}, query: {request.query[:50]}")
            error_msg = (
                "I'm taking too long to generate a query for your question. "
                "This might be because the question is complex. "
                "Could you try breaking it down into simpler parts or rephrasing it?"
            )
            
            conversation_manager.add_message(
                session_id=session_id,
                role="assistant",
                content=error_msg,
                metadata={"type": "error_response", "error_type": "timeout"}
            )
            
            return AdminQueryResponse(
                success=False,
                session_id=session_id,
                error=error_msg
            )
        except Exception as e:
            error_msg = str(e)
            logger.error(f"SQL generation error for session {session_id}: {error_msg}", exc_info=True)
            
            # Check if it's a SQL extraction error
            if "Generated query is not a SELECT statement" in error_msg:
                user_friendly_msg = (
                    "I had trouble understanding your question in a way that I can query the database. "
                    "Could you try rephrasing it? For example:\n"
                    "• 'Show me the total number of claims'\n"
                    "• 'Compare claim volumes by state'\n"
                    "• 'What are the top 10 providers by volume?'"
                )
            else:
                user_friendly_msg = (
                    "I encountered an error while processing your question. "
                    "Please try rephrasing it or breaking it into simpler parts."
                )
            
            conversation_manager.add_message(
                session_id=session_id,
                role="assistant",
                content=user_friendly_msg,
                metadata={"type": "error_response", "error_type": "sql_generation", "raw_error": error_msg[:200]}
            )
            
            return AdminQueryResponse(
                success=False,
                session_id=session_id,
                error=user_friendly_msg
            )
        
        # Step 2: Validate SQL query for PII leakage attempts
        sql_is_safe, sql_error = pii_validator.validate_sql_query(generated_sql)
        if not sql_is_safe:
            return AdminQueryResponse(
                success=False,
                session_id=session_id,
                sql_query=generated_sql,
                sql_explanation=sql_explanation,
                error=f"Query blocked for privacy compliance: {sql_error}",
                privacy_blocked=True,
                privacy_warning="Query attempts to reverse-engineer hashed identifiers or access PII directly."
            )
        
        # Step 3: Execute SQL query (read-only) - database_service already enforces this
        try:
            query_results = await database_service.execute_query(generated_sql)
        except Exception as e:
            return AdminQueryResponse(
                success=False,
                session_id=session_id,
                sql_query=generated_sql,
                sql_explanation=sql_explanation,
                error=f"Query execution failed: {str(e)}"
            )
        
        # Step 4: Apply privacy compliance - small cell suppression
        query_results = privacy_service.apply_small_cell_suppression(query_results)
        
        # Step 5: Validate query results for stray PII/PHI patterns (final output validation)
        sanitized_results, output_pii_detected = pii_validator.validate_query_results(query_results)
        query_results = sanitized_results  # Use sanitized results
        
        # Update privacy warning if PII was detected in output
        if output_pii_detected:
            output_warning = pii_validator.get_privacy_warning(output_pii_detected)
            if privacy_warning:
                privacy_warning += " " + output_warning
            else:
                privacy_warning = output_warning
            detected_pii.extend(output_pii_detected)
            detected_pii = list(set(detected_pii))  # Remove duplicates
        
        # Step 6: Generate analytical summary and visualization suggestion
        analytical_summary = await analytical_summary_service.generate_summary(
            query_results,
            generated_sql,
            request.query
        )
        
        viz_suggestion = analytical_summary_service.suggest_visualization(
            query_results,
            generated_sql
        )
        
        # Step 7: Legacy visualization support (for backward compatibility)
        visualization = visualization_service.analyze_data(query_results)
        formatted_table = visualization_service.format_table(query_results, max_rows=100)
        summary = visualization_service.generate_summary(query_results, sql_explanation)
        
        # Step 8: Save conversation history with results for narrative analysis
        # Note: User message was already saved at the beginning, so we only save assistant response here
        conversation_manager.add_message(
            session_id=session_id,
            role="assistant",
            content=analytical_summary or f"Query executed successfully. Returned {len(query_results)} results.",
            metadata={
                "type": "admin_response",
                "sql": generated_sql,
                "row_count": len(query_results),
                "analytical_summary": analytical_summary,
                "query": request.query,
                "results": query_results[:20],  # Store first 20 results for narrative analysis
                "intent": intent.value if intent else "data_query",
                "confidence": confidence
            }
        )
        
        logger.info(
            f"Query completed successfully for session {session_id}: "
            f"{len(query_results)} results, confidence: {confidence:.2f}"
        )
        
        # Step 9: Return comprehensive response with enhanced formatting
        return AdminQueryResponse(
            success=True,
            data=query_results[:100],  # Limit to 100 rows in response
            sql_query=generated_sql,  # Enhanced field name
            sql_explanation=sql_explanation,
            analytical_summary=analytical_summary,  # New: professional narrative
            viz_suggestion=viz_suggestion,  # New: visualization recommendation
            visualization={  # Legacy field for backward compatibility
                "type": visualization["type"],
                "table": formatted_table,
                "suggestions": visualization.get("suggestions", []),
                "row_count": visualization["row_count"],
                "columns": visualization["columns"]
            },
            summary=summary,  # Legacy field for backward compatibility
            session_id=session_id,
            confidence=confidence,
            correction_attempts=correction_attempts,
            privacy_blocked=False,
            privacy_warning=privacy_warning,  # Privacy warning if PII detected
            pii_detected=detected_pii if detected_pii else None  # List of detected PII types
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in admin_query_data: {e}", exc_info=True)
        session_id = request.session_id or str(uuid.uuid4())
        
        # Save error to conversation history
        conversation_manager.add_message(
            session_id=session_id,
            role="assistant",
            content="I encountered an unexpected error. Please try again or rephrase your question.",
            metadata={"type": "error_response", "error_type": "unexpected"}
        )
        
        return AdminQueryResponse(
            success=False,
            session_id=session_id,
            error="An unexpected error occurred. Please try again or contact support if the issue persists."
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
        
        # Always use analytics views for privacy compliance
        schema_info = await database_service.get_schema_info(table_name=table_name, use_analytics_views=True)
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
    
    return {
        "status": "healthy",
        "database_available": db_available,
        "admin_features_enabled": True,
        "user": user_info.get("user_id", "unknown")
    }


@router.post("/admin/inspect-database")
async def inspect_database_endpoint(
    user_info: Dict[str, Any] = Depends(admin_auth.require_admin),
    force_refresh: bool = False
):
    """
    Inspect database and generate admin query documentation
    
    Requires: Admin authentication
    """
    try:
        from app.services.schema_loader import schema_loader
        from app.services.database_inspector import database_inspector
        from pathlib import Path
        import json
        
        # Run inspection
        print("Starting database inspection...")
        inspection = await database_inspector.inspect_database()
        
        # Load comprehensive schema
        comprehensive_schema = await schema_loader.load_comprehensive_schema(force_refresh=force_refresh)
        
        # Generate documentation (inline function to avoid import issues)
        def generate_doc(schema: Dict) -> str:
            """Generate admin documentation"""
            patterns = schema.get('query_patterns', [])
            table_schemas = schema.get('table_schemas', {})
            
            doc = "# Admin Query Guide - Common Questions & Queries\n\n"
            doc += "This document lists common questions admins may ask.\n\n"
            
            # Add query patterns
            if patterns:
                doc += "## Common Query Patterns\n\n"
                for pattern in patterns[:20]:
                    doc += f"### {pattern.get('description', 'Query Pattern')}\n"
                    doc += f"**Example:** `{pattern.get('example_query', 'N/A')}`\n\n"
            
            # Add table information
            if table_schemas:
                doc += "## Available Tables\n\n"
                for table_name, table_info in list(table_schemas.items())[:30]:
                    if not table_name.startswith('information_schema'):
                        doc += f"### {table_name}\n"
                        columns = table_info.get('columns', [])
                        if columns:
                            doc += f"**Columns:** {len(columns)}\n\n"
            
            return doc
        
        doc = generate_doc(comprehensive_schema)
        
        # Save documentation
        output_file = Path(__file__).parent.parent.parent / "ADMIN_QUERY_GUIDE.md"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(doc)
        
        # Save schema JSON
        schema_file = Path(__file__).parent.parent.parent / "database_schema.json"
        with open(schema_file, 'w', encoding='utf-8') as f:
            json.dump(comprehensive_schema, f, indent=2, default=str)
        
        return {
            "success": True,
            "message": "Database inspection complete",
            "tables_analyzed": len(inspection.get('tables', [])),
            "query_patterns": len(comprehensive_schema.get('query_patterns', [])),
            "relationships": len(inspection.get('relationships', {})),
            "documentation_file": str(output_file),
            "schema_file": str(schema_file)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Database inspection failed"
        }



