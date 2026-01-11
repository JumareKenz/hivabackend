"""
ML Engine Tests
Comprehensive tests for fraud detection models
"""

import pytest
import asyncio
from datetime import date
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.models import ClaimData, ProcedureCode, DiagnosisCode, ClaimType, ProviderHistory, MemberHistory
from src.ml_engine.engine import ml_engine
from src.ml_engine.feature_engineering import feature_engineer
from src.ml_engine.models import (
    CostAnomalyDetector, BehavioralFraudDetector, ProviderAbuseDetector
)


@pytest.mark.asyncio
async def test_feature_engineering():
    """Test feature extraction"""
    
    claim = ClaimData(
        claim_id="TEST-001",
        policy_id="POL-001",
        provider_id="PRV-001",
        member_id_hash="test_hash",
        procedure_codes=[
            ProcedureCode(code="99213", code_type="CPT", quantity=1, line_amount=150.0)
        ],
        diagnosis_codes=[
            DiagnosisCode(code="J06.9", code_type="ICD10_CM", sequence=1)
        ],
        billed_amount=150.0,
        service_date=date(2026, 1, 5)
    )
    
    features = await feature_engineer.extract_features(claim)
    
    assert len(features) > 50, "Should extract 50+ features"
    assert 'claim_amount' in features
    assert 'num_procedures' in features
    assert features['num_procedures'] == 1.0
    assert features['claim_amount'] == 150.0


@pytest.mark.asyncio
async def test_cost_anomaly_detector():
    """Test cost anomaly detection"""
    
    detector = CostAnomalyDetector()
    
    features = {
        'claim_amount': 1000000.0,  # Very high amount
        'claim_amount_log': 13.8,
        'max_cost_deviation': 5.0,  # Extreme deviation
        'provider_avg_claim_amount': 50000.0
    }
    
    risk_score, confidence, contributions = detector.predict(features)
    
    assert 0.0 <= risk_score <= 1.0, "Risk score should be in [0, 1]"
    assert 0.0 <= confidence <= 1.0, "Confidence should be in [0, 1]"
    assert risk_score > 0.5, "High amount should trigger high risk"
    assert len(contributions) > 0, "Should have risk factors"


@pytest.mark.asyncio
async def test_behavioral_fraud_detector():
    """Test behavioral fraud detection"""
    
    detector = BehavioralFraudDetector()
    
    features = {
        'member_claims_30d': 25.0,  # Excessive claims
        'member_has_fraud_flag': 1.0,  # Known fraud history
        'provider_fraud_rate': 0.15,  # High fraud rate
        'submission_lag_category': 4.0  # Very late
    }
    
    risk_score, confidence, contributions = detector.predict(features)
    
    assert risk_score > 0.5, "Multiple fraud indicators should trigger high risk"
    assert len(contributions) > 0


@pytest.mark.asyncio
async def test_ml_engine_initialization():
    """Test ML engine initializes correctly"""
    
    await ml_engine.initialize()
    
    assert ml_engine._initialized
    assert len(ml_engine.models) == 6, "Should have 6 models"
    assert 'cost_anomaly' in ml_engine.models
    assert 'behavioral_fraud' in ml_engine.models
    assert 'provider_abuse' in ml_engine.models


@pytest.mark.asyncio
async def test_ml_engine_analysis():
    """Test complete ML analysis pipeline"""
    
    await ml_engine.initialize()
    
    claim = ClaimData(
        claim_id="TEST-ML-001",
        policy_id="POL-001",
        provider_id="PRV-001",
        member_id_hash="test_member",
        procedure_codes=[
            ProcedureCode(code="99213", code_type="CPT", quantity=1, line_amount=150.0)
        ],
        diagnosis_codes=[
            DiagnosisCode(code="J06.9", code_type="ICD10_CM", sequence=1)
        ],
        billed_amount=150.0,
        service_date=date(2026, 1, 5)
    )
    
    result = await ml_engine.analyze_claim(claim)
    
    assert result is not None
    assert 0.0 <= result.combined_risk_score <= 1.0
    assert 0.0 <= result.combined_confidence <= 1.0
    assert result.recommendation in ["HIGH_RISK", "MEDIUM_RISK", "LOW_RISK"]
    assert len(result.model_results) == 6, "Should have results from all 6 models"


@pytest.mark.asyncio
async def test_high_risk_claim_detection():
    """Test that high-risk claims are properly flagged"""
    
    await ml_engine.initialize()
    
    # Create suspicious claim
    claim = ClaimData(
        claim_id="FRAUD-001",
        policy_id="POL-001",
        provider_id="PRV-001",
        member_id_hash="suspicious_member",
        procedure_codes=[
            ProcedureCode(code="99999", code_type="CPT", quantity=10, line_amount=100000.0)
        ],
        diagnosis_codes=[
            DiagnosisCode(code="Z00.0", code_type="ICD10_CM", sequence=1)
        ],
        billed_amount=1000000.0,  # Extremely high amount
        service_date=date(2026, 1, 5)
    )
    
    # Create suspicious provider history
    provider_history = ProviderHistory(
        provider_id="PRV-001",
        claims_30d=500,  # Excessive volume
        fraud_rate=0.2,  # High fraud rate
        peer_percentile=0.99  # Outlier
    )
    
    result = await ml_engine.analyze_claim(claim, provider_history=provider_history)
    
    assert result.combined_risk_score > 0.6, "Should detect high risk"
    assert result.requires_review, "Should require manual review"
    assert result.recommendation in ["HIGH_RISK", "MEDIUM_RISK"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


