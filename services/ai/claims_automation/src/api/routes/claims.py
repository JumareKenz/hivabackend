"""
Claims API Routes
View and process individual claims
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, date

from ...core.models import ClaimData, ProcedureCode, DiagnosisCode, ClaimType
from ...orchestrator import orchestrator
from ..auth import User, get_current_user, Roles, require_role

router = APIRouter()


class ClaimRequest(BaseModel):
    """Request to process a claim"""
    claim_id: str
    policy_id: str
    provider_id: str
    member_id_hash: str
    procedure_codes: List[dict]
    diagnosis_codes: List[dict]
    billed_amount: float
    service_date: date
    claim_type: str = "PROFESSIONAL"


class ClaimIntelligenceResponse(BaseModel):
    """Response with claim intelligence report"""
    analysis_id: str
    claim_id: str
    timestamp: datetime
    recommendation: str
    confidence_score: float
    risk_score: float
    assigned_queue: Optional[str]
    priority: str
    sla_hours: int
    primary_reasons: List[str]
    secondary_factors: List[str]
    suggested_actions: List[str]
    rule_engine_details: dict
    ml_engine_details: dict


@router.post("/process", response_model=ClaimIntelligenceResponse)
async def process_claim(
    claim_request: ClaimRequest,
    user: User = Depends(get_current_user)
):
    """
    Process a claim through the DCAL pipeline.
    
    Requires: reviewer, senior_reviewer, or admin role
    """
    if not any(role in user.roles for role in [Roles.REVIEWER, Roles.SENIOR_REVIEWER, Roles.ADMIN]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to process claims"
        )
    
    try:
        # Build ClaimData
        claim = ClaimData(
            claim_id=claim_request.claim_id,
            policy_id=claim_request.policy_id,
            provider_id=claim_request.provider_id,
            member_id_hash=claim_request.member_id_hash,
            procedure_codes=[
                ProcedureCode(**proc) for proc in claim_request.procedure_codes
            ],
            diagnosis_codes=[
                DiagnosisCode(**diag) for diag in claim_request.diagnosis_codes
            ],
            billed_amount=claim_request.billed_amount,
            service_date=claim_request.service_date,
            claim_type=ClaimType(claim_request.claim_type)
        )
        
        # Process through orchestrator
        report = await orchestrator.process_claim(claim)
        
        # Convert to response
        return ClaimIntelligenceResponse(
            analysis_id=report.analysis_id,
            claim_id=report.claim_id,
            timestamp=report.timestamp,
            recommendation=report.recommendation.value,
            confidence_score=report.confidence_score,
            risk_score=report.risk_score,
            assigned_queue=report.assigned_queue.value if report.assigned_queue else None,
            priority=report.priority.value,
            sla_hours=report.sla_hours,
            primary_reasons=report.primary_reasons,
            secondary_factors=report.secondary_factors,
            suggested_actions=report.suggested_actions,
            rule_engine_details=report.rule_engine_details,
            ml_engine_details=report.ml_engine_details
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process claim: {str(e)}"
        )


@router.get("/{claim_id}/intelligence", response_model=ClaimIntelligenceResponse)
async def get_claim_intelligence(
    claim_id: str,
    user: User = Depends(get_current_user)
):
    """
    Get intelligence report for a previously processed claim.
    
    Requires: Any authenticated user
    """
    # In production, this would query from a database
    # For now, return 404
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Intelligence report for claim {claim_id} not found"
    )


@router.get("/{claim_id}")
async def get_claim_details(
    claim_id: str,
    user: User = Depends(get_current_user)
):
    """
    Get detailed claim information from HIP database.
    
    Requires: Any authenticated user
    """
    from ...data.hip_service import hip_service
    
    try:
        claim = await hip_service.get_claim_by_id(claim_id)
        if not claim:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Claim {claim_id} not found"
            )
        
        return {
            "claim_id": claim.claim_id,
            "billed_amount": claim.billed_amount,
            "service_date": claim.service_date,
            "provider_id": claim.provider_id,
            "member_id_hash": claim.member_id_hash,
            "procedure_count": len(claim.procedure_codes),
            "diagnosis_count": len(claim.diagnosis_codes),
            "network_status": claim.network_status.value
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve claim: {str(e)}"
        )


