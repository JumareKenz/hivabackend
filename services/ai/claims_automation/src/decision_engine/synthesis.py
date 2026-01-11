"""
Decision Synthesis Engine
Combines Rule Engine outputs + ML Engine outputs into final claim recommendations

Produces Claim Intelligence Reports with:
- Final recommendation (Auto-Approve / Manual Review / Auto-Decline)
- Confidence score
- Risk assessment
- Queue assignment
- Explicit reasoning
"""

import uuid
import logging
from typing import Optional
from datetime import datetime, timedelta

from ..core.models import (
    ClaimData, RuleEngineResult, MLEngineResult, ClaimIntelligenceReport,
    FinalRecommendation, ReviewQueue, DecisionPriority,
    RuleOutcome, RuleSeverity
)
from ..core.config import settings

logger = logging.getLogger(__name__)


class DecisionSynthesisEngine:
    """
    Synthesize final claim decisions from multiple intelligence sources.
    
    DECISION HIERARCHY:
    1. Critical rule failures → AUTO_DECLINE
    2. Major rule failures → MANUAL_REVIEW (senior queue)
    3. High ML risk + rules OK → MANUAL_REVIEW (fraud queue)
    4. Low risk + rules PASS → AUTO_APPROVE (if enabled)
    5. Everything else → MANUAL_REVIEW (standard queue)
    
    CRITICAL CONSTRAINTS:
    - Auto-approve disabled by default
    - All edge cases default to manual review
    - Low confidence always forces manual review
    - High amounts always trigger review
    """
    
    def __init__(self):
        self.engine_version = settings.DECISION_ENGINE_VERSION
    
    async def synthesize_decision(
        self,
        claim_data: ClaimData,
        rule_result: RuleEngineResult,
        ml_result: Optional[MLEngineResult] = None
    ) -> ClaimIntelligenceReport:
        """
        Generate final claim intelligence report.
        
        Args:
            claim_data: Original claim data
            rule_result: Output from rule engine
            ml_result: Output from ML engine (optional)
            
        Returns:
            Complete claim intelligence report with recommendation
        """
        timestamp = datetime.utcnow()
        analysis_id = f"CIA-{timestamp.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
        
        # Step 1: Analyze rule outcomes
        rule_analysis = self._analyze_rules(rule_result)
        
        # Step 2: Analyze ML risk (if available)
        ml_analysis = self._analyze_ml(ml_result) if ml_result else self._default_ml_analysis()
        
        # Step 3: Synthesize final decision
        final_recommendation, assigned_queue, priority, confidence_score, risk_score = self._make_decision(
            claim_data, rule_analysis, ml_analysis
        )
        
        # Step 4: Generate explanations
        primary_reasons, secondary_factors, risk_indicators = self._build_explanations(
            rule_analysis, ml_analysis, final_recommendation
        )
        
        # Step 5: Suggest actions
        suggested_actions = self._suggest_actions(
            final_recommendation, rule_analysis, ml_analysis, claim_data
        )
        
        # Step 6: Calculate SLA
        sla_hours = self._calculate_sla(priority)
        
        # Build report
        report = ClaimIntelligenceReport(
            analysis_id=analysis_id,
            claim_id=claim_data.claim_id,
            timestamp=timestamp,
            recommendation=final_recommendation,
            confidence_score=confidence_score,
            risk_score=risk_score,
            assigned_queue=assigned_queue,
            priority=priority,
            sla_hours=sla_hours,
            rule_engine_outcome=rule_result.aggregate_outcome.value,
            rule_engine_details={
                'rules_evaluated': rule_result.rules_evaluated,
                'rules_passed': rule_result.rules_passed,
                'rules_failed': rule_result.rules_failed,
                'rules_flagged': rule_result.rules_flagged,
                'triggered_rules': [
                    {
                        'rule_id': r.rule_id,
                        'rule_name': r.rule_name,
                        'outcome': r.outcome.value,
                        'severity': r.severity.value,
                        'message': r.message
                    }
                    for r in rule_result.triggered_rules
                ],
                'execution_time_ms': rule_result.execution_time_ms,
                'ruleset_version': rule_result.ruleset_version
            },
            ml_engine_outcome=ml_analysis['status'],
            ml_engine_details={
                'risk_score': ml_analysis['risk_score'],
                'confidence': ml_analysis['confidence'],
                'top_risk_factors': ml_analysis.get('top_risk_factors', []),
                'recommendation': ml_analysis.get('recommendation', 'N/A')
            },
            primary_reasons=primary_reasons,
            secondary_factors=secondary_factors,
            risk_indicators=risk_indicators,
            suggested_actions=suggested_actions,
            decision_trace={
                'rule_outcome': rule_analysis['outcome'],
                'rule_severity_max': rule_analysis['max_severity'],
                'ml_risk_score': ml_analysis['risk_score'],
                'ml_confidence': ml_analysis['confidence'],
                'auto_approve_enabled': settings.ENABLE_AUTO_APPROVE,
                'auto_decline_enabled': settings.ENABLE_AUTO_DECLINE,
                'high_amount': claim_data.billed_amount > settings.AUTO_APPROVE_MAX_AMOUNT,
                'synthesis_logic': self._get_decision_logic_trace(rule_analysis, ml_analysis)
            },
            processing_time_ms=(rule_result.execution_time_ms + (ml_result.execution_time_ms if ml_result else 0))
        )
        
        logger.info(
            f"Decision synthesized for {claim_data.claim_id}: "
            f"{final_recommendation.value} (confidence: {confidence_score:.2f}, risk: {risk_score:.2f})"
        )
        
        return report
    
    def _analyze_rules(self, rule_result: RuleEngineResult) -> dict:
        """Extract key insights from rule evaluation"""
        
        critical_failures = [r for r in rule_result.triggered_rules if r.severity == RuleSeverity.CRITICAL and r.outcome == RuleOutcome.FAIL]
        major_failures = [r for r in rule_result.triggered_rules if r.severity == RuleSeverity.MAJOR and r.outcome == RuleOutcome.FAIL]
        minor_flags = [r for r in rule_result.triggered_rules if r.severity == RuleSeverity.MINOR]
        
        return {
            'outcome': rule_result.aggregate_outcome.value,
            'critical_failures': len(critical_failures),
            'major_failures': len(major_failures),
            'minor_flags': len(minor_flags),
            'max_severity': self._get_max_severity(rule_result),
            'failed_rules': critical_failures + major_failures,
            'flagged_rules': minor_flags
        }
    
    def _analyze_ml(self, ml_result: MLEngineResult) -> dict:
        """Extract key insights from ML evaluation"""
        return {
            'status': 'available',
            'risk_score': ml_result.combined_risk_score,
            'confidence': ml_result.combined_confidence,
            'recommendation': ml_result.recommendation,
            'top_risk_factors': ml_result.top_risk_factors,
            'requires_review': ml_result.requires_review
        }
    
    def _default_ml_analysis(self) -> dict:
        """Default analysis when ML engine not available"""
        return {
            'status': 'unavailable',
            'risk_score': 0.5,  # Neutral risk
            'confidence': 0.0,  # No confidence
            'recommendation': 'UNKNOWN',
            'top_risk_factors': [],
            'requires_review': True
        }
    
    def _make_decision(
        self,
        claim_data: ClaimData,
        rule_analysis: dict,
        ml_analysis: dict
    ) -> tuple:
        """
        Core decision logic.
        
        Returns: (recommendation, queue, priority, confidence, risk_score)
        """
        
        # LEVEL 1: Critical rule failures → Auto-decline (if enabled)
        if rule_analysis['critical_failures'] > 0:
            if settings.ENABLE_AUTO_DECLINE and settings.AUTO_DECLINE_ON_CRITICAL_RULE:
                return (
                    FinalRecommendation.AUTO_DECLINE,
                    ReviewQueue.COMPLIANCE_REVIEW,
                    DecisionPriority.HIGH,
                    1.0,  # High confidence in decline
                    1.0   # Maximum risk
                )
            else:
                return (
                    FinalRecommendation.MANUAL_REVIEW,
                    ReviewQueue.SENIOR_REVIEW,
                    DecisionPriority.CRITICAL,
                    0.9,
                    0.9
                )
        
        # LEVEL 2: Major rule failures → Senior review
        if rule_analysis['major_failures'] > 0:
            return (
                FinalRecommendation.MANUAL_REVIEW,
                ReviewQueue.SENIOR_REVIEW,
                DecisionPriority.HIGH,
                0.8,
                0.7
            )
        
        # LEVEL 3: High ML risk → Fraud investigation
        if ml_analysis['risk_score'] >= settings.HIGH_RISK_THRESHOLD:
            return (
                FinalRecommendation.MANUAL_REVIEW,
                ReviewQueue.FRAUD_INVESTIGATION,
                DecisionPriority.HIGH,
                ml_analysis['confidence'],
                ml_analysis['risk_score']
            )
        
        # LEVEL 4: Low ML confidence → Manual review
        if ml_analysis['confidence'] < settings.ML_MIN_CONFIDENCE_FOR_AUTO:
            return (
                FinalRecommendation.MANUAL_REVIEW,
                ReviewQueue.STANDARD_REVIEW,
                DecisionPriority.MEDIUM,
                ml_analysis['confidence'],
                ml_analysis['risk_score']
            )
        
        # LEVEL 5: High amount → Always review
        if claim_data.billed_amount > settings.AUTO_APPROVE_MAX_AMOUNT:
            return (
                FinalRecommendation.MANUAL_REVIEW,
                ReviewQueue.SENIOR_REVIEW,
                DecisionPriority.MEDIUM,
                0.7,
                ml_analysis['risk_score']
            )
        
        # LEVEL 6: Minor flags → Standard review
        if rule_analysis['minor_flags'] > 0:
            return (
                FinalRecommendation.MANUAL_REVIEW,
                ReviewQueue.STANDARD_REVIEW,
                DecisionPriority.LOW,
                0.6,
                ml_analysis['risk_score']
            )
        
        # LEVEL 7: Low risk + rules pass → Auto-approve (if enabled)
        if settings.ENABLE_AUTO_APPROVE and ml_analysis['risk_score'] < settings.ML_AUTO_APPROVE_THRESHOLD:
            return (
                FinalRecommendation.AUTO_APPROVE,
                ReviewQueue.AUTO_PROCESS,
                DecisionPriority.LOW,
                ml_analysis['confidence'],
                ml_analysis['risk_score']
            )
        
        # DEFAULT: Manual review (conservative)
        return (
            FinalRecommendation.MANUAL_REVIEW,
            ReviewQueue.STANDARD_REVIEW,
            DecisionPriority.MEDIUM,
            0.5,
            ml_analysis['risk_score']
        )
    
    def _build_explanations(
        self,
        rule_analysis: dict,
        ml_analysis: dict,
        recommendation: FinalRecommendation
    ) -> tuple:
        """Generate human-readable explanations"""
        
        primary_reasons = []
        secondary_factors = []
        risk_indicators = []
        
        # Primary reasons (rules)
        if rule_analysis['critical_failures'] > 0:
            for rule in rule_analysis['failed_rules']:
                if rule.severity == RuleSeverity.CRITICAL:
                    primary_reasons.append(f"CRITICAL FAILURE: {rule.rule_name} - {rule.message}")
        
        if rule_analysis['major_failures'] > 0:
            for rule in rule_analysis['failed_rules']:
                if rule.severity == RuleSeverity.MAJOR:
                    primary_reasons.append(f"Rule violation: {rule.rule_name}")
        
        # Secondary factors (ML)
        if ml_analysis['status'] == 'available':
            if ml_analysis['risk_score'] >= settings.HIGH_RISK_THRESHOLD:
                secondary_factors.append(f"High fraud risk detected ({ml_analysis['risk_score']:.2%})")
            
            for factor in ml_analysis['top_risk_factors'][:5]:
                secondary_factors.append(f"{factor.get('factor', 'Unknown')}: {factor.get('contribution', 0):.2%}")
        
        # Risk indicators
        if rule_analysis['minor_flags'] > 0:
            for rule in rule_analysis['flagged_rules']:
                risk_indicators.append({
                    'type': 'rule_flag',
                    'rule_id': rule.rule_id,
                    'description': rule.message,
                    'severity': rule.severity.value
                })
        
        if not primary_reasons:
            primary_reasons.append("All critical and major rules passed")
        
        return primary_reasons, secondary_factors, risk_indicators
    
    def _suggest_actions(
        self,
        recommendation: FinalRecommendation,
        rule_analysis: dict,
        ml_analysis: dict,
        claim_data: ClaimData
    ) -> list:
        """Suggest reviewer actions"""
        
        actions = []
        
        if recommendation == FinalRecommendation.AUTO_DECLINE:
            actions.append("Review critical rule failures before declining")
            actions.append("Contact member to request corrected claim")
        
        elif recommendation == FinalRecommendation.MANUAL_REVIEW:
            if rule_analysis['critical_failures'] > 0 or rule_analysis['major_failures'] > 0:
                actions.append("Verify rule failure accuracy with source documents")
                actions.append("Check for data entry errors in claim system")
            
            if ml_analysis['risk_score'] >= settings.HIGH_RISK_THRESHOLD:
                actions.append("Investigate provider history for fraud patterns")
                actions.append("Compare with similar claims from same provider")
                actions.append("Verify service was actually rendered")
            
            if claim_data.billed_amount > settings.AUTO_APPROVE_MAX_AMOUNT:
                actions.append("Obtain itemized billing breakdown")
                actions.append("Verify medical necessity with clinical documentation")
        
        else:  # AUTO_APPROVE
            actions.append("No action required - auto-processed")
        
        return actions
    
    def _calculate_sla(self, priority: DecisionPriority) -> int:
        """Calculate SLA hours based on priority"""
        sla_map = {
            DecisionPriority.CRITICAL: settings.SLA_CRITICAL_HOURS if hasattr(settings, 'SLA_CRITICAL_HOURS') else 4,
            DecisionPriority.HIGH: settings.SLA_HIGH_HOURS if hasattr(settings, 'SLA_HIGH_HOURS') else 12,
            DecisionPriority.MEDIUM: settings.SLA_MEDIUM_HOURS if hasattr(settings, 'SLA_MEDIUM_HOURS') else 48,
            DecisionPriority.LOW: settings.SLA_LOW_HOURS if hasattr(settings, 'SLA_LOW_HOURS') else 120,
        }
        return sla_map.get(priority, 48)
    
    def _get_max_severity(self, rule_result: RuleEngineResult) -> str:
        """Get maximum severity from triggered rules"""
        severities = [r.severity for r in rule_result.triggered_rules if r.outcome != RuleOutcome.PASS]
        if not severities:
            return 'NONE'
        
        if RuleSeverity.CRITICAL in severities:
            return 'CRITICAL'
        elif RuleSeverity.MAJOR in severities:
            return 'MAJOR'
        elif RuleSeverity.MINOR in severities:
            return 'MINOR'
        else:
            return 'INFO'
    
    def _get_decision_logic_trace(self, rule_analysis: dict, ml_analysis: dict) -> str:
        """Generate trace of decision logic for audit"""
        if rule_analysis['critical_failures'] > 0:
            return "Critical rule failure(s) detected"
        elif rule_analysis['major_failures'] > 0:
            return "Major rule violation(s) require senior review"
        elif ml_analysis['risk_score'] >= settings.HIGH_RISK_THRESHOLD:
            return "High fraud risk score triggers investigation"
        elif ml_analysis['confidence'] < settings.ML_MIN_CONFIDENCE_FOR_AUTO:
            return "Low ML confidence requires manual review"
        elif rule_analysis['minor_flags'] > 0:
            return "Minor flags present, standard review assigned"
        else:
            return "All checks passed, low risk assessment"


# Global singleton
decision_engine = DecisionSynthesisEngine()


