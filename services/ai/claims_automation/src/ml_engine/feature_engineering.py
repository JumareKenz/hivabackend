"""
Feature Engineering Pipeline
Extracts 50+ features from claim data for ML models
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, date
import hashlib

from ..core.models import ClaimData, ProviderHistory, MemberHistory
from ..data.hip_service import hip_service

logger = logging.getLogger(__name__)


class FeatureEngineer:
    """
    Extracts features from claims for ML fraud detection.
    
    Feature Categories:
    1. Claim-level features (15 features)
    2. Provider-level features (12 features)
    3. Member-level features (10 features)
    4. Temporal features (8 features)
    5. Service pattern features (8 features)
    6. Cost-based features (9 features)
    
    Total: 62 features
    """
    
    def __init__(self):
        self.feature_names = self._get_feature_names()
    
    async def extract_features(
        self,
        claim_data: ClaimData,
        provider_history: Optional[ProviderHistory] = None,
        member_history: Optional[MemberHistory] = None
    ) -> Dict[str, float]:
        """
        Extract all features for a claim.
        
        Returns:
            Dictionary of feature_name -> feature_value
        """
        features = {}
        
        # Category 1: Claim-level features
        features.update(self._extract_claim_features(claim_data))
        
        # Category 2: Provider-level features
        if provider_history:
            features.update(self._extract_provider_features(provider_history))
        else:
            features.update(self._get_default_provider_features())
        
        # Category 3: Member-level features
        if member_history:
            features.update(self._extract_member_features(member_history))
        else:
            features.update(self._get_default_member_features())
        
        # Category 4: Temporal features
        features.update(self._extract_temporal_features(claim_data))
        
        # Category 5: Service pattern features
        features.update(self._extract_service_features(claim_data))
        
        # Category 6: Cost-based features
        features.update(await self._extract_cost_features(claim_data))
        
        return features
    
    def _extract_claim_features(self, claim: ClaimData) -> Dict[str, float]:
        """Extract claim-level features"""
        return {
            'claim_amount': float(claim.billed_amount),
            'claim_amount_log': self._safe_log(claim.billed_amount),
            'num_procedures': float(len(claim.procedure_codes)),
            'num_diagnoses': float(len(claim.diagnosis_codes)),
            'is_inpatient': 1.0 if claim.facility_type and 'INPATIENT' in claim.facility_type.value else 0.0,
            'is_emergency': 1.0 if claim.facility_type and 'EMERGENCY' in claim.facility_type.value else 0.0,
            'is_professional': 1.0 if claim.claim_type.value == 'PROFESSIONAL' else 0.0,
            'is_institutional': 1.0 if claim.claim_type.value == 'INSTITUTIONAL' else 0.0,
            'has_prior_auth': 1.0 if claim.prior_auth_number else 0.0,
            'is_out_of_network': 1.0 if claim.network_status.value == 'OUT_OF_NETWORK' else 0.0,
            'has_drg': 1.0 if claim.drg_code else 0.0,
            'has_referring_provider': 1.0 if claim.referring_provider_id else 0.0,
            'service_duration_days': float((claim.service_date_end - claim.service_date).days) if claim.service_date_end else 0.0,
            'avg_procedure_amount': claim.billed_amount / len(claim.procedure_codes) if claim.procedure_codes else 0.0,
            'total_procedure_quantity': float(sum(p.quantity for p in claim.procedure_codes))
        }
    
    def _extract_provider_features(self, history: ProviderHistory) -> Dict[str, float]:
        """Extract provider-level features"""
        return {
            'provider_claims_30d': float(history.claims_30d),
            'provider_claims_90d': float(history.claims_90d),
            'provider_total_billed_30d': float(history.total_billed_30d),
            'provider_avg_claim_amount': float(history.avg_claim_amount),
            'provider_std_claim_amount': float(history.std_claim_amount),
            'provider_unique_members_30d': float(history.unique_members_30d),
            'provider_denial_rate': float(history.denial_rate),
            'provider_fraud_rate': float(history.fraud_rate),
            'provider_peer_percentile': float(history.peer_percentile),
            'provider_claims_per_member': history.claims_30d / max(history.unique_members_30d, 1),
            'provider_avg_per_day': history.claims_30d / 30.0,
            'provider_volume_trend': history.claims_30d / max(history.claims_90d / 3.0, 1.0)
        }
    
    def _extract_member_features(self, history: MemberHistory) -> Dict[str, float]:
        """Extract member-level features"""
        return {
            'member_claims_30d': float(history.claims_30d),
            'member_claims_90d': float(history.claims_90d),
            'member_claims_365d': float(history.claims_365d),
            'member_total_billed_30d': float(history.total_billed_30d),
            'member_total_billed_90d': float(history.total_billed_90d),
            'member_avg_claim_amount': float(history.avg_claim_amount),
            'member_std_claim_amount': float(history.std_claim_amount),
            'member_unique_providers_30d': float(history.unique_providers_30d),
            'member_has_fraud_flag': 1.0 if history.has_fraud_flag else 0.0,
            'member_denial_rate': float(history.denial_rate)
        }
    
    def _extract_temporal_features(self, claim: ClaimData) -> Dict[str, float]:
        """Extract temporal features"""
        today = date.today()
        submission_date = claim.submission_timestamp.date() if claim.submission_timestamp else today
        
        days_since_service = (submission_date - claim.service_date).days
        day_of_week = claim.service_date.weekday()
        month = claim.service_date.month
        
        return {
            'days_since_service': float(days_since_service),
            'days_since_service_log': self._safe_log(days_since_service + 1),
            'is_weekend': 1.0 if day_of_week >= 5 else 0.0,
            'is_monday': 1.0 if day_of_week == 0 else 0.0,
            'is_friday': 1.0 if day_of_week == 4 else 0.0,
            'month': float(month),
            'is_year_end': 1.0 if month == 12 else 0.0,
            'submission_lag_category': self._categorize_lag(days_since_service)
        }
    
    def _extract_service_features(self, claim: ClaimData) -> Dict[str, float]:
        """Extract service pattern features"""
        procedure_codes = [p.code for p in claim.procedure_codes]
        diagnosis_codes = [d.code for d in claim.diagnosis_codes]
        
        # Count unique types
        unique_procedures = len(set(procedure_codes))
        unique_diagnoses = len(set(diagnosis_codes))
        
        return {
            'unique_procedures': float(unique_procedures),
            'unique_diagnoses': float(unique_diagnoses),
            'procedure_diversity': unique_procedures / max(len(procedure_codes), 1),
            'diagnosis_diversity': unique_diagnoses / max(len(diagnosis_codes), 1),
            'has_multiple_procedures': 1.0 if len(procedure_codes) > 1 else 0.0,
            'has_multiple_diagnoses': 1.0 if len(diagnosis_codes) > 1 else 0.0,
            'procedure_diagnosis_ratio': len(procedure_codes) / max(len(diagnosis_codes), 1),
            'has_modifiers': 1.0 if any(p.modifiers for p in claim.procedure_codes) else 0.0
        }
    
    async def _extract_cost_features(self, claim: ClaimData) -> Dict[str, float]:
        """Extract cost-based features"""
        
        # Get procedure statistics from database
        cost_features = {
            'amount_per_procedure': claim.billed_amount / max(len(claim.procedure_codes), 1),
            'amount_per_diagnosis': claim.billed_amount / max(len(claim.diagnosis_codes), 1),
        }
        
        # For each procedure, get expected cost
        if claim.procedure_codes:
            deviations = []
            for proc in claim.procedure_codes:
                try:
                    stats = await hip_service.get_procedure_statistics(proc.code)
                    if stats.get('median', 0) > 0:
                        expected = stats['median']
                        actual = proc.line_amount or 0
                        deviation = (actual - expected) / expected if expected > 0 else 0
                        deviations.append(deviation)
                except Exception:
                    pass
            
            if deviations:
                cost_features['max_cost_deviation'] = max(deviations)
                cost_features['avg_cost_deviation'] = sum(deviations) / len(deviations)
                cost_features['has_high_deviation'] = 1.0 if any(d > 2.0 for d in deviations) else 0.0
            else:
                cost_features['max_cost_deviation'] = 0.0
                cost_features['avg_cost_deviation'] = 0.0
                cost_features['has_high_deviation'] = 0.0
        else:
            cost_features['max_cost_deviation'] = 0.0
            cost_features['avg_cost_deviation'] = 0.0
            cost_features['has_high_deviation'] = 0.0
        
        # Amount categories
        cost_features['is_low_amount'] = 1.0 if claim.billed_amount < 10000 else 0.0
        cost_features['is_medium_amount'] = 1.0 if 10000 <= claim.billed_amount < 100000 else 0.0
        cost_features['is_high_amount'] = 1.0 if 100000 <= claim.billed_amount < 500000 else 0.0
        cost_features['is_very_high_amount'] = 1.0 if claim.billed_amount >= 500000 else 0.0
        
        return cost_features
    
    def _get_default_provider_features(self) -> Dict[str, float]:
        """Default provider features when history unavailable"""
        return {f'provider_{key}': 0.0 for key in [
            'claims_30d', 'claims_90d', 'total_billed_30d', 'avg_claim_amount',
            'std_claim_amount', 'unique_members_30d', 'denial_rate', 'fraud_rate',
            'peer_percentile', 'claims_per_member', 'avg_per_day', 'volume_trend'
        ]}
    
    def _get_default_member_features(self) -> Dict[str, float]:
        """Default member features when history unavailable"""
        return {f'member_{key}': 0.0 for key in [
            'claims_30d', 'claims_90d', 'claims_365d', 'total_billed_30d',
            'total_billed_90d', 'avg_claim_amount', 'std_claim_amount',
            'unique_providers_30d', 'has_fraud_flag', 'denial_rate'
        ]}
    
    @staticmethod
    def _safe_log(value: float) -> float:
        """Safe logarithm (handles zero/negative)"""
        import math
        return math.log(max(value, 0.01))
    
    @staticmethod
    def _categorize_lag(days: int) -> float:
        """Categorize submission lag"""
        if days < 7:
            return 0.0
        elif days < 30:
            return 1.0
        elif days < 90:
            return 2.0
        elif days < 180:
            return 3.0
        else:
            return 4.0
    
    def _get_feature_names(self) -> List[str]:
        """Get all feature names"""
        return [
            # Claim features
            'claim_amount', 'claim_amount_log', 'num_procedures', 'num_diagnoses',
            'is_inpatient', 'is_emergency', 'is_professional', 'is_institutional',
            'has_prior_auth', 'is_out_of_network', 'has_drg', 'has_referring_provider',
            'service_duration_days', 'avg_procedure_amount', 'total_procedure_quantity',
            
            # Provider features
            'provider_claims_30d', 'provider_claims_90d', 'provider_total_billed_30d',
            'provider_avg_claim_amount', 'provider_std_claim_amount', 'provider_unique_members_30d',
            'provider_denial_rate', 'provider_fraud_rate', 'provider_peer_percentile',
            'provider_claims_per_member', 'provider_avg_per_day', 'provider_volume_trend',
            
            # Member features
            'member_claims_30d', 'member_claims_90d', 'member_claims_365d',
            'member_total_billed_30d', 'member_total_billed_90d', 'member_avg_claim_amount',
            'member_std_claim_amount', 'member_unique_providers_30d', 'member_has_fraud_flag',
            'member_denial_rate',
            
            # Temporal features
            'days_since_service', 'days_since_service_log', 'is_weekend', 'is_monday',
            'is_friday', 'month', 'is_year_end', 'submission_lag_category',
            
            # Service features
            'unique_procedures', 'unique_diagnoses', 'procedure_diversity', 'diagnosis_diversity',
            'has_multiple_procedures', 'has_multiple_diagnoses', 'procedure_diagnosis_ratio',
            'has_modifiers',
            
            # Cost features
            'amount_per_procedure', 'amount_per_diagnosis', 'max_cost_deviation',
            'avg_cost_deviation', 'has_high_deviation', 'is_low_amount', 'is_medium_amount',
            'is_high_amount', 'is_very_high_amount'
        ]


# Global singleton
feature_engineer = FeatureEngineer()


