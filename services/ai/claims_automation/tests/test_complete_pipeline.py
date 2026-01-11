"""
Complete Pipeline Integration Tests
End-to-end testing of the entire DCAL system
"""

import pytest
import asyncio
from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.models import ClaimData, ProcedureCode, DiagnosisCode, ClaimType
from src.orchestrator import orchestrator
from src.rule_engine.engine import rule_engine
from src.ml_engine.engine import ml_engine
from src.decision_engine.synthesis import decision_engine
from src.audit.audit_logger import audit_logger


@pytest.mark.asyncio
async def test_full_pipeline_valid_claim():
    """Test complete pipeline with valid claim"""
    
    await orchestrator.initialize()
    
    claim = ClaimData(
        claim_id="E2E-VALID-001",
        policy_id="POL-123",
        provider_id="PRV-456",
        member_id_hash="member_abc123",
        procedure_codes=[
            ProcedureCode(code="99213", code_type="CPT", quantity=1, line_amount=150.0)
        ],
        diagnosis_codes=[
            DiagnosisCode(code="J06.9", code_type="ICD10_CM", sequence=1)
        ],
        billed_amount=150.0,
        service_date=date(2026, 1, 5)
    )
    
    report = await orchestrator.process_claim(claim)
    
    assert report is not None
    assert report.claim_id == "E2E-VALID-001"
    assert report.recommendation is not None
    assert report.confidence_score > 0
    assert len(report.primary_reasons) > 0
    assert report.sla_hours > 0


@pytest.mark.asyncio
async def test_full_pipeline_invalid_claim():
    """Test pipeline with invalid claim (should fail rules)"""
    
    await orchestrator.initialize()
    
    # Create invalid claim (negative amount, future date)
    claim = ClaimData(
        claim_id="E2E-INVALID-001",
        policy_id="POL-123",
        provider_id="PRV-456",
        member_id_hash="member_xyz789",
        procedure_codes=[],  # No procedures
        diagnosis_codes=[],  # No diagnoses
        billed_amount=-100.0,  # Negative!
        service_date=date(2027, 1, 1)  # Future date!
    )
    
    report = await orchestrator.process_claim(claim)
    
    assert report is not None
    assert report.risk_score > 0.8, "Should be high risk"
    assert "CRITICAL" in str(report.primary_reasons)


@pytest.mark.asyncio
async def test_high_value_claim_routing():
    """Test that high-value claims route to senior review"""
    
    await orchestrator.initialize()
    
    claim = ClaimData(
        claim_id="E2E-HIGHVALUE-001",
        policy_id="POL-123",
        provider_id="PRV-456",
        member_id_hash="member_high_value",
        procedure_codes=[
            ProcedureCode(code="99285", code_type="CPT", quantity=1, line_amount=5000000.0)
        ],
        diagnosis_codes=[
            DiagnosisCode(code="I21.9", code_type="ICD10_CM", sequence=1)
        ],
        billed_amount=5000000.0,  # 5 million NGN
        service_date=date(2026, 1, 5)
    )
    
    report = await orchestrator.process_claim(claim)
    
    assert report.assigned_queue.value in ["SENIOR_REVIEW", "FRAUD_INVESTIGATION"]
    assert report.priority.value in ["HIGH", "CRITICAL"]


@pytest.mark.asyncio
async def test_rules_ml_decision_integration():
    """Test that rules, ML, and decision engines work together"""
    
    await rule_engine.initialize()
    await ml_engine.initialize()
    
    claim = ClaimData(
        claim_id="E2E-INTEGRATION-001",
        policy_id="POL-123",
        provider_id="PRV-100",
        member_id_hash="member_integration",
        procedure_codes=[
            ProcedureCode(code="99213", code_type="CPT", quantity=1, line_amount=150.0)
        ],
        diagnosis_codes=[
            DiagnosisCode(code="J06.9", code_type="ICD10_CM", sequence=1)
        ],
        billed_amount=150.0,
        service_date=date(2026, 1, 5)
    )
    
    # Step 1: Rules
    rule_result = await rule_engine.evaluate_claim(claim)
    assert rule_result.aggregate_outcome is not None
    
    # Step 2: ML
    ml_result = await ml_engine.analyze_claim(claim)
    assert ml_result.combined_risk_score is not None
    
    # Step 3: Decision
    intelligence_report = await decision_engine.synthesize_decision(
        claim, rule_result, ml_result
    )
    assert intelligence_report.recommendation is not None
    assert intelligence_report.confidence_score > 0


@pytest.mark.asyncio
async def test_audit_trail_completeness():
    """Test that all processing steps are audited"""
    
    if not audit_logger._initialized:
        pytest.skip("Audit logger not initialized (PostgreSQL required)")
    
    await orchestrator.initialize()
    
    claim = ClaimData(
        claim_id="E2E-AUDIT-001",
        policy_id="POL-123",
        provider_id="PRV-456",
        member_id_hash="member_audit",
        procedure_codes=[
            ProcedureCode(code="99213", code_type="CPT", quantity=1, line_amount=150.0)
        ],
        diagnosis_codes=[
            DiagnosisCode(code="J06.9", code_type="ICD10_CM", sequence=1)
        ],
        billed_amount=150.0,
        service_date=date(2026, 1, 5)
    )
    
    # Process claim
    report = await orchestrator.process_claim(claim)
    
    # Query audit events
    events = await audit_logger.get_events(
        resource_type="claim",
        resource_id="E2E-AUDIT-001",
        limit=100
    )
    
    assert len(events) >= 2, "Should have at least rule evaluation and decision events"
    
    event_types = [e["event_type"] for e in events]
    assert "rule_evaluation" in event_types or "decision_synthesized" in event_types


@pytest.mark.asyncio
async def test_ml_degradation_mode():
    """Test system works even if ML engine fails"""
    
    await orchestrator.initialize()
    
    # Temporarily disable ML
    original_ml_setting = orchestrator.settings.ENABLE_ML_ENGINE if hasattr(orchestrator, 'settings') else True
    
    from src.core import config
    config.settings.ENABLE_ML_ENGINE = False
    
    claim = ClaimData(
        claim_id="E2E-NO-ML-001",
        policy_id="POL-123",
        provider_id="PRV-456",
        member_id_hash="member_no_ml",
        procedure_codes=[
            ProcedureCode(code="99213", code_type="CPT", quantity=1, line_amount=150.0)
        ],
        diagnosis_codes=[
            DiagnosisCode(code="J06.9", code_type="ICD10_CM", sequence=1)
        ],
        billed_amount=150.0,
        service_date=date(2026, 1, 5)
    )
    
    report = await orchestrator.process_claim(claim)
    
    assert report is not None, "System should work without ML"
    assert report.recommendation is not None
    
    # Restore setting
    config.settings.ENABLE_ML_ENGINE = original_ml_setting


@pytest.mark.asyncio
async def test_concurrent_claim_processing():
    """Test processing multiple claims concurrently"""
    
    await orchestrator.initialize()
    
    claims = []
    for i in range(10):
        claim = ClaimData(
            claim_id=f"E2E-CONCURRENT-{i:03d}",
            policy_id="POL-123",
            provider_id="PRV-456",
            member_id_hash=f"member_concurrent_{i}",
            procedure_codes=[
                ProcedureCode(code="99213", code_type="CPT", quantity=1, line_amount=150.0)
            ],
            diagnosis_codes=[
                DiagnosisCode(code="J06.9", code_type="ICD10_CM", sequence=1)
            ],
            billed_amount=150.0 * (i + 1),
            service_date=date(2026, 1, 5)
        )
        claims.append(claim)
    
    # Process all claims concurrently
    tasks = [orchestrator.process_claim(claim) for claim in claims]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # All should succeed
    successful = [r for r in results if not isinstance(r, Exception)]
    assert len(successful) == 10, "All claims should process successfully"


@pytest.mark.asyncio
async def test_performance_benchmark():
    """Benchmark claim processing performance"""
    
    await orchestrator.initialize()
    
    import time
    
    claim = ClaimData(
        claim_id="E2E-PERF-001",
        policy_id="POL-123",
        provider_id="PRV-456",
        member_id_hash="member_perf",
        procedure_codes=[
            ProcedureCode(code="99213", code_type="CPT", quantity=1, line_amount=150.0)
        ],
        diagnosis_codes=[
            DiagnosisCode(code="J06.9", code_type="ICD10_CM", sequence=1)
        ],
        billed_amount=150.0,
        service_date=date(2026, 1, 5)
    )
    
    start = time.perf_counter()
    report = await orchestrator.process_claim(claim)
    elapsed = (time.perf_counter() - start) * 1000
    
    print(f"\n⏱️  Processing time: {elapsed:.2f}ms")
    
    assert elapsed < 5000, "Should process in under 5 seconds"
    assert report is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])


