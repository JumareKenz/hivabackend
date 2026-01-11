"""
Deterministic Rule Engine
Gate 1 of the claims processing pipeline

Applies strict, versioned, rule-based checks that produce
deterministic pass/fail/flag outcomes.
"""

import time
import logging
from typing import Dict, List, Optional
from datetime import datetime

from ..core.models import (
    ClaimData, PolicyData, ProviderData,
    MemberHistory, ProviderHistory,
    RuleDefinition, RuleResult, RuleEngineResult,
    RuleOutcome, RuleCategory, RuleSeverity
)
from ..core.config import settings
from .evaluator import SafeExpressionEvaluator
from .rules_loader import RulesLoader

logger = logging.getLogger(__name__)


class DeterministicRuleEngine:
    """
    Thread-safe, deterministic rule engine.
    Produces identical outputs for identical inputs.
    
    NON-NEGOTIABLE RULES:
    - Rule failures for CRITICAL severity -> AUTO_DECLINE
    - All other failures/flags -> MANUAL_REVIEW
    - Rules NEVER return null/undefined outcomes
    - Every rule execution is logged
    """
    
    def __init__(self):
        self.engine_version = settings.RULE_ENGINE_VERSION
        self.rules_loader = RulesLoader()
        self.evaluator = SafeExpressionEvaluator()
        self.active_ruleset: Dict[str, RuleDefinition] = {}
        self.ruleset_version: str = ""
        self._initialized = False
    
    async def initialize(self):
        """Load and validate ruleset"""
        if self._initialized:
            return
        
        try:
            self.active_ruleset = await self.rules_loader.load_active_ruleset()
            self.ruleset_version = await self.rules_loader.get_active_version()
            
            # Verify checksums
            for rule_id, rule in self.active_ruleset.items():
                if rule.checksum != rule._compute_checksum():
                    raise ValueError(f"Rule {rule_id} checksum mismatch - integrity violation")
            
            logger.info(f"✅ Rule Engine initialized: {len(self.active_ruleset)} rules loaded")
            logger.info(f"   Ruleset version: {self.ruleset_version}")
            self._initialized = True
            
        except Exception as e:
            logger.error(f"Failed to initialize Rule Engine: {e}")
            raise
    
    async def evaluate_claim(
        self,
        claim_data: ClaimData,
        policy_data: Optional[PolicyData] = None,
        provider_data: Optional[ProviderData] = None,
        member_history: Optional[MemberHistory] = None,
        provider_history: Optional[ProviderHistory] = None
    ) -> RuleEngineResult:
        """
        Evaluate all applicable rules against a claim.
        Returns deterministic result with full audit trail.
        
        CRITICAL: This method must be deterministic.
        Same inputs -> Same outputs (always).
        """
        start_time = time.perf_counter()
        timestamp = datetime.utcnow()
        
        # Build evaluation context
        context = self._build_context(
            claim_data, policy_data, provider_data,
            member_history, provider_history
        )
        
        # Get applicable rules in evaluation order
        applicable_rules = self._get_applicable_rules(claim_data)
        
        # Evaluate rules
        results: List[RuleResult] = []
        critical_failure = False
        
        for rule in applicable_rules:
            if critical_failure and rule.category != RuleCategory.CRITICAL:
                # Skip non-critical rules after critical failure
                result = RuleResult(
                    rule_id=rule.rule_id,
                    rule_version=rule.version,
                    rule_name=rule.name,
                    category=rule.category,
                    outcome=RuleOutcome.SKIP,
                    severity=rule.severity,
                    message="Skipped due to prior critical failure",
                    details={},
                    execution_time_ms=0,
                    timestamp=timestamp
                )
            else:
                result = self._evaluate_rule(rule, context, timestamp)
                
                if result.outcome == RuleOutcome.FAIL and rule.severity == RuleSeverity.CRITICAL:
                    critical_failure = True
            
            results.append(result)
        
        # Aggregate results
        execution_time_ms = (time.perf_counter() - start_time) * 1000
        engine_result = self._aggregate_results(results, execution_time_ms, timestamp)
        
        logger.info(f"Rule evaluation complete for {claim_data.claim_id}: {engine_result.aggregate_outcome.value}")
        
        return engine_result
    
    def _evaluate_rule(
        self,
        rule: RuleDefinition,
        context: Dict,
        timestamp: datetime
    ) -> RuleResult:
        """Evaluate a single rule with timeout protection"""
        start_time = time.perf_counter()
        
        try:
            # Evaluate expression with timeout
            outcome_bool = self.evaluator.evaluate(
                expression=rule.condition_expression,
                context=context,
                parameters=rule.parameters,
                timeout_ms=settings.RULE_EVALUATION_TIMEOUT_MS
            )
            
            # Determine outcome
            if outcome_bool:
                outcome = RuleOutcome.PASS
                message = f"✓ {rule.name}"
            else:
                if rule.severity == RuleSeverity.CRITICAL:
                    outcome = RuleOutcome.FAIL
                    message = f"✗ CRITICAL: {rule.name} failed"
                else:
                    outcome = RuleOutcome.FLAG
                    message = f"⚠ {rule.name} flagged for review"
            
            details = {}
            
        except TimeoutError:
            outcome = RuleOutcome.FLAG
            message = f"⚠ Rule evaluation timeout: {rule.name}"
            details = {"error": "timeout", "timeout_ms": settings.RULE_EVALUATION_TIMEOUT_MS}
            logger.warning(f"Rule {rule.rule_id} timed out")
            
        except Exception as e:
            # Rule evaluation errors should flag, not crash
            outcome = RuleOutcome.FLAG
            message = f"⚠ Rule evaluation error: {str(e)}"
            details = {"error": str(e), "error_type": type(e).__name__}
            logger.error(f"Rule {rule.rule_id} error: {e}")
        
        execution_time_ms = (time.perf_counter() - start_time) * 1000
        
        return RuleResult(
            rule_id=rule.rule_id,
            rule_version=rule.version,
            rule_name=rule.name,
            category=rule.category,
            outcome=outcome,
            severity=rule.severity,
            message=message,
            details=details,
            execution_time_ms=execution_time_ms,
            timestamp=timestamp,
            input_snapshot=self._create_snapshot(context, rule.rule_id),
            expression_evaluated=rule.condition_expression,
            parameter_values=rule.parameters
        )
    
    def _build_context(
        self,
        claim_data: ClaimData,
        policy_data: Optional[PolicyData],
        provider_data: Optional[ProviderData],
        member_history: Optional[MemberHistory],
        provider_history: Optional[ProviderHistory]
    ) -> Dict:
        """Build evaluation context for rules"""
        return {
            'claim': claim_data,
            'policy': policy_data,
            'provider': provider_data,
            'member_history': member_history,
            'provider_history': provider_history,
            'today': datetime.utcnow().date(),
            'now': datetime.utcnow()
        }
    
    def _get_applicable_rules(self, claim_data: ClaimData) -> List[RuleDefinition]:
        """Get rules applicable to this claim, in evaluation order"""
        applicable = []
        
        # Define category evaluation order (CRITICAL first)
        category_order = [
            RuleCategory.CRITICAL,
            RuleCategory.POLICY_COVERAGE,
            RuleCategory.PROVIDER_ELIGIBILITY,
            RuleCategory.TARIFF_COMPLIANCE,
            RuleCategory.CODING_VALIDATION,
            RuleCategory.TEMPORAL_VALIDATION,
            RuleCategory.DUPLICATE_DETECTION,
            RuleCategory.BENEFIT_LIMITS,
            RuleCategory.CUSTOM,
        ]
        
        for category in category_order:
            for rule_id, rule in self.active_ruleset.items():
                if rule.category != category:
                    continue
                if not rule.enabled:
                    continue
                if rule.expiration_date and rule.expiration_date < datetime.utcnow():
                    continue
                
                # Check claim type applicability
                if claim_data.claim_type.value not in rule.applies_to_claim_types and 'ALL' not in rule.applies_to_claim_types:
                    continue
                
                applicable.append(rule)
        
        return applicable
    
    def _aggregate_results(
        self,
        results: List[RuleResult],
        execution_time_ms: float,
        timestamp: datetime
    ) -> RuleEngineResult:
        """Aggregate individual rule results into final outcome"""
        
        passed = sum(1 for r in results if r.outcome == RuleOutcome.PASS)
        failed = sum(1 for r in results if r.outcome == RuleOutcome.FAIL)
        flagged = sum(1 for r in results if r.outcome == RuleOutcome.FLAG)
        skipped = sum(1 for r in results if r.outcome == RuleOutcome.SKIP)
        
        # Determine aggregate outcome
        if failed > 0:
            aggregate_outcome = RuleOutcome.FAIL
        elif flagged > 0:
            aggregate_outcome = RuleOutcome.FLAG
        else:
            aggregate_outcome = RuleOutcome.PASS
        
        triggered = [r for r in results if r.outcome in (RuleOutcome.FAIL, RuleOutcome.FLAG)]
        
        return RuleEngineResult(
            aggregate_outcome=aggregate_outcome,
            rules_evaluated=len(results),
            rules_passed=passed,
            rules_failed=failed,
            rules_flagged=flagged,
            rules_skipped=skipped,
            triggered_rules=triggered,
            all_results=results,
            engine_version=self.engine_version,
            ruleset_version=self.ruleset_version,
            execution_time_ms=execution_time_ms,
            timestamp=timestamp
        )
    
    def _create_snapshot(self, context: Dict, rule_id: str) -> Dict:
        """Create input snapshot for audit trail"""
        # Extract relevant fields only (avoid huge snapshots)
        claim = context.get('claim')
        if claim:
            return {
                'claim_id': claim.claim_id,
                'billed_amount': claim.billed_amount,
                'service_date': claim.service_date.isoformat(),
                'procedure_count': len(claim.procedure_codes),
                'diagnosis_count': len(claim.diagnosis_codes)
            }
        return {}


# Global singleton
rule_engine = DeterministicRuleEngine()


