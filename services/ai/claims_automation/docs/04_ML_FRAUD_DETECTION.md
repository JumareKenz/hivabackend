# ML Fraud Detection Engine Specification

**Version:** 1.0.0  
**Date:** January 7, 2026  
**Classification:** CONFIDENTIAL - Technical Specification

---

## 1. Overview

The ML Fraud Detection Engine is the **second gate** in the claims automation pipeline. It uses machine learning models to detect cost anomalies, behavioral fraud patterns, provider abuse, and claim frequency spikes. This engine operates under strict constraints to ensure safety, explainability, and auditability.

### 1.1 Core Constraints

| Constraint | Enforcement |
|------------|-------------|
| **Advisory Only** | ML outputs are recommendations, never direct actions |
| **Never Override Rules** | Deterministic rule failures take precedence |
| **Explainable** | Every prediction includes feature contributions |
| **Versioned** | All models are versioned with cryptographic hashes |
| **No Autonomous Learning** | Retraining requires human approval |
| **Confidence-Aware** | Low confidence → Force manual review |

### 1.2 ML Engine Position in Pipeline

```
                        GATE 2: ML FRAUD DETECTION ENGINE
    ════════════════════════════════════════════════════════════════

    ┌─────────────────┐
    │  Rule Engine    │
    │  Output         │
    │  (Gate 1)       │
    └────────┬────────┘
             │
             │ [If not HARD FAIL]
             ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                    ML FRAUD DETECTION ENGINE                     │
    │                                                                  │
    │  ┌──────────────────────────────────────────────────────────┐  │
    │  │                  FEATURE ENGINEERING                      │  │
    │  │                                                           │  │
    │  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │  │
    │  │  │ Claim       │  │ Historical  │  │ Provider    │      │  │
    │  │  │ Features    │  │ Features    │  │ Features    │      │  │
    │  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘      │  │
    │  │         └────────────────┼────────────────┘              │  │
    │  └──────────────────────────┼───────────────────────────────┘  │
    │                             │                                   │
    │                             ▼                                   │
    │  ┌──────────────────────────────────────────────────────────┐  │
    │  │                  MODEL ENSEMBLE                           │  │
    │  │                                                           │  │
    │  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │  │
    │  │  │ COST        │  │ BEHAVIORAL  │  │ PROVIDER    │      │  │
    │  │  │ ANOMALY     │  │ FRAUD       │  │ ABUSE       │      │  │
    │  │  │ MODEL       │  │ MODEL       │  │ MODEL       │      │  │
    │  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘      │  │
    │  │         │                │                │              │  │
    │  │  ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐      │  │
    │  │  │ FREQUENCY   │  │ NETWORK     │  │ TEMPORAL    │      │  │
    │  │  │ SPIKE       │  │ ANALYSIS    │  │ PATTERN     │      │  │
    │  │  │ MODEL       │  │ MODEL       │  │ MODEL       │      │  │
    │  │  └─────────────┘  └─────────────┘  └─────────────┘      │  │
    │  └──────────────────────────────────────────────────────────┘  │
    │                             │                                   │
    │                             ▼                                   │
    │  ┌──────────────────────────────────────────────────────────┐  │
    │  │                  EXPLAINABILITY LAYER                     │  │
    │  │                                                           │  │
    │  │  • SHAP Values for feature importance                     │  │
    │  │  • Counterfactual explanations                           │  │
    │  │  • Confidence intervals                                   │  │
    │  │  • Anomaly indicators                                     │  │
    │  │                                                           │  │
    │  └──────────────────────────────────────────────────────────┘  │
    │                             │                                   │
    │                             ▼                                   │
    │  ┌──────────────────────────────────────────────────────────┐  │
    │  │                  OUTPUT SYNTHESIS                         │  │
    │  │                                                           │  │
    │  │    Risk Score: 0.0 - 1.0                                 │  │
    │  │    Confidence: 0.0 - 1.0                                 │  │
    │  │    Risk Factors: [ordered by contribution]               │  │
    │  │    Anomaly Indicators: [type, severity, explanation]     │  │
    │  │                                                           │  │
    │  └──────────────────────────────────────────────────────────┘  │
    └─────────────────────────────────────────────────────────────────┘
             │
             ▼
    ┌─────────────────┐
    │  ML Output      │
    │  + Explanations │
    └─────────────────┘

    ════════════════════════════════════════════════════════════════
```

---

## 2. Model Architecture

### 2.1 Model Inventory

| Model ID | Name | Type | Purpose | Update Frequency |
|----------|------|------|---------|------------------|
| `FRD-COST-001` | Cost Anomaly Detector | Isolation Forest + XGBoost | Detect billing anomalies | Monthly |
| `FRD-BEHV-001` | Behavioral Fraud Model | Gradient Boosting | Pattern-based fraud detection | Bi-weekly |
| `FRD-PROV-001` | Provider Abuse Detector | Graph Neural Network | Provider network fraud | Monthly |
| `FRD-FREQ-001` | Frequency Spike Model | LSTM Autoencoder | Temporal anomalies | Weekly |
| `FRD-NETW-001` | Network Analysis Model | Graph Embedding | Collusion detection | Monthly |
| `FRD-TEMP-001` | Temporal Pattern Model | Time Series Anomaly | Scheduling fraud | Weekly |

### 2.2 Model Registry Schema

```python
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum

class ModelStatus(Enum):
    DEVELOPMENT = "DEVELOPMENT"
    TESTING = "TESTING"
    CANARY = "CANARY"
    PRODUCTION = "PRODUCTION"
    DEPRECATED = "DEPRECATED"
    DISABLED = "DISABLED"

@dataclass(frozen=True)
class ModelMetadata:
    """Immutable model metadata for audit and versioning."""
    model_id: str
    version: str
    name: str
    description: str
    model_type: str
    
    # Training info
    training_date: datetime
    training_data_hash: str          # SHA-256 of training data
    training_data_size: int          # Number of training samples
    training_parameters: Dict[str, Any]
    
    # Artifacts
    model_artifact_path: str
    model_hash: str                  # SHA-256 of serialized model
    feature_schema_version: str
    
    # Performance metrics
    validation_metrics: Dict[str, float]
    test_metrics: Dict[str, float]
    
    # Deployment
    status: ModelStatus
    deployed_at: Optional[datetime]
    deployed_by: Optional[str]
    
    # Audit
    created_by: str
    created_at: datetime
    approved_by: Optional[str]
    approved_at: Optional[datetime]
    
    def get_signature(self) -> str:
        """Get unique signature for this model version."""
        return f"{self.model_id}:{self.version}:{self.model_hash[:16]}"

@dataclass
class ModelInferenceResult:
    """Result from a single model inference."""
    model_id: str
    model_version: str
    model_hash: str
    
    risk_score: float               # 0.0 - 1.0
    confidence: float               # 0.0 - 1.0
    
    feature_contributions: List[Dict[str, Any]]
    anomaly_indicators: List[Dict[str, Any]]
    
    inference_time_ms: float
    timestamp: datetime

@dataclass
class MLEngineResult:
    """Aggregated result from ML engine."""
    combined_risk_score: float
    combined_confidence: float
    
    model_results: List[ModelInferenceResult]
    
    top_risk_factors: List[Dict[str, Any]]
    anomaly_summary: List[Dict[str, Any]]
    
    recommendation: str             # HIGH_RISK, MEDIUM_RISK, LOW_RISK
    requires_review: bool
    
    engine_version: str
    execution_time_ms: float
    timestamp: datetime
```

---

## 3. Feature Engineering

### 3.1 Feature Categories

```python
class FeatureCategory(Enum):
    CLAIM_BASIC = "CLAIM_BASIC"           # Direct claim attributes
    CLAIM_DERIVED = "CLAIM_DERIVED"       # Calculated from claim
    MEMBER_HISTORY = "MEMBER_HISTORY"     # Member claim history
    PROVIDER_HISTORY = "PROVIDER_HISTORY" # Provider behavior
    PROVIDER_NETWORK = "PROVIDER_NETWORK" # Provider relationships
    TEMPORAL = "TEMPORAL"                 # Time-based features
    STATISTICAL = "STATISTICAL"           # Statistical aggregations
    GRAPH = "GRAPH"                       # Network graph features
```

### 3.2 Feature Definitions

```yaml
features:
  # ═══════════════════════════════════════════════════════════════
  # CLAIM BASIC FEATURES
  # ═══════════════════════════════════════════════════════════════
  claim_basic:
    - name: billed_amount
      type: float
      description: Total billed amount for the claim
      source: claim.billed_amount
      preprocessing: log_transform
      
    - name: procedure_count
      type: int
      description: Number of procedure codes on claim
      source: len(claim.procedure_codes)
      
    - name: diagnosis_count
      type: int
      description: Number of diagnosis codes
      source: len(claim.diagnosis_codes)
      
    - name: claim_type_encoded
      type: categorical
      description: Type of claim (one-hot encoded)
      source: claim.claim_type
      categories: [PROFESSIONAL, INSTITUTIONAL, DENTAL, PHARMACY, VISION]
      
    - name: facility_type_encoded
      type: categorical
      description: Facility type (one-hot encoded)
      source: claim.facility_type
      categories: [INPATIENT_HOSPITAL, OUTPATIENT_HOSPITAL, PHYSICIAN_OFFICE, ...]
      
    - name: network_status_encoded
      type: categorical
      description: In/out of network
      source: claim.network_status
      categories: [IN_NETWORK, OUT_OF_NETWORK, UNKNOWN]

  # ═══════════════════════════════════════════════════════════════
  # CLAIM DERIVED FEATURES
  # ═══════════════════════════════════════════════════════════════
  claim_derived:
    - name: avg_line_amount
      type: float
      description: Average amount per procedure line
      source: claim.billed_amount / len(claim.procedure_codes)
      preprocessing: log_transform
      
    - name: max_line_amount
      type: float
      description: Maximum single line amount
      source: max(claim.procedure_codes, key=line_amount)
      preprocessing: log_transform
      
    - name: has_high_cost_procedure
      type: bool
      description: Contains procedure in top 5% by cost
      source: any(p.code in HIGH_COST_CODES for p in claim.procedure_codes)
      
    - name: modifier_count
      type: int
      description: Total modifiers across all lines
      source: sum(len(p.modifiers) for p in claim.procedure_codes)
      
    - name: service_duration_days
      type: int
      description: Days between service start and end
      source: (claim.service_date_end - claim.service_date).days
      default: 0
      
    - name: submission_lag_days
      type: int
      description: Days between service and submission
      source: (claim.submission_timestamp - claim.service_date).days
      
    - name: amount_per_diagnosis
      type: float
      description: Billed amount divided by number of diagnoses
      source: claim.billed_amount / max(1, len(claim.diagnosis_codes))
      preprocessing: log_transform

  # ═══════════════════════════════════════════════════════════════
  # MEMBER HISTORY FEATURES
  # ═══════════════════════════════════════════════════════════════
  member_history:
    - name: member_claims_30d
      type: int
      description: Member claims in last 30 days
      source: count(member.claims_history, days=30)
      
    - name: member_claims_90d
      type: int
      description: Member claims in last 90 days
      source: count(member.claims_history, days=90)
      
    - name: member_claims_365d
      type: int
      description: Member claims in last 365 days
      source: count(member.claims_history, days=365)
      
    - name: member_total_billed_30d
      type: float
      description: Total billed amount in last 30 days
      source: sum(member.claims_history.billed_amount, days=30)
      preprocessing: log_transform
      
    - name: member_total_billed_90d
      type: float
      description: Total billed amount in last 90 days
      source: sum(member.claims_history.billed_amount, days=90)
      preprocessing: log_transform
      
    - name: member_avg_claim_amount
      type: float
      description: Member's average claim amount (lifetime)
      source: avg(member.claims_history.billed_amount)
      preprocessing: log_transform
      
    - name: member_claim_amount_zscore
      type: float
      description: Z-score of current claim vs member history
      source: (claim.billed_amount - member.avg_claim) / member.std_claim
      
    - name: member_unique_providers_30d
      type: int
      description: Distinct providers visited in 30 days
      source: count_distinct(member.claims_history.provider_id, days=30)
      
    - name: member_unique_providers_90d
      type: int
      description: Distinct providers visited in 90 days
      source: count_distinct(member.claims_history.provider_id, days=90)
      
    - name: member_same_day_claims
      type: int
      description: Other claims on same service date
      source: count(member.claims_history, same_date=true)
      
    - name: member_fraud_history
      type: bool
      description: Member has confirmed fraud in history
      source: member.has_fraud_flag
      
    - name: member_denial_rate
      type: float
      description: Historical claim denial rate
      source: member.denied_claims / max(1, member.total_claims)

  # ═══════════════════════════════════════════════════════════════
  # PROVIDER HISTORY FEATURES
  # ═══════════════════════════════════════════════════════════════
  provider_history:
    - name: provider_claims_30d
      type: int
      description: Provider claims submitted in last 30 days
      source: count(provider.claims_history, days=30)
      
    - name: provider_claims_90d
      type: int
      description: Provider claims submitted in last 90 days
      source: count(provider.claims_history, days=90)
      
    - name: provider_total_billed_30d
      type: float
      description: Provider total billed in last 30 days
      source: sum(provider.claims_history.billed_amount, days=30)
      preprocessing: log_transform
      
    - name: provider_avg_claim_amount
      type: float
      description: Provider average claim amount
      source: avg(provider.claims_history.billed_amount)
      preprocessing: log_transform
      
    - name: provider_claim_amount_zscore
      type: float
      description: Z-score vs provider's typical claims
      source: (claim.billed_amount - provider.avg_claim) / provider.std_claim
      
    - name: provider_unique_members_30d
      type: int
      description: Distinct members seen in 30 days
      source: count_distinct(provider.claims_history.member_id, days=30)
      
    - name: provider_claims_per_member_30d
      type: float
      description: Average claims per member in 30 days
      source: provider.claims_30d / max(1, provider.unique_members_30d)
      
    - name: provider_denial_rate
      type: float
      description: Provider's historical denial rate
      source: provider.denied_claims / max(1, provider.total_claims)
      
    - name: provider_fraud_rate
      type: float
      description: Provider's confirmed fraud rate
      source: provider.fraud_claims / max(1, provider.total_claims)
      
    - name: provider_peer_amount_percentile
      type: float
      description: Percentile vs peer providers (same specialty)
      source: percentile(provider.avg_claim, provider.peer_group)
      
    - name: provider_tenure_months
      type: int
      description: Months provider has been in network
      source: months_since(provider.effective_date)
      
    - name: provider_specialty_match
      type: bool
      description: Procedures match provider specialty
      source: all(p.specialty in provider.specialties for p in claim.procedures)

  # ═══════════════════════════════════════════════════════════════
  # TEMPORAL FEATURES
  # ═══════════════════════════════════════════════════════════════
  temporal:
    - name: day_of_week
      type: categorical
      description: Day of week of service
      source: claim.service_date.weekday()
      categories: [0, 1, 2, 3, 4, 5, 6]
      
    - name: is_weekend
      type: bool
      description: Service on weekend
      source: claim.service_date.weekday() >= 5
      
    - name: is_month_end
      type: bool
      description: Service in last 5 days of month
      source: claim.service_date.day >= 26
      
    - name: is_quarter_end
      type: bool
      description: Service in last week of quarter
      source: is_quarter_end(claim.service_date)
      
    - name: is_year_end
      type: bool
      description: Service in December
      source: claim.service_date.month == 12
      
    - name: hour_of_day
      type: int
      description: Hour claim was submitted
      source: claim.submission_timestamp.hour
      
    - name: is_after_hours_submission
      type: bool
      description: Submitted outside business hours
      source: claim.submission_timestamp.hour < 8 or > 18

  # ═══════════════════════════════════════════════════════════════
  # STATISTICAL FEATURES
  # ═══════════════════════════════════════════════════════════════
  statistical:
    - name: amount_vs_procedure_median
      type: float
      description: Ratio of amount to procedure code median
      source: claim.billed_amount / tariff.get_median(claim.primary_procedure)
      
    - name: amount_vs_procedure_95th
      type: float
      description: Ratio of amount to 95th percentile
      source: claim.billed_amount / tariff.get_percentile(claim.primary_procedure, 95)
      
    - name: amount_vs_diagnosis_median
      type: float
      description: Ratio vs median for primary diagnosis
      source: claim.billed_amount / stats.diagnosis_median(claim.primary_diagnosis)
      
    - name: procedure_rarity_score
      type: float
      description: How rare is this procedure combination
      source: -log(stats.procedure_frequency(claim.procedure_codes))
      
    - name: diagnosis_procedure_compatibility
      type: float
      description: Statistical compatibility score
      source: stats.dx_px_compatibility(claim.diagnosis_codes, claim.procedure_codes)
      
    - name: regional_amount_zscore
      type: float
      description: Z-score vs regional average
      source: (claim.billed_amount - stats.regional_avg) / stats.regional_std

  # ═══════════════════════════════════════════════════════════════
  # GRAPH/NETWORK FEATURES
  # ═══════════════════════════════════════════════════════════════
  graph:
    - name: provider_member_edge_count
      type: int
      description: Number of edges between provider and member
      source: graph.edge_count(provider_id, member_id)
      
    - name: provider_centrality
      type: float
      description: Provider's centrality in referral network
      source: graph.centrality(provider_id)
      
    - name: member_provider_cluster_size
      type: int
      description: Size of member's provider cluster
      source: graph.cluster_size(member_id)
      
    - name: shared_member_count
      type: int
      description: Members shared with referring provider
      source: graph.shared_members(provider_id, referring_provider_id)
      
    - name: suspicious_cluster_flag
      type: bool
      description: Provider in flagged suspicious cluster
      source: graph.is_suspicious_cluster(provider_id)
```

### 3.3 Feature Pipeline

```python
from typing import Dict, Any, List
import numpy as np
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.impute import SimpleImputer

class FeaturePipeline:
    """
    Deterministic feature engineering pipeline.
    Produces consistent feature vectors from claim data.
    """
    
    def __init__(self, config: FeatureConfig):
        self.config = config
        self.feature_definitions = self._load_feature_definitions()
        self.preprocessors = self._initialize_preprocessors()
        self.feature_names: List[str] = []
        self._build_feature_names()
    
    def extract_features(self, claim_data: ClaimData) -> np.ndarray:
        """
        Extract feature vector from claim data.
        Returns numpy array suitable for model input.
        """
        features = {}
        
        # Extract each feature category
        features.update(self._extract_claim_basic(claim_data))
        features.update(self._extract_claim_derived(claim_data))
        features.update(self._extract_member_history(claim_data))
        features.update(self._extract_provider_history(claim_data))
        features.update(self._extract_temporal(claim_data))
        features.update(self._extract_statistical(claim_data))
        features.update(self._extract_graph(claim_data))
        
        # Apply preprocessing
        feature_vector = self._preprocess_features(features)
        
        return feature_vector
    
    def _extract_claim_basic(self, claim_data: ClaimData) -> Dict[str, Any]:
        """Extract basic claim features."""
        return {
            'billed_amount': claim_data.claim.billed_amount,
            'procedure_count': len(claim_data.claim.procedure_codes),
            'diagnosis_count': len(claim_data.claim.diagnosis_codes),
            'claim_type': claim_data.claim.claim_type,
            'facility_type': claim_data.claim.facility_type,
            'network_status': claim_data.claim.network_status,
        }
    
    def _extract_member_history(self, claim_data: ClaimData) -> Dict[str, Any]:
        """Extract member history features."""
        member_history = claim_data.member_history
        
        return {
            'member_claims_30d': member_history.get_claim_count(days=30),
            'member_claims_90d': member_history.get_claim_count(days=90),
            'member_claims_365d': member_history.get_claim_count(days=365),
            'member_total_billed_30d': member_history.get_total_billed(days=30),
            'member_total_billed_90d': member_history.get_total_billed(days=90),
            'member_avg_claim_amount': member_history.get_avg_claim_amount(),
            'member_claim_amount_zscore': self._compute_zscore(
                claim_data.claim.billed_amount,
                member_history.get_avg_claim_amount(),
                member_history.get_std_claim_amount()
            ),
            'member_unique_providers_30d': member_history.get_unique_providers(days=30),
            'member_unique_providers_90d': member_history.get_unique_providers(days=90),
            'member_same_day_claims': member_history.get_same_day_claims(
                claim_data.claim.service_date
            ),
            'member_fraud_history': member_history.has_fraud_flag,
            'member_denial_rate': member_history.get_denial_rate(),
        }
    
    def _extract_provider_history(self, claim_data: ClaimData) -> Dict[str, Any]:
        """Extract provider history features."""
        provider_history = claim_data.provider_history
        
        return {
            'provider_claims_30d': provider_history.get_claim_count(days=30),
            'provider_claims_90d': provider_history.get_claim_count(days=90),
            'provider_total_billed_30d': provider_history.get_total_billed(days=30),
            'provider_avg_claim_amount': provider_history.get_avg_claim_amount(),
            'provider_claim_amount_zscore': self._compute_zscore(
                claim_data.claim.billed_amount,
                provider_history.get_avg_claim_amount(),
                provider_history.get_std_claim_amount()
            ),
            'provider_unique_members_30d': provider_history.get_unique_members(days=30),
            'provider_claims_per_member_30d': provider_history.get_claims_per_member(days=30),
            'provider_denial_rate': provider_history.get_denial_rate(),
            'provider_fraud_rate': provider_history.get_fraud_rate(),
            'provider_peer_amount_percentile': provider_history.get_peer_percentile(),
            'provider_tenure_months': provider_history.get_tenure_months(),
            'provider_specialty_match': self._check_specialty_match(claim_data),
        }
    
    def _preprocess_features(self, features: Dict[str, Any]) -> np.ndarray:
        """Apply preprocessing transformations."""
        processed = []
        
        for feature_name in self.feature_names:
            value = features.get(feature_name)
            feature_def = self.feature_definitions.get(feature_name)
            
            if feature_def is None:
                raise ValueError(f"Unknown feature: {feature_name}")
            
            # Handle missing values
            if value is None:
                value = feature_def.get('default', 0)
            
            # Apply preprocessing
            preprocessing = feature_def.get('preprocessing')
            if preprocessing == 'log_transform':
                value = np.log1p(max(0, value))
            elif preprocessing == 'clip':
                min_val = feature_def.get('clip_min', float('-inf'))
                max_val = feature_def.get('clip_max', float('inf'))
                value = np.clip(value, min_val, max_val)
            
            processed.append(value)
        
        return np.array(processed, dtype=np.float32)
    
    def _compute_zscore(self, value: float, mean: float, std: float) -> float:
        """Compute z-score with safe division."""
        if std == 0 or std is None:
            return 0.0
        return (value - mean) / std
    
    def get_feature_names(self) -> List[str]:
        """Return ordered list of feature names."""
        return self.feature_names.copy()
    
    def get_feature_importance_mapping(self) -> Dict[str, int]:
        """Return mapping of feature names to indices."""
        return {name: idx for idx, name in enumerate(self.feature_names)}
```

---

## 4. Model Implementations

### 4.1 Cost Anomaly Detector

```python
from sklearn.ensemble import IsolationForest
import xgboost as xgb

class CostAnomalyDetector:
    """
    Hybrid model for detecting cost anomalies.
    Combines Isolation Forest (unsupervised) with XGBoost (supervised).
    """
    
    MODEL_ID = "FRD-COST-001"
    
    def __init__(self, model_path: str, config: ModelConfig):
        self.config = config
        self.isolation_forest = self._load_isolation_forest(model_path)
        self.xgb_model = self._load_xgboost(model_path)
        self.metadata = self._load_metadata(model_path)
        
        # Validate model integrity
        self._validate_model_hash()
    
    def predict(self, features: np.ndarray) -> ModelInferenceResult:
        """
        Predict cost anomaly score.
        Returns score between 0 (normal) and 1 (highly anomalous).
        """
        start_time = time.perf_counter()
        
        # Isolation Forest anomaly score
        if_score = self.isolation_forest.decision_function(features.reshape(1, -1))[0]
        # Convert to 0-1 range (more negative = more anomalous)
        if_score_normalized = 1 / (1 + np.exp(if_score))
        
        # XGBoost fraud probability
        xgb_proba = self.xgb_model.predict_proba(features.reshape(1, -1))[0][1]
        
        # Combine scores (weighted average)
        combined_score = (
            self.config.isolation_forest_weight * if_score_normalized +
            self.config.xgboost_weight * xgb_proba
        )
        
        # Compute confidence based on agreement
        agreement = 1 - abs(if_score_normalized - xgb_proba)
        confidence = agreement * 0.5 + 0.5  # Scale to 0.5-1.0
        
        # Get feature contributions
        feature_contributions = self._compute_shap_values(features)
        
        # Identify anomaly indicators
        anomaly_indicators = self._identify_anomalies(features, combined_score)
        
        inference_time = (time.perf_counter() - start_time) * 1000
        
        return ModelInferenceResult(
            model_id=self.MODEL_ID,
            model_version=self.metadata.version,
            model_hash=self.metadata.model_hash,
            risk_score=float(combined_score),
            confidence=float(confidence),
            feature_contributions=feature_contributions,
            anomaly_indicators=anomaly_indicators,
            inference_time_ms=inference_time,
            timestamp=datetime.utcnow()
        )
    
    def _compute_shap_values(self, features: np.ndarray) -> List[Dict[str, Any]]:
        """Compute SHAP values for explainability."""
        import shap
        
        explainer = shap.TreeExplainer(self.xgb_model)
        shap_values = explainer.shap_values(features.reshape(1, -1))[0]
        
        # Get feature names
        feature_names = self.config.feature_pipeline.get_feature_names()
        
        # Sort by absolute contribution
        contributions = []
        for idx, (name, value) in enumerate(zip(feature_names, shap_values)):
            contributions.append({
                'feature': name,
                'shap_value': float(value),
                'contribution': float(abs(value)),
                'direction': 'increases_risk' if value > 0 else 'decreases_risk',
                'feature_value': float(features[idx])
            })
        
        # Return top contributors
        contributions.sort(key=lambda x: x['contribution'], reverse=True)
        return contributions[:10]
    
    def _identify_anomalies(
        self,
        features: np.ndarray,
        risk_score: float
    ) -> List[Dict[str, Any]]:
        """Identify specific anomaly indicators."""
        anomalies = []
        feature_names = self.config.feature_pipeline.get_feature_names()
        
        # Check for specific anomaly patterns
        feature_dict = dict(zip(feature_names, features))
        
        # Cost anomaly patterns
        if feature_dict.get('amount_vs_procedure_95th', 0) > 1.0:
            anomalies.append({
                'indicator_type': 'COST_ANOMALY',
                'severity': 'HIGH' if feature_dict['amount_vs_procedure_95th'] > 2.0 else 'MEDIUM',
                'score': min(1.0, feature_dict['amount_vs_procedure_95th'] / 3.0),
                'explanation': f"Billed amount exceeds 95th percentile by {(feature_dict['amount_vs_procedure_95th'] - 1) * 100:.1f}%"
            })
        
        if feature_dict.get('provider_claim_amount_zscore', 0) > 3.0:
            anomalies.append({
                'indicator_type': 'PROVIDER_ANOMALY',
                'severity': 'MEDIUM',
                'score': min(1.0, feature_dict['provider_claim_amount_zscore'] / 5.0),
                'explanation': f"Claim amount is {feature_dict['provider_claim_amount_zscore']:.1f} standard deviations above provider's average"
            })
        
        return anomalies
```

### 4.2 Behavioral Fraud Model

```python
class BehavioralFraudModel:
    """
    Gradient Boosting model for detecting behavioral fraud patterns.
    Trained on confirmed fraud cases with pattern-based features.
    """
    
    MODEL_ID = "FRD-BEHV-001"
    
    def __init__(self, model_path: str, config: ModelConfig):
        self.config = config
        self.model = self._load_model(model_path)
        self.metadata = self._load_metadata(model_path)
        self.fraud_patterns = self._load_fraud_patterns()
        
        self._validate_model_hash()
    
    def predict(self, features: np.ndarray, claim_data: ClaimData) -> ModelInferenceResult:
        """Predict behavioral fraud probability."""
        start_time = time.perf_counter()
        
        # Model prediction
        proba = self.model.predict_proba(features.reshape(1, -1))[0][1]
        
        # Pattern matching
        pattern_scores = self._check_fraud_patterns(claim_data)
        
        # Combine model score with pattern matches
        combined_score = proba
        if pattern_scores:
            pattern_weight = min(0.3, len(pattern_scores) * 0.1)
            avg_pattern_score = np.mean([p['score'] for p in pattern_scores])
            combined_score = (1 - pattern_weight) * proba + pattern_weight * avg_pattern_score
        
        # Confidence
        confidence = self._compute_confidence(proba, pattern_scores)
        
        # Feature contributions
        feature_contributions = self._compute_feature_importance(features)
        
        # Anomaly indicators
        anomaly_indicators = self._patterns_to_indicators(pattern_scores)
        
        inference_time = (time.perf_counter() - start_time) * 1000
        
        return ModelInferenceResult(
            model_id=self.MODEL_ID,
            model_version=self.metadata.version,
            model_hash=self.metadata.model_hash,
            risk_score=float(combined_score),
            confidence=float(confidence),
            feature_contributions=feature_contributions,
            anomaly_indicators=anomaly_indicators,
            inference_time_ms=inference_time,
            timestamp=datetime.utcnow()
        )
    
    def _check_fraud_patterns(self, claim_data: ClaimData) -> List[Dict[str, Any]]:
        """Check claim against known fraud patterns."""
        matched_patterns = []
        
        for pattern in self.fraud_patterns:
            if pattern.matches(claim_data):
                matched_patterns.append({
                    'pattern_id': pattern.pattern_id,
                    'pattern_name': pattern.name,
                    'score': pattern.risk_score,
                    'description': pattern.description
                })
        
        return matched_patterns
    
    def _patterns_to_indicators(
        self,
        pattern_scores: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Convert pattern matches to anomaly indicators."""
        indicators = []
        
        for pattern in pattern_scores:
            severity = 'HIGH' if pattern['score'] > 0.7 else 'MEDIUM' if pattern['score'] > 0.4 else 'LOW'
            indicators.append({
                'indicator_type': 'PATTERN_ANOMALY',
                'severity': severity,
                'score': pattern['score'],
                'explanation': f"Matches fraud pattern: {pattern['pattern_name']}. {pattern['description']}"
            })
        
        return indicators
```

### 4.3 Frequency Spike Detector

```python
import torch
import torch.nn as nn

class FrequencySpikeModel:
    """
    LSTM Autoencoder for detecting unusual claim frequency patterns.
    Identifies sudden spikes in claim volume.
    """
    
    MODEL_ID = "FRD-FREQ-001"
    
    def __init__(self, model_path: str, config: ModelConfig):
        self.config = config
        self.autoencoder = self._load_autoencoder(model_path)
        self.metadata = self._load_metadata(model_path)
        
        # Reconstruction error thresholds
        self.threshold_high = config.frequency_spike_threshold_high
        self.threshold_medium = config.frequency_spike_threshold_medium
        
        self._validate_model_hash()
    
    def predict(
        self,
        member_time_series: np.ndarray,
        provider_time_series: np.ndarray
    ) -> ModelInferenceResult:
        """
        Detect frequency anomalies in claim time series.
        
        Args:
            member_time_series: Daily claim counts for member (30 days)
            provider_time_series: Daily claim counts for provider (30 days)
        """
        start_time = time.perf_counter()
        
        # Compute reconstruction errors
        member_error = self._compute_reconstruction_error(member_time_series)
        provider_error = self._compute_reconstruction_error(provider_time_series)
        
        # Combined score
        combined_error = (member_error + provider_error) / 2
        risk_score = self._error_to_risk_score(combined_error)
        
        # Identify spike patterns
        member_spikes = self._detect_spikes(member_time_series)
        provider_spikes = self._detect_spikes(provider_time_series)
        
        # Build anomaly indicators
        anomaly_indicators = []
        
        if member_error > self.threshold_medium:
            anomaly_indicators.append({
                'indicator_type': 'FREQUENCY_ANOMALY',
                'severity': 'HIGH' if member_error > self.threshold_high else 'MEDIUM',
                'score': member_error,
                'explanation': f"Member claim frequency pattern is unusual (error: {member_error:.3f})"
            })
        
        if provider_error > self.threshold_medium:
            anomaly_indicators.append({
                'indicator_type': 'FREQUENCY_ANOMALY',
                'severity': 'HIGH' if provider_error > self.threshold_high else 'MEDIUM',
                'score': provider_error,
                'explanation': f"Provider claim frequency pattern is unusual (error: {provider_error:.3f})"
            })
        
        for spike in member_spikes + provider_spikes:
            anomaly_indicators.append(spike)
        
        # Feature contributions
        feature_contributions = [
            {'feature': 'member_reconstruction_error', 'contribution': member_error, 'shap_value': member_error},
            {'feature': 'provider_reconstruction_error', 'contribution': provider_error, 'shap_value': provider_error},
        ]
        
        inference_time = (time.perf_counter() - start_time) * 1000
        
        return ModelInferenceResult(
            model_id=self.MODEL_ID,
            model_version=self.metadata.version,
            model_hash=self.metadata.model_hash,
            risk_score=float(risk_score),
            confidence=float(self._compute_confidence(combined_error)),
            feature_contributions=feature_contributions,
            anomaly_indicators=anomaly_indicators,
            inference_time_ms=inference_time,
            timestamp=datetime.utcnow()
        )
    
    def _compute_reconstruction_error(self, time_series: np.ndarray) -> float:
        """Compute autoencoder reconstruction error."""
        with torch.no_grad():
            input_tensor = torch.FloatTensor(time_series).unsqueeze(0).unsqueeze(-1)
            reconstruction = self.autoencoder(input_tensor)
            error = torch.mean((input_tensor - reconstruction) ** 2).item()
        return error
    
    def _detect_spikes(self, time_series: np.ndarray) -> List[Dict[str, Any]]:
        """Detect significant spikes in time series."""
        spikes = []
        
        # Compute rolling statistics
        window = 7
        rolling_mean = np.convolve(time_series, np.ones(window)/window, mode='valid')
        rolling_std = np.array([np.std(time_series[max(0, i-window):i+1]) 
                                for i in range(len(time_series))])
        
        # Detect spikes (values > 3 std from rolling mean)
        for i in range(window, len(time_series)):
            if rolling_std[i] > 0:
                zscore = (time_series[i] - rolling_mean[i-window]) / rolling_std[i]
                if zscore > 3:
                    spikes.append({
                        'indicator_type': 'TEMPORAL_ANOMALY',
                        'severity': 'HIGH' if zscore > 5 else 'MEDIUM',
                        'score': min(1.0, zscore / 5.0),
                        'explanation': f"Claim spike detected at day {i}: {zscore:.1f} standard deviations above normal"
                    })
        
        return spikes
    
    def _error_to_risk_score(self, error: float) -> float:
        """Convert reconstruction error to risk score."""
        # Sigmoid transformation
        return 1 / (1 + np.exp(-10 * (error - self.threshold_medium)))
```

---

## 5. Model Ensemble & Aggregation

### 5.1 Ensemble Orchestrator

```python
class MLFraudDetectionEngine:
    """
    Orchestrates multiple fraud detection models.
    Aggregates results with confidence-weighted scoring.
    """
    
    def __init__(self, config: MLEngineConfig):
        self.config = config
        self.feature_pipeline = FeaturePipeline(config.feature_config)
        
        # Initialize models
        self.models = {
            'cost_anomaly': CostAnomalyDetector(
                config.cost_model_path, config.cost_model_config
            ),
            'behavioral_fraud': BehavioralFraudModel(
                config.behavioral_model_path, config.behavioral_model_config
            ),
            'provider_abuse': ProviderAbuseDetector(
                config.provider_model_path, config.provider_model_config
            ),
            'frequency_spike': FrequencySpikeModel(
                config.frequency_model_path, config.frequency_model_config
            ),
        }
        
        # Model weights (confidence-adjusted)
        self.base_weights = {
            'cost_anomaly': 0.30,
            'behavioral_fraud': 0.35,
            'provider_abuse': 0.20,
            'frequency_spike': 0.15,
        }
        
        self.engine_version = config.engine_version
    
    def analyze_claim(self, claim_data: ClaimData) -> MLEngineResult:
        """
        Run all fraud detection models on a claim.
        Returns aggregated result with explanations.
        """
        start_time = time.perf_counter()
        
        # Extract features
        features = self.feature_pipeline.extract_features(claim_data)
        
        # Run each model
        model_results = []
        
        # Cost anomaly
        cost_result = self.models['cost_anomaly'].predict(features)
        model_results.append(cost_result)
        
        # Behavioral fraud
        behavioral_result = self.models['behavioral_fraud'].predict(features, claim_data)
        model_results.append(behavioral_result)
        
        # Provider abuse
        provider_result = self.models['provider_abuse'].predict(features, claim_data)
        model_results.append(provider_result)
        
        # Frequency spike (needs time series)
        member_ts = claim_data.member_history.get_daily_claim_counts(days=30)
        provider_ts = claim_data.provider_history.get_daily_claim_counts(days=30)
        frequency_result = self.models['frequency_spike'].predict(member_ts, provider_ts)
        model_results.append(frequency_result)
        
        # Aggregate results
        aggregated = self._aggregate_results(model_results)
        
        execution_time = (time.perf_counter() - start_time) * 1000
        
        return MLEngineResult(
            combined_risk_score=aggregated['risk_score'],
            combined_confidence=aggregated['confidence'],
            model_results=model_results,
            top_risk_factors=aggregated['top_risk_factors'],
            anomaly_summary=aggregated['anomaly_summary'],
            recommendation=aggregated['recommendation'],
            requires_review=aggregated['requires_review'],
            engine_version=self.engine_version,
            execution_time_ms=execution_time,
            timestamp=datetime.utcnow()
        )
    
    def _aggregate_results(
        self,
        model_results: List[ModelInferenceResult]
    ) -> Dict[str, Any]:
        """Aggregate multiple model results."""
        
        # Confidence-weighted score aggregation
        total_weight = 0
        weighted_score = 0
        
        model_map = {
            'FRD-COST-001': 'cost_anomaly',
            'FRD-BEHV-001': 'behavioral_fraud',
            'FRD-PROV-001': 'provider_abuse',
            'FRD-FREQ-001': 'frequency_spike',
        }
        
        for result in model_results:
            model_key = model_map.get(result.model_id)
            if model_key:
                base_weight = self.base_weights[model_key]
                confidence_adjusted_weight = base_weight * result.confidence
                weighted_score += result.risk_score * confidence_adjusted_weight
                total_weight += confidence_adjusted_weight
        
        combined_risk_score = weighted_score / max(total_weight, 0.001)
        
        # Combined confidence (geometric mean)
        confidences = [r.confidence for r in model_results]
        combined_confidence = np.prod(confidences) ** (1/len(confidences))
        
        # Aggregate risk factors
        all_contributions = []
        for result in model_results:
            all_contributions.extend(result.feature_contributions)
        
        # Deduplicate and sort
        feature_scores = {}
        for contrib in all_contributions:
            feature = contrib['feature']
            if feature not in feature_scores:
                feature_scores[feature] = []
            feature_scores[feature].append(contrib['contribution'])
        
        top_risk_factors = [
            {
                'feature': feature,
                'avg_contribution': np.mean(scores),
                'max_contribution': max(scores)
            }
            for feature, scores in feature_scores.items()
        ]
        top_risk_factors.sort(key=lambda x: x['max_contribution'], reverse=True)
        top_risk_factors = top_risk_factors[:10]
        
        # Aggregate anomaly indicators
        all_anomalies = []
        for result in model_results:
            all_anomalies.extend(result.anomaly_indicators)
        
        # Group by type
        anomaly_summary = self._summarize_anomalies(all_anomalies)
        
        # Determine recommendation
        recommendation, requires_review = self._determine_recommendation(
            combined_risk_score,
            combined_confidence,
            all_anomalies
        )
        
        return {
            'risk_score': combined_risk_score,
            'confidence': combined_confidence,
            'top_risk_factors': top_risk_factors,
            'anomaly_summary': anomaly_summary,
            'recommendation': recommendation,
            'requires_review': requires_review
        }
    
    def _determine_recommendation(
        self,
        risk_score: float,
        confidence: float,
        anomalies: List[Dict[str, Any]]
    ) -> tuple:
        """Determine recommendation based on scores."""
        
        # Count high severity anomalies
        high_severity_count = sum(1 for a in anomalies if a['severity'] == 'HIGH')
        critical_count = sum(1 for a in anomalies if a['severity'] == 'CRITICAL')
        
        # Low confidence always requires review
        if confidence < self.config.min_confidence_threshold:
            return 'MEDIUM_RISK', True
        
        # Critical anomalies
        if critical_count > 0:
            return 'HIGH_RISK', True
        
        # Risk score thresholds
        if risk_score >= self.config.high_risk_threshold:
            return 'HIGH_RISK', True
        elif risk_score >= self.config.medium_risk_threshold:
            return 'MEDIUM_RISK', True
        elif risk_score >= self.config.low_risk_threshold or high_severity_count > 0:
            return 'LOW_RISK', high_severity_count > 1
        else:
            return 'MINIMAL_RISK', False
    
    def _summarize_anomalies(
        self,
        anomalies: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Summarize anomalies by type."""
        by_type = {}
        
        for anomaly in anomalies:
            atype = anomaly['indicator_type']
            if atype not in by_type:
                by_type[atype] = {
                    'type': atype,
                    'count': 0,
                    'max_severity': 'LOW',
                    'avg_score': 0,
                    'explanations': []
                }
            
            by_type[atype]['count'] += 1
            by_type[atype]['avg_score'] += anomaly['score']
            by_type[atype]['explanations'].append(anomaly['explanation'])
            
            # Update max severity
            severity_order = {'LOW': 0, 'MEDIUM': 1, 'HIGH': 2, 'CRITICAL': 3}
            if severity_order.get(anomaly['severity'], 0) > severity_order.get(by_type[atype]['max_severity'], 0):
                by_type[atype]['max_severity'] = anomaly['severity']
        
        # Compute averages
        for atype in by_type:
            by_type[atype]['avg_score'] /= by_type[atype]['count']
        
        return list(by_type.values())
```

---

## 6. Model Training & Retraining

### 6.1 Training Pipeline (Offline)

```python
class ModelTrainingPipeline:
    """
    Offline model training pipeline.
    All training requires human review and approval.
    """
    
    def __init__(self, config: TrainingConfig):
        self.config = config
        self.data_store = TrainingDataStore(config.data_store_path)
        self.model_registry = ModelRegistry(config.registry_path)
        self.audit_logger = TrainingAuditLogger()
    
    def train_model(
        self,
        model_type: str,
        training_request: TrainingRequest
    ) -> TrainingResult:
        """
        Train a new model version.
        
        Steps:
        1. Validate training request
        2. Load and validate training data
        3. Train model
        4. Evaluate on holdout set
        5. Generate model artifacts
        6. Submit for approval (NO auto-deployment)
        """
        
        # Step 1: Validate request
        self._validate_training_request(training_request)
        
        # Step 2: Load training data
        training_data, validation_data, test_data = self._load_data(
            training_request
        )
        
        # Log data provenance
        data_hash = self._compute_data_hash(training_data)
        self.audit_logger.log_training_start(
            model_type=model_type,
            request=training_request,
            data_hash=data_hash,
            data_size=len(training_data)
        )
        
        # Step 3: Train model
        if model_type == 'cost_anomaly':
            model, metrics = self._train_cost_anomaly_model(
                training_data, validation_data
            )
        elif model_type == 'behavioral_fraud':
            model, metrics = self._train_behavioral_fraud_model(
                training_data, validation_data
            )
        else:
            raise ValueError(f"Unknown model type: {model_type}")
        
        # Step 4: Evaluate on test set
        test_metrics = self._evaluate_model(model, test_data, model_type)
        
        # Step 5: Generate artifacts
        model_artifact = self._serialize_model(model)
        model_hash = hashlib.sha256(model_artifact).hexdigest()
        
        # Create metadata
        metadata = ModelMetadata(
            model_id=f"FRD-{model_type.upper()[:4]}-001",
            version=self._generate_version(),
            name=f"{model_type} Model",
            description=training_request.description,
            model_type=model_type,
            training_date=datetime.utcnow(),
            training_data_hash=data_hash,
            training_data_size=len(training_data),
            training_parameters=training_request.hyperparameters,
            model_artifact_path="",  # Set after approval
            model_hash=f"sha256:{model_hash}",
            feature_schema_version=self.config.feature_schema_version,
            validation_metrics=metrics,
            test_metrics=test_metrics,
            status=ModelStatus.DEVELOPMENT,
            deployed_at=None,
            deployed_by=None,
            created_by=training_request.requested_by,
            created_at=datetime.utcnow(),
            approved_by=None,
            approved_at=None
        )
        
        # Step 6: Save artifacts (not deployed)
        artifact_path = self._save_artifacts(model_artifact, metadata)
        
        # Log completion
        self.audit_logger.log_training_complete(
            metadata=metadata,
            test_metrics=test_metrics
        )
        
        return TrainingResult(
            metadata=metadata,
            artifact_path=artifact_path,
            test_metrics=test_metrics,
            requires_approval=True,
            approval_instructions=self._generate_approval_instructions(metadata)
        )
    
    def approve_model(
        self,
        model_id: str,
        version: str,
        approver_id: str,
        approval_notes: str
    ) -> ApprovalResult:
        """
        Approve a trained model for deployment.
        Requires explicit human approval.
        """
        # Load model metadata
        metadata = self.model_registry.get_metadata(model_id, version)
        
        if metadata.status != ModelStatus.DEVELOPMENT:
            raise ValueError(f"Model {model_id}:{version} is not awaiting approval")
        
        # Update metadata
        updated_metadata = dataclasses.replace(
            metadata,
            status=ModelStatus.TESTING,
            approved_by=approver_id,
            approved_at=datetime.utcnow()
        )
        
        # Save approval
        self.model_registry.update_metadata(updated_metadata)
        
        # Log approval
        self.audit_logger.log_model_approved(
            model_id=model_id,
            version=version,
            approver_id=approver_id,
            notes=approval_notes
        )
        
        return ApprovalResult(
            model_id=model_id,
            version=version,
            status=ModelStatus.TESTING,
            next_step="Deploy to testing environment for validation"
        )
```

### 6.2 Training Data Management

```python
class TrainingDataStore:
    """
    Manages training data with full provenance tracking.
    Training data comes from admin feedback only.
    """
    
    def __init__(self, store_path: str):
        self.store_path = store_path
        self.db = self._connect_db()
    
    def ingest_feedback(self, feedback: ClaimFeedbackEvent) -> None:
        """
        Ingest feedback from admin review for training.
        Only confirmed outcomes are used for training.
        """
        # Validate feedback
        if not feedback.ground_truth.final_decision:
            raise ValueError("Feedback must have final decision")
        
        # Extract training record
        record = TrainingRecord(
            record_id=str(uuid.uuid4()),
            claim_id=feedback.claim_id,
            features=self._extract_features(feedback.claim_id),
            label=self._compute_label(feedback.ground_truth),
            feedback_type=feedback.feedback_type,
            confidence=feedback.ground_truth.confidence,
            fraud_type=feedback.ground_truth.fraud_type,
            reviewer_id=feedback.reviewer_id,
            ingested_at=datetime.utcnow()
        )
        
        # Store with audit trail
        self._store_record(record)
    
    def get_training_dataset(
        self,
        model_type: str,
        date_range: tuple,
        min_confidence: float = 0.8
    ) -> pd.DataFrame:
        """
        Get training dataset for a model type.
        Filters by confidence threshold.
        """
        query = """
            SELECT * FROM training_records
            WHERE model_type = %s
            AND ingested_at BETWEEN %s AND %s
            AND confidence >= %s
            ORDER BY ingested_at
        """
        
        df = pd.read_sql(
            query,
            self.db,
            params=(model_type, date_range[0], date_range[1], min_confidence)
        )
        
        return df
    
    def _compute_label(self, ground_truth: GroundTruth) -> int:
        """Convert ground truth to training label."""
        if ground_truth.is_fraudulent:
            return 1  # Fraud
        elif ground_truth.final_decision == 'DECLINED':
            return 1  # Treat denials as positive class
        else:
            return 0  # Legitimate
```

---

## 7. Model Monitoring & Drift Detection

### 7.1 Performance Monitoring

```python
class ModelMonitor:
    """
    Monitors model performance in production.
    Detects drift and performance degradation.
    """
    
    def __init__(self, config: MonitorConfig):
        self.config = config
        self.metrics_store = MetricsStore(config.metrics_path)
        self.alert_manager = AlertManager()
    
    def record_prediction(
        self,
        model_id: str,
        prediction: ModelInferenceResult,
        features: np.ndarray
    ) -> None:
        """Record prediction for monitoring."""
        self.metrics_store.record_prediction(
            model_id=model_id,
            risk_score=prediction.risk_score,
            confidence=prediction.confidence,
            feature_hash=self._hash_features(features),
            timestamp=prediction.timestamp
        )
    
    def record_outcome(
        self,
        model_id: str,
        claim_id: str,
        predicted_label: int,
        actual_label: int
    ) -> None:
        """Record actual outcome for accuracy tracking."""
        self.metrics_store.record_outcome(
            model_id=model_id,
            claim_id=claim_id,
            predicted=predicted_label,
            actual=actual_label,
            timestamp=datetime.utcnow()
        )
    
    def check_drift(self, model_id: str) -> DriftReport:
        """Check for feature and prediction drift."""
        # Get recent predictions
        recent = self.metrics_store.get_predictions(
            model_id=model_id,
            days=7
        )
        
        # Get baseline predictions
        baseline = self.metrics_store.get_predictions(
            model_id=model_id,
            days=30,
            offset_days=7
        )
        
        # Statistical tests for drift
        drift_indicators = []
        
        # Risk score distribution drift (KS test)
        ks_stat, p_value = stats.ks_2samp(
            recent['risk_score'],
            baseline['risk_score']
        )
        
        if p_value < 0.05:
            drift_indicators.append({
                'type': 'PREDICTION_DRIFT',
                'metric': 'risk_score_distribution',
                'ks_statistic': ks_stat,
                'p_value': p_value,
                'severity': 'HIGH' if p_value < 0.01 else 'MEDIUM'
            })
        
        # Volume drift
        recent_volume = len(recent)
        baseline_volume = len(baseline) / 4  # Normalize to 7 days
        volume_change = (recent_volume - baseline_volume) / max(baseline_volume, 1)
        
        if abs(volume_change) > 0.3:
            drift_indicators.append({
                'type': 'VOLUME_DRIFT',
                'metric': 'prediction_volume',
                'change_pct': volume_change * 100,
                'severity': 'HIGH' if abs(volume_change) > 0.5 else 'MEDIUM'
            })
        
        # Generate alerts if needed
        if drift_indicators:
            self._generate_drift_alerts(model_id, drift_indicators)
        
        return DriftReport(
            model_id=model_id,
            check_timestamp=datetime.utcnow(),
            drift_detected=len(drift_indicators) > 0,
            indicators=drift_indicators
        )
    
    def get_performance_metrics(self, model_id: str, days: int = 30) -> Dict[str, float]:
        """Calculate performance metrics."""
        outcomes = self.metrics_store.get_outcomes(
            model_id=model_id,
            days=days
        )
        
        if len(outcomes) < 100:
            return {'warning': 'Insufficient data for reliable metrics'}
        
        y_true = outcomes['actual'].values
        y_pred = outcomes['predicted'].values
        
        return {
            'accuracy': accuracy_score(y_true, y_pred),
            'precision': precision_score(y_true, y_pred, zero_division=0),
            'recall': recall_score(y_true, y_pred, zero_division=0),
            'f1': f1_score(y_true, y_pred, zero_division=0),
            'auc_roc': roc_auc_score(y_true, y_pred) if len(set(y_true)) > 1 else 0,
            'sample_size': len(outcomes)
        }
```

---

**END OF ML FRAUD DETECTION SPECIFICATION**


