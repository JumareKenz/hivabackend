"""
ML Fraud Detection Models
6 specialized models for different fraud patterns
"""

import numpy as np
import logging
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path
import joblib
from datetime import datetime

from ..core.config import settings

logger = logging.getLogger(__name__)

# Try to import ML libraries
try:
    from sklearn.ensemble import IsolationForest, RandomForestClassifier, GradientBoostingClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.cluster import DBSCAN
    import shap
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    logger.warning("sklearn/shap not installed - ML features will use fallback heuristics")


class BaseMLModel:
    """Base class for all ML models"""
    
    def __init__(self, model_name: str, version: str):
        self.model_name = model_name
        self.version = version
        self.model = None
        self.scaler = None
        self.feature_names = []
        self.is_trained = False
    
    def predict(self, features: Dict[str, float]) -> Tuple[float, float, List[Dict]]:
        """
        Make prediction.
        
        Returns:
            (risk_score, confidence, feature_contributions)
        """
        raise NotImplementedError
    
    def load(self, model_path: Path):
        """Load trained model from disk"""
        try:
            model_file = model_path / f"{self.model_name}_v{self.version}.joblib"
            if model_file.exists():
                data = joblib.load(model_file)
                self.model = data['model']
                self.scaler = data['scaler']
                self.feature_names = data['feature_names']
                self.is_trained = True
                logger.info(f"✅ Loaded {self.model_name} v{self.version}")
            else:
                logger.warning(f"Model file not found: {model_file}")
        except Exception as e:
            logger.error(f"Failed to load {self.model_name}: {e}")
    
    def save(self, model_path: Path):
        """Save trained model to disk"""
        try:
            model_path.mkdir(parents=True, exist_ok=True)
            model_file = model_path / f"{self.model_name}_v{self.version}.joblib"
            joblib.dump({
                'model': self.model,
                'scaler': self.scaler,
                'feature_names': self.feature_names
            }, model_file)
            logger.info(f"✅ Saved {self.model_name} to {model_file}")
        except Exception as e:
            logger.error(f"Failed to save {self.model_name}: {e}")


class CostAnomalyDetector(BaseMLModel):
    """
    Detects claims with anomalous costs compared to historical patterns.
    Uses Isolation Forest for anomaly detection.
    """
    
    def __init__(self):
        super().__init__("cost_anomaly", settings.ML_MODEL_COST_ANOMALY_VERSION)
        
        if ML_AVAILABLE:
            self.model = IsolationForest(
                contamination=0.1,
                random_state=42,
                n_estimators=100
            )
            self.scaler = StandardScaler()
        
        # Key features for cost anomalies
        self.feature_names = [
            'claim_amount', 'claim_amount_log', 'num_procedures',
            'avg_procedure_amount', 'max_cost_deviation', 'avg_cost_deviation',
            'provider_avg_claim_amount', 'provider_std_claim_amount',
            'member_avg_claim_amount', 'member_std_claim_amount'
        ]
    
    def predict(self, features: Dict[str, float]) -> Tuple[float, float, List[Dict]]:
        """Detect cost anomalies"""
        
        # Extract relevant features
        X = np.array([[features.get(f, 0.0) for f in self.feature_names]])
        
        if ML_AVAILABLE and self.is_trained:
            # Scale features
            X_scaled = self.scaler.transform(X)
            
            # Get anomaly score
            anomaly_score = self.model.decision_function(X_scaled)[0]
            prediction = self.model.predict(X_scaled)[0]
            
            # Convert to risk score (0-1)
            # Isolation Forest: negative = anomaly, positive = normal
            risk_score = 1.0 / (1.0 + np.exp(anomaly_score))
            confidence = 0.8
            
            # Feature contributions (simplified SHAP alternative)
            contributions = self._compute_contributions(features)
            
        else:
            # Fallback: Rule-based heuristics
            risk_score, confidence, contributions = self._heuristic_detection(features)
        
        return risk_score, confidence, contributions
    
    def _heuristic_detection(self, features: Dict[str, float]) -> Tuple[float, float, List[Dict]]:
        """Rule-based fallback for cost anomaly detection"""
        risk_factors = []
        
        # Check cost deviation
        max_deviation = features.get('max_cost_deviation', 0.0)
        if max_deviation > 3.0:
            risk_factors.append({
                'factor': 'extreme_cost_deviation',
                'value': max_deviation,
                'contribution': 0.4
            })
        elif max_deviation > 2.0:
            risk_factors.append({
                'factor': 'high_cost_deviation',
                'value': max_deviation,
                'contribution': 0.2
            })
        
        # Check against provider average
        claim_amount = features.get('claim_amount', 0.0)
        provider_avg = features.get('provider_avg_claim_amount', 0.0)
        if provider_avg > 0 and claim_amount > provider_avg * 3:
            risk_factors.append({
                'factor': 'exceeds_provider_average',
                'value': claim_amount / provider_avg,
                'contribution': 0.3
            })
        
        # Calculate risk score
        if risk_factors:
            risk_score = min(sum(r['contribution'] for r in risk_factors), 0.9)
            confidence = 0.7
        else:
            risk_score = 0.1
            confidence = 0.6
        
        return risk_score, confidence, risk_factors
    
    def _compute_contributions(self, features: Dict[str, float]) -> List[Dict]:
        """Compute feature contributions (simplified)"""
        contributions = []
        
        for feat in self.feature_names[:5]:  # Top 5 features
            value = features.get(feat, 0.0)
            if abs(value) > 0.01:
                contributions.append({
                    'feature': feat,
                    'value': value,
                    'contribution': abs(value) * 0.1  # Simplified
                })
        
        return sorted(contributions, key=lambda x: x['contribution'], reverse=True)


class BehavioralFraudDetector(BaseMLModel):
    """
    Detects behavioral fraud patterns (e.g., claim rings, systematic abuse).
    Uses Random Forest Classifier.
    """
    
    def __init__(self):
        super().__init__("behavioral_fraud", settings.ML_MODEL_BEHAVIORAL_FRAUD_VERSION)
        
        if ML_AVAILABLE:
            self.model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                random_state=42
            )
            self.scaler = StandardScaler()
        
        self.feature_names = [
            'member_claims_30d', 'member_unique_providers_30d', 'member_has_fraud_flag',
            'provider_claims_30d', 'provider_unique_members_30d', 'provider_fraud_rate',
            'days_since_service', 'submission_lag_category', 'has_prior_auth'
        ]
    
    def predict(self, features: Dict[str, float]) -> Tuple[float, float, List[Dict]]:
        """Detect behavioral fraud patterns"""
        
        X = np.array([[features.get(f, 0.0) for f in self.feature_names]])
        
        if ML_AVAILABLE and self.is_trained:
            X_scaled = self.scaler.transform(X)
            risk_proba = self.model.predict_proba(X_scaled)[0][1]  # Probability of fraud class
            confidence = float(np.max(self.model.predict_proba(X_scaled)[0]))
            contributions = self._compute_contributions(features)
        else:
            risk_proba, confidence, contributions = self._heuristic_behavioral(features)
        
        return risk_proba, confidence, contributions
    
    def _heuristic_behavioral(self, features: Dict[str, float]) -> Tuple[float, float, List[Dict]]:
        """Heuristic behavioral fraud detection"""
        risk_factors = []
        
        # Check member claim frequency
        member_claims_30d = features.get('member_claims_30d', 0.0)
        if member_claims_30d > 15:
            risk_factors.append({
                'factor': 'excessive_member_claims',
                'value': member_claims_30d,
                'contribution': 0.3
            })
        
        # Check provider fraud rate
        provider_fraud_rate = features.get('provider_fraud_rate', 0.0)
        if provider_fraud_rate > 0.1:
            risk_factors.append({
                'factor': 'high_provider_fraud_rate',
                'value': provider_fraud_rate,
                'contribution': 0.4
            })
        
        # Check member fraud flag
        if features.get('member_has_fraud_flag', 0.0) > 0.5:
            risk_factors.append({
                'factor': 'member_fraud_history',
                'value': 1.0,
                'contribution': 0.5
            })
        
        # Check late submission
        submission_lag = features.get('submission_lag_category', 0.0)
        if submission_lag >= 3.0:
            risk_factors.append({
                'factor': 'late_submission',
                'value': submission_lag,
                'contribution': 0.2
            })
        
        if risk_factors:
            risk_score = min(sum(r['contribution'] for r in risk_factors), 0.95)
            confidence = 0.75
        else:
            risk_score = 0.05
            confidence = 0.6
        
        return risk_score, confidence, risk_factors
    
    def _compute_contributions(self, features: Dict[str, float]) -> List[Dict]:
        """Feature importance from Random Forest"""
        contributions = []
        for feat in self.feature_names[:5]:
            value = features.get(feat, 0.0)
            if value > 0:
                contributions.append({
                    'feature': feat,
                    'value': value,
                    'contribution': value * 0.1
                })
        return sorted(contributions, key=lambda x: x['contribution'], reverse=True)


class ProviderAbuseDetector(BaseMLModel):
    """
    Detects provider-level abuse patterns (upcoding, unbundling, phantom billing).
    Uses Gradient Boosting.
    """
    
    def __init__(self):
        super().__init__("provider_abuse", settings.ML_MODEL_PROVIDER_ABUSE_VERSION)
        
        if ML_AVAILABLE:
            self.model = GradientBoostingClassifier(
                n_estimators=100,
                learning_rate=0.1,
                max_depth=5,
                random_state=42
            )
            self.scaler = StandardScaler()
        
        self.feature_names = [
            'provider_claims_30d', 'provider_avg_claim_amount', 'provider_std_claim_amount',
            'provider_fraud_rate', 'provider_denial_rate', 'provider_peer_percentile',
            'provider_claims_per_member', 'provider_volume_trend',
            'num_procedures', 'unique_procedures', 'has_multiple_procedures'
        ]
    
    def predict(self, features: Dict[str, float]) -> Tuple[float, float, List[Dict]]:
        """Detect provider abuse"""
        
        X = np.array([[features.get(f, 0.0) for f in self.feature_names]])
        
        if ML_AVAILABLE and self.is_trained:
            X_scaled = self.scaler.transform(X)
            risk_proba = self.model.predict_proba(X_scaled)[0][1]
            confidence = float(np.max(self.model.predict_proba(X_scaled)[0]))
            contributions = self._compute_contributions(features)
        else:
            risk_proba, confidence, contributions = self._heuristic_provider(features)
        
        return risk_proba, confidence, contributions
    
    def _heuristic_provider(self, features: Dict[str, float]) -> Tuple[float, float, List[Dict]]:
        """Heuristic provider abuse detection"""
        risk_factors = []
        
        # Check volume spike
        volume_trend = features.get('provider_volume_trend', 1.0)
        if volume_trend > 1.5:
            risk_factors.append({
                'factor': 'volume_spike',
                'value': volume_trend,
                'contribution': 0.3
            })
        
        # Check peer comparison
        peer_percentile = features.get('provider_peer_percentile', 0.5)
        if peer_percentile > 0.95:
            risk_factors.append({
                'factor': 'outlier_vs_peers',
                'value': peer_percentile,
                'contribution': 0.35
            })
        
        # Check excessive procedures
        num_procedures = features.get('num_procedures', 0.0)
        if num_procedures > 10:
            risk_factors.append({
                'factor': 'excessive_procedures',
                'value': num_procedures,
                'contribution': 0.25
            })
        
        if risk_factors:
            risk_score = min(sum(r['contribution'] for r in risk_factors), 0.9)
            confidence = 0.7
        else:
            risk_score = 0.1
            confidence = 0.6
        
        return risk_score, confidence, risk_factors
    
    def _compute_contributions(self, features: Dict[str, float]) -> List[Dict]:
        """Feature importance"""
        contributions = []
        for feat in self.feature_names[:5]:
            value = features.get(feat, 0.0)
            if value > 0:
                contributions.append({
                    'feature': feat,
                    'value': value,
                    'contribution': value * 0.08
                })
        return sorted(contributions, key=lambda x: x['contribution'], reverse=True)


class FrequencySpikeDetector(BaseMLModel):
    """Detects unusual frequency spikes in claims submission"""
    
    def __init__(self):
        super().__init__("frequency_spike", settings.ML_MODEL_FREQUENCY_SPIKE_VERSION)
        self.feature_names = [
            'member_claims_30d', 'member_claims_90d', 'provider_claims_30d',
            'provider_avg_per_day', 'provider_volume_trend', 'is_weekend'
        ]
    
    def predict(self, features: Dict[str, float]) -> Tuple[float, float, List[Dict]]:
        """Detect frequency anomalies"""
        risk_factors = []
        
        # Member frequency check
        member_30d = features.get('member_claims_30d', 0.0)
        member_90d = features.get('member_claims_90d', 0.0)
        if member_30d > 10:
            spike = member_30d / max((member_90d / 3.0), 1.0)
            if spike > 2.0:
                risk_factors.append({
                    'factor': 'member_frequency_spike',
                    'value': spike,
                    'contribution': 0.4
                })
        
        # Provider frequency check
        provider_trend = features.get('provider_volume_trend', 1.0)
        if provider_trend > 1.8:
            risk_factors.append({
                'factor': 'provider_volume_spike',
                'value': provider_trend,
                'contribution': 0.35
            })
        
        # Weekend submission (suspicious pattern)
        if features.get('is_weekend', 0.0) > 0.5:
            risk_factors.append({
                'factor': 'weekend_submission',
                'value': 1.0,
                'contribution': 0.15
            })
        
        if risk_factors:
            risk_score = min(sum(r['contribution'] for r in risk_factors), 0.85)
            confidence = 0.65
        else:
            risk_score = 0.05
            confidence = 0.6
        
        return risk_score, confidence, risk_factors


class NetworkAnalysisDetector(BaseMLModel):
    """Detects network-based fraud (claim rings, coordinated fraud)"""
    
    def __init__(self):
        super().__init__("network_analysis", "1.0.0")
        self.feature_names = [
            'member_unique_providers_30d', 'provider_unique_members_30d',
            'provider_claims_per_member', 'is_out_of_network'
        ]
    
    def predict(self, features: Dict[str, float]) -> Tuple[float, float, List[Dict]]:
        """Detect network-based fraud patterns"""
        risk_factors = []
        
        # Check provider shopping (member using many providers)
        member_providers = features.get('member_unique_providers_30d', 0.0)
        if member_providers > 5:
            risk_factors.append({
                'factor': 'provider_shopping',
                'value': member_providers,
                'contribution': 0.3
            })
        
        # Check out-of-network
        if features.get('is_out_of_network', 0.0) > 0.5:
            risk_factors.append({
                'factor': 'out_of_network',
                'value': 1.0,
                'contribution': 0.2
            })
        
        # Check tight provider-member relationship (potential collusion)
        claims_per_member = features.get('provider_claims_per_member', 0.0)
        if claims_per_member > 3.0:
            risk_factors.append({
                'factor': 'high_claims_per_member',
                'value': claims_per_member,
                'contribution': 0.25
            })
        
        if risk_factors:
            risk_score = min(sum(r['contribution'] for r in risk_factors), 0.8)
            confidence = 0.6
        else:
            risk_score = 0.05
            confidence = 0.55
        
        return risk_score, confidence, risk_factors


class TemporalPatternDetector(BaseMLModel):
    """Detects suspicious temporal patterns"""
    
    def __init__(self):
        super().__init__("temporal_pattern", "1.0.0")
        self.feature_names = [
            'days_since_service', 'submission_lag_category', 'is_weekend',
            'is_year_end', 'service_duration_days'
        ]
    
    def predict(self, features: Dict[str, float]) -> Tuple[float, float, List[Dict]]:
        """Detect temporal fraud patterns"""
        risk_factors = []
        
        # Late submission
        submission_lag = features.get('submission_lag_category', 0.0)
        if submission_lag >= 3.0:
            risk_factors.append({
                'factor': 'very_late_submission',
                'value': submission_lag,
                'contribution': 0.3
            })
        
        # Year-end stuffing
        if features.get('is_year_end', 0.0) > 0.5:
            days_since = features.get('days_since_service', 0.0)
            if days_since < 10:
                risk_factors.append({
                    'factor': 'year_end_rush',
                    'value': 1.0,
                    'contribution': 0.2
                })
        
        # Unusually long service duration
        service_duration = features.get('service_duration_days', 0.0)
        if service_duration > 30:
            risk_factors.append({
                'factor': 'extended_service_duration',
                'value': service_duration,
                'contribution': 0.25
            })
        
        if risk_factors:
            risk_score = min(sum(r['contribution'] for r in risk_factors), 0.75)
            confidence = 0.65
        else:
            risk_score = 0.05
            confidence = 0.6
        
        return risk_score, confidence, risk_factors


