"""
Optimized streaming endpoint with async support
"""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
import json
import uuid
import random
from typing import Optional

from app.services.ollama_client import get_ollama_client
from app.services.rag_service import rag_service
from app.services.conversation_manager import conversation_manager
from app.services.branch_detector import BranchDetector
from app.services.performance_optimizer import PerformanceOptimizer
from app.services.response_cache import get_response_cache
from app.core.config import settings

router = APIRouter()


def _format_sse(data: dict) -> str:
    """Format data as Server-Sent Event"""
    return f"data: {json.dumps(data)}\n\n"


@router.post("/stream")
async def stream_endpoint(request: Request):
    """
    High-performance streaming endpoint with:
    - Async Ollama client with HTTP/2
    - Conversation history management
    - Branch-specific context
    - Optimized RAG retrieval with caching
    """
    try:
        body = await request.json()
        user_prompt = body.get("query", "").strip()
        session_id = body.get("session_id") or str(uuid.uuid4())
        explicit_branch_id = body.get("branch_id")  # Optional explicit branch ID
        
        # Smart branch detection: explicit > query detection > session history
        branch_id = BranchDetector.smart_detect(
            query=user_prompt,
            session_id=session_id,
            explicit_branch_id=explicit_branch_id,
            conversation_manager=conversation_manager
        )
        
        if not user_prompt:
            raise HTTPException(
                status_code=400,
                detail="Please provide a 'query' string in JSON body."
            )
        
        # Get Ollama client
        ollama_client = await get_ollama_client()
        
        # Check if it's a simple greeting or query that doesn't need RAG
        simple_greetings = ['hello', 'hi', 'hey', 'good morning', 'good afternoon', 'good evening', 'greetings']
        is_simple_greeting = user_prompt.lower().strip() in simple_greetings or len(user_prompt.strip()) < 10
        
        rag_context = None
        if not is_simple_greeting:
            # Retrieve relevant context asynchronously (optimized for speed)
            # Use more documents for better accuracy when branch is specified
            retrieval_k = 5 if branch_id else settings.RAG_TOP_K  # More docs for branch-specific queries
            rag_context = await rag_service.retrieve_async(
                query=user_prompt,
                k=retrieval_k,
                branch_id=branch_id,
                use_cache=True,
                fast_mode=False if branch_id else settings.OPTIMIZE_FOR_SPEED  # Don't use fast mode for branch queries
            )
            
            # Validate that we have context, especially for branch-specific queries
            if branch_id and not rag_context:
                # Try without branch filter as fallback, but warn the LLM
                rag_context = await rag_service.retrieve_async(
                    query=user_prompt,
                    k=3,
                    branch_id=None,  # Try general
                    use_cache=True,
                    fast_mode=True
                )
                if rag_context:
                    rag_context = f"WARNING: Branch-specific information not found. General information:\n{rag_context}"
        
        # Get conversation history
        conversation_history = conversation_manager.get_messages(
            session_id=session_id,
            max_messages=8  # Keep last 8 messages for context
        )
        
        # Check response cache (only if enabled and context hasn't changed much)
        if settings.RESPONSE_CACHE_ENABLED:
            response_cache = get_response_cache()
            cached_response = response_cache.get(
                query=user_prompt,
                session_id=session_id,
                conversation_history=conversation_history,
                branch_id=branch_id
            )
            
            if cached_response:
                # Return cached response immediately (instant!)
                async def cached_event_generator():
                    # Stream cached response in chunks for consistency
                    chunk_size = 30
                    for i in range(0, len(cached_response), chunk_size):
                        chunk = cached_response[i:i+chunk_size]
                        yield _format_sse({
                            "type": "chunk",
                            "content": chunk,
                            "session_id": session_id
                        })
                    yield _format_sse({
                        "type": "done",
                        "session_id": session_id
                    })
                
                # Still save to conversation history
                conversation_manager.add_message(
                    session_id=session_id,
                    role="assistant",
                    content=cached_response,
                    branch_id=branch_id
                )
                
                return StreamingResponse(
                    cached_event_generator(),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "X-Accel-Buffering": "no",
                        "X-Cached": "true",  # Indicate this was cached
                    }
                )
        
        # Build comprehensive context
        llm_context = conversation_manager.get_context_for_llm(
            session_id=session_id,
            branch_id=branch_id,
            rag_context=rag_context
        )
        
        # Add user message to history
        conversation_manager.add_message(
            session_id=session_id,
            role="user",
            content=user_prompt,
            branch_id=branch_id
        )
        
        # Prepare messages for LLM
        messages = conversation_history + [
            {"role": "user", "content": user_prompt}
        ]
        
        # Stream response
        async def event_generator():
            """Generate SSE events from Ollama stream with smart buffering"""
            full_response = ""
            buffer = ""
            buffer_size = getattr(settings, "STREAM_BUFFER_SIZE", 30)  # Configurable buffer size
            
            try:
                # Get optimized options based on query length
                optimized_options = PerformanceOptimizer.get_optimized_llm_options(
                    len(user_prompt)
                ) if settings.OPTIMIZE_FOR_SPEED else {
                    "num_predict": settings.DEFAULT_NUM_PREDICT,
                    "temperature": 0.7,
                    "top_p": 0.9,
                }
                
                async for chunk in ollama_client.stream_chat(
                    messages=messages,
                    context=llm_context,
                    options=optimized_options,
                    branch_id=branch_id  # Pass branch_id for strict filtering
                ):
                    if chunk:
                        full_response += chunk
                        buffer += chunk
                        
                        # Send buffer when:
                        # 1. Buffer is large enough (>= buffer_size chars)
                        # 2. We hit a word boundary (space, punctuation, newline)
                        # 3. Buffer ends with sentence-ending punctuation
                        # 4. We have a complete word (space after word)
                        should_flush = (
                            len(buffer) >= buffer_size or
                            (chunk in [' ', '\n'] and len(buffer) >= 5) or  # Word boundary with some content
                            buffer.rstrip().endswith(('.', '!', '?', '\n\n'))  # Sentence end
                        )
                        
                        if should_flush and buffer.strip():
                            yield _format_sse({
                                "type": "chunk",
                                "content": buffer,
                                "session_id": session_id
                            })
                            buffer = ""
                
                # Send any remaining buffer
                if buffer.strip():
                    yield _format_sse({
                        "type": "chunk",
                        "content": buffer,
                        "session_id": session_id
                    })
                
                # Save assistant response to history
                if full_response:
                    conversation_manager.add_message(
                        session_id=session_id,
                        role="assistant",
                        content=full_response,
                        branch_id=branch_id
                    )
                    
                    # Cache response if enabled and conditions are met
                    if settings.RESPONSE_CACHE_ENABLED:
                        response_cache = get_response_cache()
                        response_cache.set(
                            query=user_prompt,
                            response=full_response,
                            session_id=session_id,
                            conversation_history=conversation_history,
                            branch_id=branch_id,
                            min_length=settings.RESPONSE_CACHE_MIN_LENGTH
                        )
                    
                    # Check if response should include a follow-up question
                    # Only if response is substantial and doesn't already ask a question
                    should_ask_followup = (
                        len(full_response) > 50 and  # Substantial answer
                        not any(q in full_response.lower() for q in ['?', 'anything else', 'more information', 'help', 'satisfied']) and
                        not full_response.strip().endswith('?')
                    )
                    
                    if should_ask_followup:
                        # Add a friendly follow-up
                        followup_options = [
                            " Does this help?",
                            " I hope that answers your question. Is there anything else you'd like to know?",
                            " Does this information help? Feel free to ask if you need more details.",
                            " I hope this is helpful. Would you like more information on this topic?",
                        ]
                        followup = random.choice(followup_options)
                        yield _format_sse({
                            "type": "chunk",
                            "content": followup,
                            "session_id": session_id
                        })
                        # Update full response with followup
                        full_response += followup
                        conversation_manager._conversations[session_id][-1]["content"] = full_response
                
                # Send completion event
                yield _format_sse({
                    "type": "done",
                    "session_id": session_id
                })
                
            except Exception as e:
                yield _format_sse({
                    "type": "error",
                    "error": str(e),
                    "session_id": session_id
                })
        
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"  # Disable nginx buffering
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse(
            {"error": str(e), "type": "stream_error"},
            status_code=500
        )


@router.post("/stream/clear")
async def clear_conversation(request: Request):
    """Clear conversation history for a session"""
    try:
        body = await request.json()
        session_id = body.get("session_id")
        
        if not session_id:
            raise HTTPException(
                status_code=400,
                detail="Please provide a 'session_id' in JSON body."
            )
        
        conversation_manager.clear_conversation(session_id)
        return {"status": "cleared", "session_id": session_id}
    
    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse(
            {"error": str(e)},
            status_code=500
        )
