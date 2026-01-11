#!/usr/bin/env python3
"""
Quick Test Script for DCAL ML Models
Tests the ML fraud detection models directly without API authentication
"""

import sys
import os
import asyncio
from datetime import date
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Load environment variables
from dotenv import load_dotenv
env_path = project_root / '.env'
if env_path.exists():
    load_dotenv(env_path)

from src.core.models import ClaimData, ProcedureCode, DiagnosisCode, ClaimType
from src.ml_engine.engine import MLFraudDetectionEngine
from src.orchestrator import orchestrator


async def test_ml_engine_direct():
    """Test ML engine directly"""
    print("="*80)
    print("TEST 1: ML Engine Direct Testing")
    print("="*80)
    print()
    
    try:
        ml_engine = MLFraudDetectionEngine()
        print("🔄 Initializing ML engine...")
        await ml_engine.initialize()
        print("✅ ML engine initialized")
        print()
        
        # Test claim 1: Low-risk claim
        print("📋 Test Claim 1: Low-Risk Scenario")
        print("-" * 80)
        claim1 = ClaimData(
            claim_id="ML-TEST-001",
            policy_id="POL-001",
            provider_id="PROV-001",
            member_id_hash="member_hash_001",
            procedure_codes=[
                ProcedureCode(code="99213", code_type="CPT", quantity=1, line_amount=150.0)
            ],
            diagnosis_codes=[
                DiagnosisCode(code="J06.9", code_type="ICD10_CM", sequence=1)
            ],
            billed_amount=150.0,
            service_date=date(2026, 1, 5),
            claim_type=ClaimType.PROFESSIONAL
        )
        
        result1 = await ml_engine.analyze_claim(claim1)
        print(f"   Risk Score: {result1.combined_risk_score:.2%}")
        print(f"   Confidence: {result1.combined_confidence:.2%}")
        print(f"   Recommendation: {result1.recommendation}")
        print(f"   Models Evaluated: {len(result1.model_results)}")
        print()
        
        # Test claim 2: High-risk claim
        print("📋 Test Claim 2: High-Risk Scenario")
        print("-" * 80)
        claim2 = ClaimData(
            claim_id="ML-TEST-002",
            policy_id="POL-002",
            provider_id="PROV-999",  # Unknown provider
            member_id_hash="member_hash_002",
            procedure_codes=[
                ProcedureCode(code="99213", code_type="CPT", quantity=1, line_amount=50000.0)  # High amount
            ],
            diagnosis_codes=[
                DiagnosisCode(code="A00.0", code_type="ICD10_CM", sequence=1)
            ],
            billed_amount=50000.0,  # Unusually high
            service_date=date(2026, 1, 5),
            claim_type=ClaimType.PROFESSIONAL
        )
        
        result2 = await ml_engine.analyze_claim(claim2)
        print(f"   Risk Score: {result2.combined_risk_score:.2%}")
        print(f"   Confidence: {result2.combined_confidence:.2%}")
        print(f"   Recommendation: {result2.recommendation}")
        print(f"   Models Evaluated: {len(result2.model_results)}")
        print()
        
        # Show individual model scores for high-risk claim
        print("   Individual Model Scores:")
        for model_name, score in result2.model_results.items():
            risk_level = "🔴 HIGH" if score > 0.7 else "🟡 MEDIUM" if score > 0.4 else "🟢 LOW"
            print(f"     {model_name:25} {score:6.2%} {risk_level}")
        print()
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_full_pipeline():
    """Test complete DCAL pipeline (Rules + ML + Decision)"""
    print("="*80)
    print("TEST 2: Full Pipeline Testing (Rules + ML + Decision)")
    print("="*80)
    print()
    
    try:
        # Test claim through full orchestrator
        print("📋 Processing Claim Through Full Pipeline")
        print("-" * 80)
        
        claim = ClaimData(
            claim_id="PIPELINE-TEST-001",
            policy_id="POL-001",
            provider_id="PROV-001",
            member_id_hash="member_hash_pipeline",
            procedure_codes=[
                ProcedureCode(code="99213", code_type="CPT", quantity=1, line_amount=50000.0)
            ],
            diagnosis_codes=[
                DiagnosisCode(code="A00.0", code_type="ICD10_CM", sequence=1)
            ],
            billed_amount=50000.0,
            service_date=date(2026, 1, 5),
            claim_type=ClaimType.PROFESSIONAL
        )
        
        print("🔄 Processing claim...")
        report = await orchestrator.process_claim(claim)
        print("✅ Claim processed successfully")
        print()
        
        # Display results
        print("📊 PROCESSING RESULTS")
        print("-" * 80)
        
        if report.decision:
            print(f"Recommendation: {report.decision.recommendation}")
            print(f"Confidence: {report.decision.confidence_score:.2%}")
            print(f"Priority: {report.decision.priority}")
            if report.decision.queue_assignment:
                print(f"Queue: {report.decision.queue_assignment}")
            print()
        
        if report.rule_results:
            passed = [r for r in report.rule_results if r.outcome == "pass"]
            flagged = [r for r in report.rule_results if r.outcome == "flag"]
            failed = [r for r in report.rule_results if r.outcome == "fail"]
            
            print(f"Rule Engine: {len(passed)} passed, {len(flagged)} flagged, {len(failed)} failed")
            if flagged:
                print("   Flagged Rules:")
                for rule in flagged[:3]:
                    print(f"     - {rule.rule_id}: {rule.description}")
            if failed:
                print("   Failed Rules:")
                for rule in failed[:3]:
                    print(f"     - {rule.rule_id}: {rule.description}")
            print()
        
        if report.ml_analysis:
            print(f"ML Analysis:")
            print(f"   Risk Score: {report.ml_analysis.risk_score:.2%}")
            print(f"   Confidence: {report.ml_analysis.confidence:.2%}")
            if report.ml_analysis.risk_indicators:
                print(f"   Risk Indicators: {', '.join(report.ml_analysis.risk_indicators[:3])}")
            print()
        
        print(f"Status: {report.status}")
        print(f"Processed At: {report.processed_at}")
        print()
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_multiple_claims():
    """Test processing multiple claims"""
    print("="*80)
    print("TEST 3: Multiple Claims Processing")
    print("="*80)
    print()
    
    try:
        claims = [
            ClaimData(
                claim_id=f"BATCH-{i:03d}",
                policy_id=f"POL-{i:03d}",
                provider_id="PROV-001",
                member_id_hash=f"member_{i}",
                procedure_codes=[
                    ProcedureCode(code="99213", code_type="CPT", quantity=1, line_amount=100.0 * (i + 1))
                ],
                diagnosis_codes=[
                    DiagnosisCode(code="J06.9", code_type="ICD10_CM", sequence=1)
                ],
                billed_amount=100.0 * (i + 1),
                service_date=date(2026, 1, 5 + i),
                claim_type=ClaimType.PROFESSIONAL
            )
            for i in range(3)
        ]
        
        print(f"🔄 Processing {len(claims)} claims...")
        results = []
        for claim in claims:
            report = await orchestrator.process_claim(claim)
            results.append({
                'claim_id': claim.claim_id,
                'risk_score': report.ml_analysis.risk_score if report.ml_analysis else 0.0,
                'recommendation': report.decision.recommendation if report.decision else "UNKNOWN"
            })
        
        print("✅ All claims processed")
        print()
        print("Results Summary:")
        print("-" * 80)
        for result in results:
            print(f"  {result['claim_id']:15} Risk: {result['risk_score']:6.2%} → {result['recommendation']}")
        print()
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests"""
    print("""
    ╔════════════════════════════════════════════════════════════════════════╗
    ║              DCAL ML MODEL TESTING SUITE                               ║
    ║              Testing ML Fraud Detection Models                        ║
    ╚════════════════════════════════════════════════════════════════════════╝
    """)
    
    results = []
    
    # Test 1: ML Engine Direct
    results.append(("ML Engine Direct", await test_ml_engine_direct()))
    
    # Test 2: Full Pipeline
    results.append(("Full Pipeline", await test_full_pipeline()))
    
    # Test 3: Multiple Claims
    results.append(("Multiple Claims", await test_multiple_claims()))
    
    # Summary
    print("="*80)
    print("TEST SUMMARY")
    print("="*80)
    print()
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:30} {status}")
    
    print()
    print(f"Total: {passed}/{total} tests passed ({(passed/total)*100:.1f}%)")
    print()
    
    if passed == total:
        print("🎉 All tests passed! ML models are operational.")
    else:
        print("⚠️  Some tests failed. Check errors above.")
    
    print()
    print("="*80)
    print("NEXT STEPS")
    print("="*80)
    print()
    print("1. Test via API (requires authentication):")
    print("   http://localhost:8300/docs")
    print()
    print("2. View detailed ML documentation:")
    print("   /root/hiva/services/ai/claims_automation/docs/04_ML_FRAUD_DETECTION.md")
    print()
    print("3. Run pytest suite:")
    print("   pytest tests/test_ml_engine.py -v")
    print()
    print("="*80)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
