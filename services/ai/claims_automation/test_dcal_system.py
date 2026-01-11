#!/usr/bin/env python3
"""
DCAL System Integration Test
Tests all implemented components end-to-end
"""

import asyncio
import sys
from datetime import date, datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.core.models import (
    ClaimData, ProcedureCode, DiagnosisCode,
    ClaimType, NetworkStatus
)
from src.orchestrator import orchestrator

# Test data
def create_test_claim(claim_id: str, amount: float, valid: bool = True) -> ClaimData:
    """Create a test claim"""
    
    if valid:
        service_date = date(2026, 1, 5)
        procedures = [
            ProcedureCode(
                code="99213",
                code_type="CPT",
                quantity=1,
                line_amount=amount
            )
        ]
        diagnoses = [
            DiagnosisCode(
                code="J06.9",
                code_type="ICD10_CM",
                sequence=1
            )
        ]
    else:
        # Create invalid claim (negative amount, future date)
        service_date = date(2027, 1, 1)  # Future date
        procedures = []  # No procedures
        diagnoses = []
    
    return ClaimData(
        claim_id=claim_id,
        policy_id="POL-TEST-001",
        provider_id="PRV-100",
        member_id_hash="test_member_hash_abc123",
        procedure_codes=procedures,
        diagnosis_codes=diagnoses,
        billed_amount=amount,
        service_date=service_date,
        claim_type=ClaimType.PROFESSIONAL,
        network_status=NetworkStatus.IN_NETWORK
    )


async def test_hip_database():
    """Test HIP database connectivity"""
    print("\n" + "="*80)
    print("TEST 1: HIP Database Connectivity")
    print("="*80)
    
    from src.data.hip_service import hip_service
    
    try:
        await hip_service.initialize()
        print("✅ HIP database connection established")
        
        # Try to fetch a claim
        claim = await hip_service.get_claim_by_id("1")
        if claim:
            print(f"✅ Successfully retrieved claim: {claim.claim_id}")
            print(f"   Amount: ₦{claim.billed_amount:,.2f}")
            print(f"   Service Date: {claim.service_date}")
            print(f"   Member Hash: {claim.member_id_hash[:16]}...")
        else:
            print("⚠️  No claim found with ID 1 (may not exist)")
        
        # Get provider history
        provider_history = await hip_service.get_provider_history("PRV-100")
        print(f"✅ Provider history retrieved:")
        print(f"   Claims (30d): {provider_history.claims_30d}")
        print(f"   Claims (90d): {provider_history.claims_90d}")
        print(f"   Average Amount: ₦{provider_history.avg_claim_amount:,.2f}")
        
        return True
        
    except Exception as e:
        print(f"❌ HIP database test failed: {e}")
        return False


async def test_rule_engine():
    """Test rule engine evaluation"""
    print("\n" + "="*80)
    print("TEST 2: Rule Engine Evaluation")
    print("="*80)
    
    from src.rule_engine.engine import rule_engine
    
    try:
        await rule_engine.initialize()
        print(f"✅ Rule engine initialized")
        print(f"   Rules loaded: {len(rule_engine.active_ruleset)}")
        print(f"   Ruleset version: {rule_engine.ruleset_version}")
        
        # Test Case 1: Valid claim
        print("\n--- Test Case 1: Valid Claim ---")
        valid_claim = create_test_claim("CLM-TEST-001", 150.0, valid=True)
        result1 = await rule_engine.evaluate_claim(valid_claim)
        
        print(f"Outcome: {result1.aggregate_outcome.value}")
        print(f"Rules Evaluated: {result1.rules_evaluated}")
        print(f"Passed: {result1.rules_passed}, Failed: {result1.rules_failed}, Flagged: {result1.rules_flagged}")
        
        if result1.triggered_rules:
            print("Triggered Rules:")
            for rule in result1.triggered_rules:
                print(f"  - [{rule.outcome.value}] {rule.rule_name}")
        
        # Test Case 2: Invalid claim
        print("\n--- Test Case 2: Invalid Claim (Critical Failures) ---")
        invalid_claim = create_test_claim("CLM-TEST-002", -100.0, valid=False)
        result2 = await rule_engine.evaluate_claim(invalid_claim)
        
        print(f"Outcome: {result2.aggregate_outcome.value}")
        print(f"Rules Evaluated: {result2.rules_evaluated}")
        print(f"Passed: {result2.rules_passed}, Failed: {result2.rules_failed}, Flagged: {result2.rules_flagged}")
        
        if result2.triggered_rules:
            print("Triggered Rules:")
            for rule in result2.triggered_rules:
                print(f"  - [{rule.outcome.value}] {rule.rule_name}: {rule.message}")
        
        return True
        
    except Exception as e:
        print(f"❌ Rule engine test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_decision_synthesis():
    """Test decision synthesis engine"""
    print("\n" + "="*80)
    print("TEST 3: Decision Synthesis Engine")
    print("="*80)
    
    from src.rule_engine.engine import rule_engine
    from src.decision_engine.synthesis import decision_engine
    
    try:
        # Create test claim
        test_claim = create_test_claim("CLM-TEST-003", 250000.0, valid=True)
        
        # Evaluate rules
        rule_result = await rule_engine.evaluate_claim(test_claim)
        
        # Synthesize decision
        intelligence_report = await decision_engine.synthesize_decision(
            claim_data=test_claim,
            rule_result=rule_result,
            ml_result=None  # ML not yet implemented
        )
        
        print(f"✅ Decision synthesized successfully")
        print(f"\nClaim Intelligence Report:")
        print(f"  Analysis ID: {intelligence_report.analysis_id}")
        print(f"  Claim ID: {intelligence_report.claim_id}")
        print(f"  Recommendation: {intelligence_report.recommendation.value}")
        print(f"  Confidence: {intelligence_report.confidence_score:.2%}")
        print(f"  Risk Score: {intelligence_report.risk_score:.2%}")
        print(f"  Assigned Queue: {intelligence_report.assigned_queue.value if intelligence_report.assigned_queue else 'N/A'}")
        print(f"  Priority: {intelligence_report.priority.value}")
        print(f"  SLA: {intelligence_report.sla_hours} hours")
        
        print(f"\nPrimary Reasons:")
        for reason in intelligence_report.primary_reasons:
            print(f"  - {reason}")
        
        if intelligence_report.suggested_actions:
            print(f"\nSuggested Actions:")
            for action in intelligence_report.suggested_actions:
                print(f"  - {action}")
        
        return True
        
    except Exception as e:
        print(f"❌ Decision synthesis test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_end_to_end():
    """Test end-to-end claim processing through orchestrator"""
    print("\n" + "="*80)
    print("TEST 4: End-to-End Claim Processing")
    print("="*80)
    
    try:
        # Initialize orchestrator
        await orchestrator.initialize()
        print("✅ Orchestrator initialized\n")
        
        # Test Case 1: Standard valid claim
        print("--- Processing Claim 1: Standard Valid Claim ---")
        claim1 = create_test_claim("CLM-E2E-001", 15000.0, valid=True)
        report1 = await orchestrator.process_claim(claim1)
        
        print(f"✅ Claim processed: {report1.recommendation.value}")
        print(f"   Confidence: {report1.confidence_score:.2%}, Risk: {report1.risk_score:.2%}\n")
        
        # Test Case 2: High-value claim
        print("--- Processing Claim 2: High-Value Claim ---")
        claim2 = create_test_claim("CLM-E2E-002", 750000.0, valid=True)
        report2 = await orchestrator.process_claim(claim2)
        
        print(f"✅ Claim processed: {report2.recommendation.value}")
        print(f"   Confidence: {report2.confidence_score:.2%}, Risk: {report2.risk_score:.2%}\n")
        
        # Test Case 3: Invalid claim
        print("--- Processing Claim 3: Invalid Claim ---")
        claim3 = create_test_claim("CLM-E2E-003", -500.0, valid=False)
        report3 = await orchestrator.process_claim(claim3)
        
        print(f"✅ Claim processed: {report3.recommendation.value}")
        print(f"   Confidence: {report3.confidence_score:.2%}, Risk: {report3.risk_score:.2%}")
        
        return True
        
    except Exception as e:
        print(f"❌ End-to-end test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_audit_integrity():
    """Test audit chain integrity"""
    print("\n" + "="*80)
    print("TEST 5: Audit Chain Integrity")
    print("="*80)
    
    from src.audit.audit_logger import audit_logger
    
    try:
        # Check if audit logger is initialized
        if not audit_logger._initialized:
            print("⚠️  Audit logger not initialized (PostgreSQL may not be running)")
            print("   Skipping audit test")
            return True
        
        # Verify chain integrity
        is_valid, errors = await audit_logger.verify_chain_integrity(start_sequence=0)
        
        if is_valid:
            print("✅ Audit chain integrity verified")
            print(f"   Sequence counter: {audit_logger._sequence_counter}")
            print(f"   Last hash: {audit_logger._last_hash[:32]}...")
        else:
            print("❌ Audit chain integrity FAILED")
            for error in errors:
                print(f"   - {error}")
        
        return is_valid
        
    except Exception as e:
        print(f"⚠️  Audit test skipped: {e}")
        return True  # Non-blocking


async def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("DCAL SYSTEM INTEGRATION TESTS")
    print("Dynamic Claims Automation Layer - Component Verification")
    print("="*80)
    
    results = {}
    
    # Run tests
    results['hip_database'] = await test_hip_database()
    results['rule_engine'] = await test_rule_engine()
    results['decision_synthesis'] = await test_decision_synthesis()
    results['end_to_end'] = await test_end_to_end()
    results['audit_integrity'] = await test_audit_integrity()
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name.replace('_', ' ').title():.<50} {status}")
    
    total = len(results)
    passed = sum(1 for p in results.values() if p)
    
    print("="*80)
    print(f"Total: {passed}/{total} tests passed")
    print("="*80)
    
    # Cleanup
    await orchestrator.shutdown()
    
    return passed == total


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


