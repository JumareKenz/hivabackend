"""
Optimized non-streaming ask endpoint
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import uuid
import random
from typing import Optional

from app.services.ollama_client import get_ollama_client
from app.services.rag_service import rag_service
from app.services.conversation_manager import conversation_manager
from app.services.branch_detector import BranchDetector

router = APIRouter()


@router.post("/ask")
async def ask(payload: dict):
    """
    High-performance non-streaming endpoint with:
    - Async Ollama client
    - Conversation history
    - Branch-specific context
    - Optimized RAG
    """
    try:
        user_query = payload.get("query", "").strip()
        session_id = payload.get("session_id") or str(uuid.uuid4())
        explicit_branch_id = payload.get("branch_id")
        
        # Smart branch detection: explicit > query detection > session history
        branch_id = BranchDetector.smart_detect(
            query=user_query,
            session_id=session_id,
            explicit_branch_id=explicit_branch_id,
            conversation_manager=conversation_manager
        )
        
        if not user_query:
            return JSONResponse(
                {"answer": "Please provide a query.", "session_id": session_id},
                status_code=400
            )
        
        # Get Ollama client
        ollama_client = await get_ollama_client()
        
        # Retrieve context asynchronously
        rag_context = await rag_service.retrieve_async(
            query=user_query,
            k=5,
            branch_id=branch_id,
            use_cache=True
        )
        
        if not rag_context:
            return {
                "answer": "I couldn't find specific information about this in our knowledge base. Please contact us at +2349012345678 for more information.",
                "session_id": session_id
            }
        
        # Get conversation history
        conversation_history = conversation_manager.get_messages(
            session_id=session_id,
            max_messages=8
        )
        
        # Build context
        llm_context = conversation_manager.get_context_for_llm(
            session_id=session_id,
            branch_id=branch_id,
            rag_context=rag_context
        )
        
        # Add user message to history
        conversation_manager.add_message(
            session_id=session_id,
            role="user",
            content=user_query,
            branch_id=branch_id
        )
        
        # Prepare messages
        messages = conversation_history + [
            {"role": "user", "content": user_query}
        ]
        
        # Get response
        answer = await ollama_client.chat(
            messages=messages,
            context=llm_context,
            branch_id=branch_id  # Pass branch_id for strict filtering
        )
        
        # Add friendly follow-up if answer is substantial and doesn't already ask a question
        if (
            len(answer) > 50 and
            not any(q in answer.lower() for q in ['?', 'anything else', 'more information', 'help', 'satisfied']) and
            not answer.strip().endswith('?')
        ):
            followup_options = [
                " Does this help?",
                " I hope that answers your question. Is there anything else you'd like to know?",
                " Does this information help? Feel free to ask if you need more details.",
                " I hope this is helpful. Would you like more information on this topic?",
            ]
            answer += random.choice(followup_options)
        
        # Save assistant response
        conversation_manager.add_message(
            session_id=session_id,
            role="assistant",
            content=answer,
            branch_id=branch_id
        )
        
        return {
            "answer": answer,
            "session_id": session_id
        }
    
    except Exception as e:
        return JSONResponse(
            {"error": str(e), "session_id": payload.get("session_id", "unknown")},
            status_code=500
        )
