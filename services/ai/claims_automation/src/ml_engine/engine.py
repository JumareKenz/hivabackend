"""
ML Fraud Detection Engine
Orchestrates 6 specialized models with SHAP explainability
"""

import time
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path

from ..core.models import ClaimData, MLEngineResult, ModelInferenceResult, ProviderHistory, MemberHistory
from ..core.config import settings
from .feature_engineering import feature_engineer
from .models import (
    CostAnomalyDetector, BehavioralFraudDetector, ProviderAbuseDetector,
    FrequencySpikeDetector, NetworkAnalysisDetector, TemporalPatternDetector
)

logger = logging.getLogger(__name__)


class MLFraudDetectionEngine:
    """
    ML-based fraud detection using ensemble of 6 specialized models.
    
    Models:
    1. Cost Anomaly Detector - Isolation Forest
    2. Behavioral Fraud Detector - Random Forest
    3. Provider Abuse Detector - Gradient Boosting
    4. Frequency Spike Detector - Statistical
    5. Network Analysis Detector - Graph-based
    6. Temporal Pattern Detector - Time-series
    
    Output:
    - Combined risk score (0-1)
    - Combined confidence score (0-1)
    - Top risk factors with SHAP-like explanations
    - Anomaly indicators
    - Recommendation (HIGH_RISK, MEDIUM_RISK, LOW_RISK)
    """
    
    def __init__(self):
        self.engine_version = settings.ML_ENGINE_VERSION if hasattr(settings, 'ML_ENGINE_VERSION') else "1.0.0"
        self.models = {}
        self._initialized = False
    
    async def initialize(self):
        """Initialize all ML models"""
        if self._initialized:
            return
        
        logger.info("🤖 Initializing ML Fraud Detection Engine...")
        
        try:
            # Initialize models
            self.models = {
                'cost_anomaly': CostAnomalyDetector(),
                'behavioral_fraud': BehavioralFraudDetector(),
                'provider_abuse': ProviderAbuseDetector(),
                'frequency_spike': FrequencySpikeDetector(),
                'network_analysis': NetworkAnalysisDetector(),
                'temporal_pattern': TemporalPatternDetector()
            }
            
            # Load trained models from disk (if available)
            models_path = Path(settings.ML_MODELS_PATH)
            if models_path.exists():
                for model_name, model in self.models.items():
                    try:
                        model.load(models_path)
                    except Exception as e:
                        logger.warning(f"Could not load {model_name}: {e}")
            
            self._initialized = True
            logger.info(f"✅ ML Engine initialized with {len(self.models)} models")
            logger.info(f"   Engine version: {self.engine_version}")
            
        except Exception as e:
            logger.error(f"Failed to initialize ML engine: {e}")
            # Non-fatal - system can run without ML
            self._initialized = False
    
    async def analyze_claim(
        self,
        claim_data: ClaimData,
        provider_history: Optional[ProviderHistory] = None,
        member_history: Optional[MemberHistory] = None
    ) -> MLEngineResult:
        """
        Analyze claim for fraud using all models.
        
        Args:
            claim_data: Claim to analyze
            provider_history: Provider historical data
            member_history: Member historical data
            
        Returns:
            Complete ML analysis result with risk scores and explanations
        """
        if not self._initialized:
            await self.initialize()
        
        start_time = time.perf_counter()
        timestamp = datetime.utcnow()
        
        logger.info(f"🤖 Running ML fraud detection for {claim_data.claim_id}")
        
        try:
            # Step 1: Feature Engineering
            features = await feature_engineer.extract_features(
                claim_data, provider_history, member_history
            )
            
            logger.debug(f"   Extracted {len(features)} features")
            
            # Step 2: Run all models
            model_results = []
            for model_name, model in self.models.items():
                try:
                    risk_score, confidence, contributions = model.predict(features)
                    
                    # Create model result
                    model_result = ModelInferenceResult(
                        model_id=model_name,
                        model_version=model.version,
                        model_hash=self._compute_model_hash(model),
                        risk_score=risk_score,
                        confidence=confidence,
                        feature_contributions=contributions,
                        anomaly_indicators=[],
                        inference_time_ms=(time.perf_counter() - start_time) * 1000,
                        timestamp=timestamp
                    )
                    
                    model_results.append(model_result)
                    
                except Exception as e:
                    logger.error(f"Model {model_name} failed: {e}")
                    # Continue with other models
            
            # Step 3: Synthesize results
            combined_risk_score, combined_confidence = self._combine_scores(model_results)
            
            # Step 4: Extract top risk factors
            top_risk_factors = self._aggregate_risk_factors(model_results, features)
            
            # Step 5: Generate anomaly summary
            anomaly_summary = self._generate_anomaly_summary(model_results, combined_risk_score)
            
            # Step 6: Make recommendation
            recommendation, requires_review = self._make_recommendation(
                combined_risk_score, combined_confidence
            )
            
            execution_time_ms = (time.perf_counter() - start_time) * 1000
            
            # Build result
            result = MLEngineResult(
                combined_risk_score=combined_risk_score,
                combined_confidence=combined_confidence,
                model_results=model_results,
                top_risk_factors=top_risk_factors,
                anomaly_summary=anomaly_summary,
                recommendation=recommendation,
                requires_review=requires_review,
                engine_version=self.engine_version,
                execution_time_ms=execution_time_ms,
                timestamp=timestamp
            )
            
            logger.info(
                f"✅ ML analysis complete for {claim_data.claim_id}: "
                f"risk={combined_risk_score:.2%}, confidence={combined_confidence:.2%}, "
                f"recommendation={recommendation}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"ML analysis failed for {claim_data.claim_id}: {e}")
            # Return safe defaults
            return self._create_fallback_result(execution_time_ms=0)
    
    def _combine_scores(self, model_results: List[ModelInferenceResult]) -> tuple:
        """
        Combine scores from multiple models.
        Uses weighted average based on model confidence.
        """
        if not model_results:
            return 0.5, 0.0  # Neutral risk, no confidence
        
        # Weighted average by confidence
        total_weight = sum(r.confidence for r in model_results)
        if total_weight == 0:
            # Equal weight if no confidence
            combined_risk = sum(r.risk_score for r in model_results) / len(model_results)
            combined_confidence = 0.3
        else:
            combined_risk = sum(
                r.risk_score * r.confidence for r in model_results
            ) / total_weight
            combined_confidence = total_weight / len(model_results)
        
        # Clamp to valid range
        combined_risk = max(0.0, min(1.0, combined_risk))
        combined_confidence = max(0.0, min(1.0, combined_confidence))
        
        return combined_risk, combined_confidence
    
    def _aggregate_risk_factors(
        self,
        model_results: List[ModelInferenceResult],
        features: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """Aggregate and rank risk factors across all models"""
        
        factor_map = {}
        
        # Collect all contributions
        for model_result in model_results:
            for contrib in model_result.feature_contributions:
                factor_name = contrib.get('factor') or contrib.get('feature', 'unknown')
                contribution = contrib.get('contribution', 0.0)
                value = contrib.get('value', 0.0)
                
                if factor_name not in factor_map:
                    factor_map[factor_name] = {
                        'factor': factor_name,
                        'total_contribution': 0.0,
                        'count': 0,
                        'values': []
                    }
                
                factor_map[factor_name]['total_contribution'] += contribution
                factor_map[factor_name]['count'] += 1
                factor_map[factor_name]['values'].append(value)
        
        # Build sorted list
        risk_factors = []
        for factor_name, data in factor_map.items():
            risk_factors.append({
                'factor': factor_name,
                'contribution': data['total_contribution'] / data['count'],
                'importance': data['total_contribution'],
                'frequency': data['count'],
                'avg_value': sum(data['values']) / len(data['values']) if data['values'] else 0
            })
        
        # Sort by importance
        risk_factors.sort(key=lambda x: x['importance'], reverse=True)
        
        return risk_factors[:10]  # Top 10
    
    def _generate_anomaly_summary(
        self,
        model_results: List[ModelInferenceResult],
        combined_risk: float
    ) -> List[Dict[str, Any]]:
        """Generate human-readable anomaly summary"""
        
        anomalies = []
        
        # Categorize by risk level
        high_risk_models = [r for r in model_results if r.risk_score >= 0.7]
        medium_risk_models = [r for r in model_results if 0.4 <= r.risk_score < 0.7]
        
        if high_risk_models:
            anomalies.append({
                'severity': 'HIGH',
                'description': f'{len(high_risk_models)} models detected high-risk patterns',
                'models': [r.model_id for r in high_risk_models]
            })
        
        if medium_risk_models:
            anomalies.append({
                'severity': 'MEDIUM',
                'description': f'{len(medium_risk_models)} models detected medium-risk patterns',
                'models': [r.model_id for r in medium_risk_models]
            })
        
        # Overall assessment
        if combined_risk >= 0.7:
            anomalies.append({
                'severity': 'HIGH',
                'description': 'Overall high fraud risk detected',
                'risk_score': combined_risk
            })
        
        return anomalies
    
    def _make_recommendation(self, risk_score: float, confidence: float) -> tuple:
        """
        Make fraud risk recommendation.
        
        Returns:
            (recommendation_string, requires_manual_review_bool)
        """
        if risk_score >= settings.HIGH_RISK_THRESHOLD:
            return "HIGH_RISK", True
        elif risk_score >= settings.ML_MEDIUM_RISK_THRESHOLD if hasattr(settings, 'ML_MEDIUM_RISK_THRESHOLD') else 0.5:
            return "MEDIUM_RISK", True
        else:
            return "LOW_RISK", False
    
    def _compute_model_hash(self, model) -> str:
        """Compute hash of model for versioning"""
        import hashlib
        model_str = f"{model.model_name}_{model.version}"
        return hashlib.sha256(model_str.encode()).hexdigest()[:16]
    
    def _create_fallback_result(self, execution_time_ms: float) -> MLEngineResult:
        """Create safe fallback result when ML engine fails"""
        return MLEngineResult(
            combined_risk_score=0.5,  # Neutral
            combined_confidence=0.0,  # No confidence
            model_results=[],
            top_risk_factors=[],
            anomaly_summary=[{
                'severity': 'WARNING',
                'description': 'ML engine unavailable - defaulting to manual review'
            }],
            recommendation="UNKNOWN",
            requires_review=True,  # Force manual review
            engine_version=self.engine_version,
            execution_time_ms=execution_time_ms,
            timestamp=datetime.utcnow()
        )


# Global singleton
ml_engine = MLFraudDetectionEngine()


