"""
Audit API Routes
Query audit trail and verify integrity
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from ..auth import User, get_current_user, Roles
from ...audit.audit_logger import audit_logger

router = APIRouter()


class AuditEventResponse(BaseModel):
    """Audit event response"""
    event_id: str
    event_type: str
    event_category: str
    timestamp: datetime
    actor_id: str
    actor_type: str
    action: str
    resource_type: str
    resource_id: str
    change_summary: Optional[str]
    sequence_number: int


class IntegrityCheckResponse(BaseModel):
    """Chain integrity check response"""
    is_valid: bool
    total_events_checked: int
    errors: List[str]
    last_sequence: int
    last_hash: str


@router.get("/events", response_model=List[AuditEventResponse])
async def get_audit_events(
    user: User = Depends(get_current_user),
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    actor_id: Optional[str] = None,
    limit: int = Query(100, le=1000)
):
    """
    Query audit events.
    
    Requires: admin or compliance_officer
    """
    if not any(role in user.roles for role in [Roles.ADMIN, Roles.COMPLIANCE_OFFICER]):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    try:
        events = await audit_logger.get_events(
            resource_type=resource_type,
            resource_id=resource_id,
            actor_id=actor_id,
            limit=limit
        )
        
        # Convert to response model
        return [
            AuditEventResponse(
                event_id=e["event_id"],
                event_type=e["event_type"],
                event_category=e["event_category"],
                timestamp=e["timestamp"],
                actor_id=e["actor_id"],
                actor_type=e["actor_type"],
                action=e["action"],
                resource_type=e["resource_type"],
                resource_id=e["resource_id"],
                change_summary=e.get("change_summary"),
                sequence_number=e["sequence_number"]
            )
            for e in events
        ]
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to query audit events: {str(e)}"
        )


@router.post("/verify-integrity", response_model=IntegrityCheckResponse)
async def verify_chain_integrity(
    user: User = Depends(get_current_user),
    start_sequence: int = Query(0, ge=0),
    end_sequence: Optional[int] = None
):
    """
    Verify cryptographic integrity of audit chain.
    
    Requires: admin or compliance_officer
    
    CRITICAL: This endpoint verifies that no audit events have been
    tampered with by checking cryptographic hashes.
    """
    if not any(role in user.roles for role in [Roles.ADMIN, Roles.COMPLIANCE_OFFICER]):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    try:
        is_valid, errors = await audit_logger.verify_chain_integrity(
            start_sequence=start_sequence,
            end_sequence=end_sequence
        )
        
        return IntegrityCheckResponse(
            is_valid=is_valid,
            total_events_checked=audit_logger._sequence_counter - start_sequence if audit_logger._initialized else 0,
            errors=errors,
            last_sequence=audit_logger._sequence_counter if audit_logger._initialized else 0,
            last_hash=audit_logger._last_hash if audit_logger._initialized else ""
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to verify chain integrity: {str(e)}"
        )


@router.get("/stats")
async def get_audit_stats(user: User = Depends(get_current_user)):
    """
    Get audit statistics.
    
    Requires: admin or compliance_officer
    """
    if not any(role in user.roles for role in [Roles.ADMIN, Roles.COMPLIANCE_OFFICER]):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    if not audit_logger._initialized:
        return {
            "status": "not_initialized",
            "total_events": 0
        }
    
    return {
        "status": "operational",
        "total_events": audit_logger._sequence_counter,
        "last_hash": audit_logger._last_hash[:16] + "...",
        "genesis_hash": audit_logger._compute_genesis_hash()[:16] + "..."
    }


