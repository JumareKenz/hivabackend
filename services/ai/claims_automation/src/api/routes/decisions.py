"""
Decision Management API Routes
Submit and track claim decisions
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from ..auth import User, get_current_user, Roles
from ...audit.audit_logger import audit_logger

router = APIRouter()


class DecisionRequest(BaseModel):
    """Request to submit a decision"""
    claim_id: str
    analysis_id: str
    decision: str  # APPROVED, DECLINED, REQUEST_MORE_INFO
    decision_reason: str
    override_ai_recommendation: bool = False
    notes: Optional[str] = None
    adjusted_amount: Optional[float] = None


class DecisionResponse(BaseModel):
    """Response after submitting decision"""
    decision_id: str
    claim_id: str
    status: str
    message: str
    timestamp: datetime


@router.post("/submit", response_model=DecisionResponse)
async def submit_decision(
    decision: DecisionRequest,
    user: User = Depends(get_current_user)
):
    """
    Submit a claim decision.
    
    Requires: reviewer or higher
    
    CRITICAL: All decisions are immutably logged to audit trail
    """
    if not any(role in user.roles for role in [Roles.REVIEWER, Roles.SENIOR_REVIEWER, Roles.ADMIN]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to submit decisions"
        )
    
    try:
        # Log decision to immutable audit trail
        decision_id = await audit_logger.log_event(
            event_type="claim_decision_submitted",
            event_category="decision_management",
            actor_type="human",
            actor_id=user.user_id,
            actor_role=user.roles[0] if user.roles else "unknown",
            action="submit_decision",
            resource_type="claim",
            resource_id=decision.claim_id,
            request_id=decision.analysis_id,
            new_state={
                "decision": decision.decision,
                "decision_reason": decision.decision_reason,
                "override_ai": decision.override_ai_recommendation,
                "adjusted_amount": decision.adjusted_amount,
                "notes": decision.notes
            },
            change_summary=f"Decision: {decision.decision} by {user.username}",
            authorization_decision="ALLOW"
        )
        
        # In production, also update claim status in database
        # ...
        
        return DecisionResponse(
            decision_id=decision_id,
            claim_id=decision.claim_id,
            status="SUBMITTED",
            message=f"Decision {decision.decision} recorded successfully",
            timestamp=datetime.utcnow()
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit decision: {str(e)}"
        )


@router.get("/{claim_id}/history")
async def get_decision_history(
    claim_id: str,
    user: User = Depends(get_current_user)
):
    """
    Get decision history for a claim.
    
    Requires: Any authenticated user
    """
    try:
        # Query audit log
        events = await audit_logger.get_events(
            resource_type="claim",
            resource_id=claim_id,
            limit=100
        )
        
        return {
            "claim_id": claim_id,
            "total_decisions": len(events),
            "events": events
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve decision history: {str(e)}"
        )


@router.post("/{claim_id}/assign")
async def assign_claim(
    claim_id: str,
    assignee_id: str,
    user: User = Depends(get_current_user)
):
    """
    Assign claim to a reviewer.
    
    Requires: senior_reviewer or admin
    """
    if not any(role in user.roles for role in [Roles.SENIOR_REVIEWER, Roles.ADMIN]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to assign claims"
        )
    
    try:
        # Log assignment
        await audit_logger.log_event(
            event_type="claim_assigned",
            event_category="queue_management",
            actor_type="human",
            actor_id=user.user_id,
            action="assign_claim",
            resource_type="claim",
            resource_id=claim_id,
            request_id=f"assign-{claim_id}",
            new_state={"assignee_id": assignee_id},
            change_summary=f"Claim assigned to {assignee_id}"
        )
        
        return {
            "status": "success",
            "message": f"Claim {claim_id} assigned to {assignee_id}"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to assign claim: {str(e)}"
        )


