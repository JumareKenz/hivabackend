"""
Chat endpoint for frontend integration.

This endpoint handles chat requests from the frontend and routes them
to the appropriate RAG service or state/provider KB.
"""

from __future__ import annotations

import uuid
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.services.ollama_client import get_ollama_client
from app.services.rag_service import rag_service
from app.services.conversation_manager import conversation_manager
from app.services.branch_detector import BranchDetector


router = APIRouter()


@router.post("/chat")
async def chat(payload: dict):
    """
    Main chat endpoint for frontend.
    
    Request body:
    {
        "query": "user question",
        "session_id": "optional session id",
        "user_role": "customer" | "provider" | etc.
    }
    
    Returns:
    {
        "answer": "response text",
        "session_id": "session id"
    }
    """
    try:
        user_query = (payload.get("query") or "").strip()
        session_id = payload.get("session_id") or str(uuid.uuid4())
        user_role = payload.get("user_role", "customer")
        explicit_branch_id = payload.get("branch_id")

        if not user_query:
            return JSONResponse(
                {"error": "Please provide a query.", "session_id": session_id}, 
                status_code=400
            )

        # Detect branch if not explicitly provided
        branch_id = BranchDetector.smart_detect(
            query=user_query,
            session_id=session_id,
            explicit_branch_id=explicit_branch_id,
            conversation_manager=conversation_manager,
        )

        # Get LLM client
        ollama_client = await get_ollama_client()

        # Retrieve RAG context
        rag_context = await rag_service.retrieve_async(
            query=user_query, 
            k=5, 
            branch_id=branch_id, 
            use_cache=True
        )
        
        if not rag_context:
            return {
                "answer": "I couldn't find specific information about this in our knowledge base. Please contact support for more information.",
                "session_id": session_id,
            }

        # Build conversation context
        conversation_history = conversation_manager.get_messages(
            session_id=session_id, 
            max_messages=8
        )
        llm_context = conversation_manager.get_context_for_llm(
            session_id=session_id,
            branch_id=branch_id,
            rag_context=rag_context,
        )

        # Add user message to conversation
        conversation_manager.add_message(
            session_id=session_id, 
            role="user", 
            content=user_query, 
            branch_id=branch_id
        )

        # Generate response
        answer = await ollama_client.chat(
            messages=conversation_history + [{"role": "user", "content": user_query}],
            context=llm_context,
            branch_id=branch_id,
        )

        # Add assistant response to conversation
        conversation_manager.add_message(
            session_id=session_id, 
            role="assistant", 
            content=answer, 
            branch_id=branch_id
        )

        return {
            "answer": answer, 
            "session_id": session_id,
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            {
                "error": "AI service error. Our team has been notified.",
                "code": 500,
                "type": "backend_error",
                "details": {"message": str(e)},
                "session_id": payload.get("session_id", "unknown")
            }, 
            status_code=500
        )


