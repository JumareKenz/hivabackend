"""
Streaming endpoint (compat layer).

The repository's `app/main.py` includes `api.v1.stream`, but earlier iterations of this
codebase only shipped a non-streaming `/ask`. To keep the app importable and provide a
useful endpoint, this module exposes `/stream` returning a standard JSON payload.

If you later want true token streaming (SSE), you can replace the response with a
`StreamingResponse` implementation.
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


@router.post("/stream")
async def stream(payload: dict):
    """
    Compatibility endpoint that behaves like `/ask` but is named `/stream`.
    Returns JSON (non-streaming).
    """
    try:
        user_query = (payload.get("query") or "").strip()
        session_id = payload.get("session_id") or str(uuid.uuid4())
        explicit_branch_id = payload.get("branch_id")

        branch_id = BranchDetector.smart_detect(
            query=user_query,
            session_id=session_id,
            explicit_branch_id=explicit_branch_id,
            conversation_manager=conversation_manager,
        )

        if not user_query:
            return JSONResponse({"answer": "Please provide a query.", "session_id": session_id}, status_code=400)

        ollama_client = await get_ollama_client()

        rag_context = await rag_service.retrieve_async(query=user_query, k=5, branch_id=branch_id, use_cache=True)
        if not rag_context:
            return {
                "answer": "I couldn't find specific information about this in our knowledge base. Please contact us at +2349012345678 for more information.",
                "session_id": session_id,
            }

        conversation_history = conversation_manager.get_messages(session_id=session_id, max_messages=8)
        llm_context = conversation_manager.get_context_for_llm(
            session_id=session_id,
            branch_id=branch_id,
            rag_context=rag_context,
        )

        conversation_manager.add_message(session_id=session_id, role="user", content=user_query, branch_id=branch_id)

        answer = await ollama_client.chat(
            messages=conversation_history + [{"role": "user", "content": user_query}],
            context=llm_context,
            branch_id=branch_id,
        )

        conversation_manager.add_message(session_id=session_id, role="assistant", content=answer, branch_id=branch_id)
        return {"answer": answer, "session_id": session_id}
    except Exception as e:
        return JSONResponse({"error": str(e), "session_id": payload.get("session_id", "unknown")}, status_code=500)


