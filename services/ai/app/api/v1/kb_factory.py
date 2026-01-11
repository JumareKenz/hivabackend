"""
Router factory for state/provider knowledge bases.

Creates FastAPI routers with endpoints for:
- /ask - Non-streaming query endpoint
- /stream - Streaming query endpoint (compatibility layer, returns JSON)
- /health - Health check endpoint
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.services.conversation_manager import conversation_manager
from app.services.ollama_client import get_ollama_client
from app.state_kb.service import state_kb_service
from app.state_kb.registry import require_kb
from app.state_kb.store import get_or_create_collection

logger = logging.getLogger(__name__)


def build_kb_router(*, kb_id: str, prefix: str, tag: str) -> APIRouter:
    """
    Build a FastAPI router for a knowledge base.
    
    Args:
        kb_id: Knowledge base identifier (e.g., 'adamawa', 'providers')
        prefix: URL prefix for the router (e.g., '/states/adamawa')
        tag: OpenAPI tag for documentation
        
    Returns:
        Configured APIRouter with /ask, /stream, and /health endpoints
    """
    kb = require_kb(kb_id)
    router = APIRouter(prefix=prefix, tags=[tag])

    @router.post("/ask")
    async def ask_kb(payload: dict):
        """
        Query the knowledge base and get a response.
        
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
            "kb_id": "knowledge base id",
            "kb_name": "display name"
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

            logger.info(f"Query received for kb_id={kb.kb_id}, session_id={session_id}, query_length={len(user_query)}")
            
            # Detect special query types
            import re
            query_lower = user_query.lower().strip()
            is_greeting = bool(re.match(r'^(hi|hello|hey|yo|greetings|good\s+(morning|afternoon|evening))[!.,\s]*$', query_lower))
            is_thanks = bool(re.search(r'\b(thank|thanks|thank\s+you|appreciate|grateful)\b', query_lower))
            is_help_request = bool(re.search(r'\b(help|assist|support|please)\b', query_lower))
            is_satisfaction_no = bool(re.search(r'\b(no|not|unsatisfied|dissatisfied|not\s+helpful|didn\'?t\s+help|not\s+what\s+i\s+needed)\b', query_lower))
            
            # Handle greetings with helpful information
            if is_greeting:
                greeting_response = f"""Hello! I'm here to help you with information about {kb.display_name}. 

I can assist you with:
• Enrollment procedures and requirements
• Policy information and guidelines
• Operational procedures
• Benefits and coverage details
• Any other questions about the {kb.display_name} scheme

Feel free to ask me anything, and I'll do my best to provide you with accurate and helpful information!"""
                return {
                    "answer": greeting_response,
                    "session_id": session_id,
                    "kb_id": kb.kb_id,
                    "kb_name": kb.display_name,
                }
            
            # Handle satisfaction "no" responses
            if is_satisfaction_no:
                return {
                    "answer": "I'm sorry to hear that. I'd really like to help you better. Could you please tell me:\n\n• What information were you looking for?\n• What part of my response wasn't helpful?\n• How can I assist you more effectively?\n\nI'm here to make sure you get the information you need!",
                    "session_id": session_id,
                    "kb_id": kb.kb_id,
                    "kb_name": kb.display_name,
                }

            # Retrieve KB context - use more chunks for better retrieval quality
            # Use 5-7 chunks but manage payload intelligently
            optimal_top_k = min(max(top_k, 5), 7)  # Use 5-7 chunks for better coverage
            rag_context = await state_kb_service.retrieve_async(
                kb_id=kb.kb_id, 
                query=user_query, 
                k=optimal_top_k, 
                use_cache=True
            )
            
            if not rag_context:
                # Handle thank you messages when no context is retrieved
                if is_thanks:
                    return {
                        "answer": f"You're very welcome! I'm glad I could help. If you have any other questions about {kb.display_name}, feel free to ask. I'm here to assist you anytime!",
                        "session_id": session_id,
                        "kb_id": kb.kb_id,
                        "kb_name": kb.display_name,
                    }
                logger.warning(f"No context retrieved for kb_id={kb.kb_id}, query='{user_query[:50]}...'")
                return {
                    "answer": f"I couldn't find specific information about this in the {kb.display_name} knowledge base. Please contact the Agency directly for more information, and I'm here to help with any other questions you might have!",
                    "session_id": session_id,
                    "kb_id": kb.kb_id,
                    "kb_name": kb.display_name,
                }

            # Smart truncation: Keep most relevant parts, remove less relevant
            # Prioritize keeping complete sentences and paragraphs
            if len(rag_context) > 8000:
                logger.info(f"RAG context large ({len(rag_context)} chars), intelligently truncating")
                # Find sentence boundaries for clean truncation
                def find_sentence_end(text: str, max_pos: int) -> int:
                    """Find the last sentence end before max_pos"""
                    # Look for sentence endings (. ! ?) followed by space or newline
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

            # Conversation context - use more history for better context
            conversation_history = conversation_manager.get_messages(
                session_id=session_id, 
                max_messages=4  # Increased to 4 for better context
            )
            llm_context = conversation_manager.get_context_for_llm(
                session_id=session_id,
                kb_id=kb.kb_id,
                rag_context=rag_context,
                current_query=user_query,
            )

            # Smart truncation: Keep essential parts, truncate intelligently
            if llm_context and len(llm_context) > 12000:
                logger.warning(f"LLM context large ({len(llm_context)} chars), intelligently truncating")
                # Keep the anti-hallucination instructions and first 8000 chars of context
                if "CRITICAL INSTRUCTIONS" in llm_context:
                    parts = llm_context.split("===")
                    instructions = parts[0] if parts else ""
                    context_part = "===".join(parts[1:]) if len(parts) > 1 else llm_context
                    # Keep instructions + first 8000 of context
                    llm_context = instructions + context_part[:8000] + "... [truncated for API limits]"
                else:
                    llm_context = llm_context[:10000] + "... [truncated for API limits]"

            conversation_manager.add_message(
                session_id=session_id, 
                role="user", 
                content=user_query, 
                kb_id=kb.kb_id
            )

            # Generate response using LLM
            ollama_client = await get_ollama_client()
            
            # Prepare messages - keep more context for better responses
            messages_to_send = conversation_history + [{"role": "user", "content": user_query}]
            
            # Truncate individual messages if needed, but less aggressively
            for msg in messages_to_send:
                content = msg.get("content", "")
                if len(content) > 2000:  # Allow longer messages for better context
                    # Try to truncate at sentence boundary
                    truncated = content[:2000]
                    last_period = truncated.rfind('.')
                    if last_period > 1500:  # If we can find a sentence end
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
                    kb_id=kb.kb_id,
                )
            except Exception as e:
                error_msg = str(e)
                logger.error(f"LLM API error for kb_id={kb.kb_id}: {error_msg}")
                
                # If it's a payload size error, try with minimal context
                if "400" in error_msg or "413" in error_msg or "payload" in error_msg.lower() or "Bad Request" in error_msg:
                    logger.info("Retrying with minimal context...")
                    # Reduce context to minimal
                    if llm_context:
                        # Keep only the most essential part
                        llm_context = rag_context[:2000] + "... [minimal context]" if rag_context else None
                    # Use only current query, no history
                    messages_to_send = [{"role": "user", "content": user_query}]
                    
                    try:
                        answer = await ollama_client.chat(
                            messages=messages_to_send,
                            context=llm_context,
                            kb_id=kb.kb_id,
                        )
                        logger.info("Retry successful with minimal context")
                    except Exception as retry_error:
                        logger.error(f"Retry also failed: {retry_error}")
                        # Last resort - no context at all
                        answer = await ollama_client.chat(
                            messages=[{"role": "user", "content": user_query}],
                            context=None,
                            kb_id=kb.kb_id,
                        )
                else:
                    raise

            conversation_manager.add_message(
                session_id=session_id, 
                role="assistant", 
                content=answer, 
                kb_id=kb.kb_id
            )

            logger.info(f"Response generated for kb_id={kb.kb_id}, session_id={session_id}, answer_length={len(answer)}")

            # Clean up any source markers that might have been generated despite instructions
            import re
            # Remove various source citation patterns
            answer = re.sub(r'【[^】]*source[^】]*】', '', answer, flags=re.IGNORECASE)
            answer = re.sub(r'\[[^\]]*source[^\]]*\]', '', answer, flags=re.IGNORECASE)
            answer = re.sub(r'\([^)]*source[^)]*\)', '', answer, flags=re.IGNORECASE)
            answer = re.sub(r'\([^)]*source:[^)]*\)', '', answer, flags=re.IGNORECASE)
            # Remove attribution phrases (with or without parentheses, with or without period)
            answer = re.sub(r'\([^)]*All points are drawn directly from[^)]*\)\.?', '', answer, flags=re.IGNORECASE)
            answer = re.sub(r'\([^)]*All points are drawn directly from[^)]*\)', '', answer, flags=re.IGNORECASE)
            answer = re.sub(r'All points are drawn directly from[^.]*\.?', '', answer, flags=re.IGNORECASE)
            # Remove variations like "These are... in the knowledge base" or "explicitly outlined in the knowledge base"
            answer = re.sub(r'These are[^.]*explicitly[^.]*knowledge base\.?', '', answer, flags=re.IGNORECASE)
            answer = re.sub(r'These are[^.]*outlined[^.]*knowledge base\.?', '', answer, flags=re.IGNORECASE)
            answer = re.sub(r'[^.]*explicitly[^.]*outlined[^.]*knowledge base\.?', '', answer, flags=re.IGNORECASE)
            answer = re.sub(r'[^.]*explicitly[^.]*described[^.]*knowledge base\.?', '', answer, flags=re.IGNORECASE)
            answer = re.sub(r'\(.*pages?\s*\d+[^)]*\)', '', answer, flags=re.IGNORECASE)
            # Remove any remaining standalone source markers
            answer = re.sub(r'\s*【[^】]*】\s*', ' ', answer)
            answer = re.sub(r'\s*\[[^\]]*\]\s*', ' ', answer)
            
            # Fix responses that start mid-sentence (common issue with chunking/truncation)
            if answer and len(answer) > 10:
                # Check if it starts with a word that looks like mid-sentence
                # Common patterns: starts with lowercase, starts with punctuation, starts with incomplete word
                first_word_end = answer.find(' ')
                if first_word_end > 0 and first_word_end < 50:
                    first_word = answer[:first_word_end].strip('.,;:!?')
                    # If first word is very short or looks incomplete, try to find sentence start
                    if len(first_word) < 3 or answer[0].islower():
                        # Look for sentence boundaries (period, exclamation, question mark)
                        sentence_endings = ['.', '!', '?']
                        for i, char in enumerate(answer[:300]):
                            if char in sentence_endings and (i + 1 >= len(answer) or answer[i + 1] in ' \n\t'):
                                # Found sentence end, start from after it
                                answer = answer[i + 1:].strip()
                                # Capitalize first letter if it's lowercase
                                if answer and answer[0].islower():
                                    answer = answer[0].upper() + answer[1:]
                                break
                    elif answer[0].islower() and answer[0].isalpha():
                        # Starts with lowercase letter - capitalize it
                        answer = answer[0].upper() + answer[1:]
            
            # Clean up multiple spaces and periods
            answer = re.sub(r'\s+', ' ', answer)
            answer = re.sub(r'\.\s*\.', '.', answer)
            # Remove trailing attribution phrases that might have been missed
            answer = re.sub(r'\s*\([^)]*drawn directly[^)]*\)\.?\s*$', '', answer, flags=re.IGNORECASE)
            answer = re.sub(r'\s*\([^)]*knowledge base[^)]*\)\.?\s*$', '', answer, flags=re.IGNORECASE)
            # Remove sentences ending with "knowledge base" or similar attribution
            answer = re.sub(r'\s*These are[^.]*knowledge base\.?\s*$', '', answer, flags=re.IGNORECASE)
            answer = re.sub(r'\s*[^.]*explicitly[^.]*knowledge base\.?\s*$', '', answer, flags=re.IGNORECASE)
            answer = re.sub(r'\s*[^.]*outlined[^.]*knowledge base\.?\s*$', '', answer, flags=re.IGNORECASE)
            answer = re.sub(r'\s*[^.]*described[^.]*knowledge base\.?\s*$', '', answer, flags=re.IGNORECASE)
            answer = answer.strip()
            
            # Add polite closing phrase with satisfaction check (unless it's already a thank you or greeting response)
            # Don't add if the answer already ends with a question or satisfaction check
            if not is_thanks and not is_greeting and not is_satisfaction_no:
                # Check if answer already has a satisfaction check
                has_satisfaction_check = bool(re.search(r'(hope|satisfied|helpful|anything else|other questions)', answer[-100:].lower()))
                
                if not has_satisfaction_check:
                    # Add polite closing with satisfaction check
                    closing_phrase = "\n\nI hope this information is helpful! If you have any other questions or need further clarification, please feel free to ask. I'm here to assist you!"
                    answer = answer + closing_phrase
            
            # If it's a thank you message with context, add a friendly closing
            elif is_thanks:
                # Check if answer doesn't already have a closing
                if not re.search(r'(welcome|glad|happy|assist)', answer[-50:].lower()):
                    answer = answer + "\n\nYou're very welcome! If you have any other questions, I'm here to help!"

            return {
                "answer": answer, 
                "session_id": session_id, 
                "kb_id": kb.kb_id, 
                "kb_name": kb.display_name
            }
        except Exception as e:
            logger.error(f"Error in ask_kb for kb_id={kb.kb_id}: {e}", exc_info=True)
            return JSONResponse(
                {"error": str(e), "session_id": payload.get("session_id", "unknown")}, 
                status_code=500
            )

    @router.post("/stream")
    async def stream_kb(payload: dict):
        """
        Streaming endpoint (compatibility layer).
        
        Currently returns JSON (non-streaming). Can be enhanced to support
        Server-Sent Events (SSE) for true token streaming in the future.
        
        Request body: Same as /ask
        Returns: Same as /ask
        """
        # For now, delegate to ask_kb
        # In the future, this can be enhanced to support SSE streaming
        return await ask_kb(payload)

    @router.get("/health")
    async def health_check():
        """
        Health check endpoint for the knowledge base.
        
        Returns:
        {
            "status": "healthy" | "unhealthy",
            "kb_id": "knowledge base id",
            "kb_name": "display name",
            "collection_count": number of documents,
            "cache_stats": cache statistics
        }
        """
        try:
            collection = get_or_create_collection(kb.kb_id)
            collection_count = collection.count()
            
            cache_stats = state_kb_service.get_cache_stats()
            
            status = "healthy" if collection_count > 0 else "unhealthy"
            
            return {
                "status": status,
                "kb_id": kb.kb_id,
                "kb_name": kb.display_name,
                "collection_count": collection_count,
                "cache_stats": cache_stats,
            }
        except Exception as e:
            logger.error(f"Error in health_check for kb_id={kb.kb_id}: {e}", exc_info=True)
            return JSONResponse(
                {
                    "status": "unhealthy",
                    "kb_id": kb.kb_id,
                    "kb_name": kb.display_name,
                    "error": str(e)
                },
                status_code=500
            )

    return router


