"""
Queue Management API Routes
View and manage review queues
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from ..auth import User, get_current_user, Roles

router = APIRouter()


class QueueItem(BaseModel):
    """Claim in review queue"""
    claim_id: str
    analysis_id: str
    priority: str
    assigned_queue: str
    recommendation: str
    risk_score: float
    confidence_score: float
    sla_deadline: datetime
    sla_remaining_hours: float
    created_at: datetime


class QueueSummary(BaseModel):
    """Queue statistics"""
    queue_name: str
    total_claims: int
    overdue_claims: int
    high_priority: int
    medium_priority: int
    low_priority: int
    avg_risk_score: float


@router.get("/summary", response_model=List[QueueSummary])
async def get_queues_summary(user: User = Depends(get_current_user)):
    """
    Get summary of all review queues.
    
    Requires: Any authenticated user
    """
    # In production, this would query from database
    # Mock data for demonstration
    return [
        QueueSummary(
            queue_name="STANDARD_REVIEW",
            total_claims=45,
            overdue_claims=3,
            high_priority=5,
            medium_priority=30,
            low_priority=10,
            avg_risk_score=0.35
        ),
        QueueSummary(
            queue_name="SENIOR_REVIEW",
            total_claims=12,
            overdue_claims=1,
            high_priority=8,
            medium_priority=4,
            low_priority=0,
            avg_risk_score=0.65
        ),
        QueueSummary(
            queue_name="FRAUD_INVESTIGATION",
            total_claims=8,
            overdue_claims=0,
            high_priority=8,
            medium_priority=0,
            low_priority=0,
            avg_risk_score=0.82
        )
    ]


@router.get("/{queue_name}/claims", response_model=List[QueueItem])
async def get_queue_claims(
    queue_name: str,
    user: User = Depends(get_current_user),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0)
):
    """
    Get claims in a specific queue.
    
    Requires: reviewer or higher
    """
    if not any(role in user.roles for role in [Roles.REVIEWER, Roles.SENIOR_REVIEWER, Roles.ADMIN]):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # In production, query from database
    # Mock empty list for now
    return []


@router.get("/my-assignments", response_model=List[QueueItem])
async def get_my_assignments(user: User = Depends(get_current_user)):
    """
    Get claims assigned to current user.
    
    Requires: reviewer or higher
    """
    if not any(role in user.roles for role in [Roles.REVIEWER, Roles.SENIOR_REVIEWER, Roles.ADMIN]):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # In production, query from database
    return []


