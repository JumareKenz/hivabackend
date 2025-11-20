"""
Branch management endpoints for configuring branch-specific contexts
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any
from app.services.conversation_manager import conversation_manager

router = APIRouter()


@router.post("/branches/{branch_id}/context")
async def set_branch_context(branch_id: str, context: Dict[str, Any]):
    """
    Set branch-specific context (modes of operation, policies, etc.)
    
    Example:
    {
        "name": "Lagos Branch",
        "modes": ["standard", "premium"],
        "policies": ["policy1", "policy2"],
        "contact": "+2349012345678",
        "specializations": ["auto", "health"]
    }
    """
    try:
        conversation_manager.set_branch_context(branch_id, context)
        return {
            "status": "success",
            "branch_id": branch_id,
            "message": "Branch context updated"
        }
    except Exception as e:
        return JSONResponse(
            {"error": str(e)},
            status_code=500
        )


@router.get("/branches/{branch_id}/context")
async def get_branch_context(branch_id: str):
    """Get branch-specific context"""
    context = conversation_manager.get_branch_context(branch_id)
    if not context:
        raise HTTPException(
            status_code=404,
            detail=f"Branch {branch_id} not found"
        )
    return {
        "branch_id": branch_id,
        "context": context
    }


@router.get("/branches")
async def list_branches():
    """List all configured branches"""
    # This would need to be stored in a way that allows listing
    # For now, return a placeholder
    return {
        "branches": [],
        "message": "Use POST /branches/{branch_id}/context to configure branches"
    }

