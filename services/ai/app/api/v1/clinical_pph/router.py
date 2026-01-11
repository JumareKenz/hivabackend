"""
FastAPI router for Clinical PPH knowledge base.

Provides endpoints for:
- /ask - Non-streaming query endpoint
- /stream - Streaming query endpoint (compatibility layer, returns JSON)
- /health - Health check endpoint
"""

from __future__ import annotations

import logging
import uuid
import re
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.services.conversation_manager import conversation_manager
from app.services.ollama_client import get_ollama_client
from clinical_pph.service import clinical_pph_service
from clinical_pph.store import get_or_create_collection, get_collection_count

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/clinical-pph", tags=["clinical-pph"])

KB_ID = "clinical_pph"
KB_DISPLAY_NAME = "Clinical PPH (Postpartum Hemorrhage)"


@router.post("/ask")
async def ask_clinical_pph(payload: dict):
    """
    Query the Clinical PPH knowledge base and get a response.
    
    Request body:
    {
        "query": "user question",
        "session_id": "optional session id",
        "top_k": 5  // optional, number of documents to retrieve
    }
    
    Returns:
    {
        "answer": "response text",
        "session_id": "session id",
        "kb_id": "clinical_pph",
        "kb_name": "Clinical PPH (Postpartum Hemorrhage)"
    }
    """
    try:
        user_query = (payload.get("query") or "").strip()
        session_id = payload.get("session_id") or str(uuid.uuid4())
        top_k = int(payload.get("top_k") or getattr(settings, "RAG_DEFAULT_TOP_K", 5))

        if not user_query:
            return JSONResponse(
                {"answer": "Please provide a query.", "session_id": session_id}, 
                status_code=400
            )

        logger.info(f"Query received for Clinical PPH, session_id={session_id}, query_length={len(user_query)}")

        # Retrieve KB context - use optimal number of chunks
        optimal_top_k = min(max(top_k, 5), 7)  # Use 5-7 chunks for better coverage
        rag_context = await clinical_pph_service.retrieve_async(
            query=user_query, 
            k=optimal_top_k, 
            use_cache=True
        )
        
        if not rag_context:
            logger.warning(f"No context retrieved for query='{user_query[:50]}...'")
            return {
                "answer": (
                    "I couldn't find specific information about this in the Clinical PPH knowledge base. "
                    "Please consult with a healthcare professional for clinical guidance."
                ),
                "session_id": session_id,
                "kb_id": KB_ID,
                "kb_name": KB_DISPLAY_NAME,
            }

        # Smart truncation: Keep most relevant parts, remove less relevant
        if len(rag_context) > 8000:
            logger.info(f"RAG context large ({len(rag_context)} chars), intelligently truncating")
            # Find sentence boundaries for clean truncation
            def find_sentence_end(text: str, max_pos: int) -> int:
                """Find the last sentence end before max_pos"""
                for i in range(max_pos - 1, max(0, max_pos - 200), -1):
                    if text[i] in '.!?' and (i + 1 >= len(text) or text[i + 1] in ' \n\t'):
                        return i + 1
                return max_pos
            
            if len(rag_context) > 10000:
                # Truncate at sentence boundaries
                first_end = find_sentence_end(rag_context, 6000)
                last_start = len(rag_context) - 2000
                # Find sentence start after last_start
                for i in range(last_start, min(len(rag_context), last_start + 200)):
                    if rag_context[i] in '.!?' and (i + 1 >= len(rag_context) or rag_context[i + 1] in ' \n\t'):
                        last_start = i + 1
                        break
                rag_context = rag_context[:first_end] + "\n\n[... middle content truncated ...]\n\n" + rag_context[last_start:].lstrip()
            else:
                # Truncate at sentence boundary
                truncate_pos = find_sentence_end(rag_context, 8000)
                rag_context = rag_context[:truncate_pos] + "... [truncated]"

        # Conversation context
        conversation_history = conversation_manager.get_messages(
            session_id=session_id, 
            max_messages=4
        )
        llm_context = conversation_manager.get_context_for_llm(
            session_id=session_id,
            kb_id=KB_ID,
            rag_context=rag_context,
            current_query=user_query,
        )

        # Smart truncation: Keep essential parts, truncate intelligently
        if llm_context and len(llm_context) > 12000:
            logger.warning(f"LLM context large ({len(llm_context)} chars), intelligently truncating")
            if "CRITICAL INSTRUCTIONS" in llm_context:
                parts = llm_context.split("===")
                instructions = parts[0] if parts else ""
                context_part = "===".join(parts[1:]) if len(parts) > 1 else llm_context
                llm_context = instructions + context_part[:8000] + "... [truncated for API limits]"
            else:
                llm_context = llm_context[:10000] + "... [truncated for API limits]"

        conversation_manager.add_message(
            session_id=session_id, 
            role="user", 
            content=user_query, 
            kb_id=KB_ID
        )

        # Generate response using LLM
        ollama_client = await get_ollama_client()
        
        # Prepare messages
        messages_to_send = conversation_history + [{"role": "user", "content": user_query}]
        
        # Truncate individual messages if needed
        for msg in messages_to_send:
            content = msg.get("content", "")
            if len(content) > 2000:
                truncated = content[:2000]
                last_period = truncated.rfind('.')
                if last_period > 1500:
                    msg["content"] = truncated[:last_period+1] + "... [truncated]"
                else:
                    msg["content"] = truncated + "... [truncated]"
        
        # Calculate total payload size estimate
        total_size = len(llm_context) if llm_context else 0
        total_size += sum(len(m.get("content", "")) for m in messages_to_send)
        
        logger.info(f"Payload estimate: context={len(llm_context) if llm_context else 0}, messages={len(messages_to_send)}, total={total_size}")
        
        try:
            answer = await ollama_client.chat(
                messages=messages_to_send,
                context=llm_context,
                kb_id=KB_ID,
            )
        except Exception as e:
            error_msg = str(e)
            logger.error(f"LLM API error: {error_msg}")
            
            # If it's a payload size error, try with minimal context
            if "400" in error_msg or "413" in error_msg or "payload" in error_msg.lower() or "Bad Request" in error_msg:
                logger.info("Retrying with minimal context...")
                if llm_context:
                    llm_context = rag_context[:2000] + "... [minimal context]" if rag_context else None
                messages_to_send = [{"role": "user", "content": user_query}]
                
                try:
                    answer = await ollama_client.chat(
                        messages=messages_to_send,
                        context=llm_context,
                        kb_id=KB_ID,
                    )
                    logger.info("Retry successful with minimal context")
                except Exception as retry_error:
                    logger.error(f"Retry also failed: {retry_error}")
                    answer = await ollama_client.chat(
                        messages=[{"role": "user", "content": user_query}],
                        context=None,
                        kb_id=KB_ID,
                    )
            else:
                raise

        conversation_manager.add_message(
            session_id=session_id, 
            role="assistant", 
            content=answer, 
            kb_id=KB_ID
        )

        logger.info(f"Response generated, session_id={session_id}, answer_length={len(answer)}")

        # Aggressively clean up citations, references, and verbose attribution
        # Remove source citations
        answer = re.sub(r'【[^】]*】', '', answer)
        answer = re.sub(r'\[[^\]]*source[^\]]*\]', '', answer, flags=re.IGNORECASE)
        answer = re.sub(r'\([^)]*source[^)]*\)', '', answer, flags=re.IGNORECASE)
        answer = re.sub(r'\([^)]*Source[^)]*\)', '', answer)
        
        # Remove references and citations
        answer = re.sub(r'\d+\.\s*[A-Z][^.]*\.\s*(?:BJOG|Lancet|RANZCOG|WHO|DOI)[^.]*\.', '', answer)
        answer = re.sub(r'\([^)]*DOI[^)]*\)', '', answer, flags=re.IGNORECASE)
        answer = re.sub(r'\([^)]*\d{4}[^)]*\)', '', answer)  # Remove year citations like (2023)
        
        # Remove attribution phrases
        answer = re.sub(r'Here is (a|the) (concise )?summary of (the )?information.*?knowledge base.*?:', '', answer, flags=re.IGNORECASE | re.DOTALL)
        answer = re.sub(r'Key References?.*?knowledge base.*?:', '', answer, flags=re.IGNORECASE | re.DOTALL)
        answer = re.sub(r'All points are drawn directly from[^.]*\.?', '', answer, flags=re.IGNORECASE)
        answer = re.sub(r'These are[^.]*explicitly[^.]*knowledge base\.?', '', answer, flags=re.IGNORECASE)
        answer = re.sub(r'Based on (the )?knowledge base[^.]*\.?', '', answer, flags=re.IGNORECASE)
        answer = re.sub(r'According to (the )?knowledge base[^.]*\.?', '', answer, flags=re.IGNORECASE)
        answer = re.sub(r'The knowledge base (states|says|indicates|provides)[^.]*\.?', '', answer, flags=re.IGNORECASE)
        
        # Remove table formatting and markdown
        answer = re.sub(r'\|[^|]*\|', '', answer)  # Remove table rows
        answer = re.sub(r'^#+\s*', '', answer, flags=re.MULTILINE)  # Remove markdown headers
        answer = re.sub(r'\*\*([^*]+)\*\*', r'\1', answer)  # Remove bold markdown
        answer = re.sub(r'\*([^*]+)\*', r'\1', answer)  # Remove italic markdown
        answer = re.sub(r'^\s*[-*]\s+', '', answer, flags=re.MULTILINE)  # Remove bullet points
        answer = re.sub(r'^\s*\d+\.\s+', '', answer, flags=re.MULTILINE)  # Remove numbered lists
        answer = re.sub(r'^---+$', '', answer, flags=re.MULTILINE)  # Remove horizontal rules
        answer = re.sub(r'\n\s*---+\s*\n', '\n\n', answer)  # Remove horizontal rules with spacing
        
        # Remove page references
        answer = re.sub(r'\(.*pages?\s*\d+[^)]*\)', '', answer, flags=re.IGNORECASE)
        answer = re.sub(r'pages?\s*\d+[^.]*\.?', '', answer, flags=re.IGNORECASE)
        
        # Remove standalone brackets
        answer = re.sub(r'\s*【[^】]*】\s*', ' ', answer)
        answer = re.sub(r'\s*\[[^\]]*\]\s*', ' ', answer)
        
        # Remove "Note:" sections that reference the knowledge base
        answer = re.sub(r'Note:.*?knowledge base.*?\.', '', answer, flags=re.IGNORECASE | re.DOTALL)
        answer = re.sub(r'Note:.*?provided information.*?\.', '', answer, flags=re.IGNORECASE | re.DOTALL)
        
        # Fix responses that start mid-sentence
        if answer and len(answer) > 10:
            first_word_end = answer.find(' ')
            if first_word_end > 0 and first_word_end < 50:
                first_word = answer[:first_word_end].strip('.,;:!?')
                if len(first_word) < 3 or answer[0].islower():
                    sentence_endings = ['.', '!', '?']
                    for i, char in enumerate(answer[:300]):
                        if char in sentence_endings and (i + 1 >= len(answer) or answer[i + 1] in ' \n\t'):
                            answer = answer[i + 1:].strip()
                            if answer and answer[0].islower():
                                answer = answer[0].upper() + answer[1:]
                            break
                elif answer[0].islower() and answer[0].isalpha():
                    answer = answer[0].upper() + answer[1:]
        
        # Clean up multiple spaces and periods
        answer = re.sub(r'\s+', ' ', answer)
        answer = re.sub(r'\.\s*\.', '.', answer)
        answer = re.sub(r'\s*\([^)]*drawn directly[^)]*\)\.?\s*$', '', answer, flags=re.IGNORECASE)
        answer = re.sub(r'\s*\([^)]*knowledge base[^)]*\)\.?\s*$', '', answer, flags=re.IGNORECASE)
        
        # For very long responses (especially follow-ups), truncate intelligently
        if len(answer) > 2000:
            # Try to find a good stopping point (end of sentence near 1500 chars)
            truncate_pos = 1500
            for i in range(1500, min(len(answer), 2000)):
                if answer[i] in '.!?' and (i + 1 >= len(answer) or answer[i + 1] in ' \n\t'):
                    truncate_pos = i + 1
                    break
            answer = answer[:truncate_pos].strip()
            if not answer.endswith(('.', '!', '?')):
                answer += '.'
        
        answer = answer.strip()

        return {
            "answer": answer, 
            "session_id": session_id, 
            "kb_id": KB_ID, 
            "kb_name": KB_DISPLAY_NAME
        }
    except Exception as e:
        logger.error(f"Error in ask_clinical_pph: {e}", exc_info=True)
        return JSONResponse(
            {"error": str(e), "session_id": payload.get("session_id", "unknown")}, 
            status_code=500
        )


@router.post("/stream")
async def stream_clinical_pph(payload: dict):
    """
    Streaming endpoint (compatibility layer).
    
    Currently returns JSON (non-streaming). Can be enhanced to support
    Server-Sent Events (SSE) for true token streaming in the future.
    
    Request body: Same as /ask
    Returns: Same as /ask
    """
    # For now, delegate to ask_clinical_pph
    return await ask_clinical_pph(payload)


@router.get("/health")
async def health_check():
    """
    Health check endpoint for the Clinical PPH knowledge base.
    
    Returns:
    {
        "status": "healthy" | "unhealthy",
        "kb_id": "clinical_pph",
        "kb_name": "Clinical PPH (Postpartum Hemorrhage)",
        "collection_count": number of documents,
        "cache_stats": cache statistics
    }
    """
    try:
        collection_count = get_collection_count()
        cache_stats = clinical_pph_service.get_cache_stats()
        
        status = "healthy" if collection_count > 0 else "unhealthy"
        
        return {
            "status": status,
            "kb_id": KB_ID,
            "kb_name": KB_DISPLAY_NAME,
            "collection_count": collection_count,
            "cache_stats": cache_stats,
        }
    except Exception as e:
        logger.error(f"Error in health_check: {e}", exc_info=True)
        return JSONResponse(
            {
                "status": "unhealthy",
                "kb_id": KB_ID,
                "kb_name": KB_DISPLAY_NAME,
                "error": str(e)
            },
            status_code=500
        )

