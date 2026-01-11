# Decision Synthesis Engine Specification

**Version:** 1.0.0  
**Date:** January 7, 2026  
**Classification:** CONFIDENTIAL - Technical Specification

---

## 1. Overview

The Decision Synthesis Engine combines outputs from the Deterministic Rule Engine (Gate 1) and ML Fraud Detection Engine (Gate 2) to produce a unified **Claim Intelligence Report**. This report provides an actionable recommendation with full explainability, confidence scoring, and audit trail.

### 1.1 Core Responsibilities

| Responsibility | Description |
|----------------|-------------|
| **Combine Results** | Merge rule and ML outputs with proper precedence |
| **Confidence Scoring** | Calculate overall decision confidence |
| **Recommendation** | Generate APPROVE / REVIEW / DECLINE recommendation |
| **Queue Assignment** | Route to appropriate review queue |
| **Explanation** | Produce human-readable decision explanation |
| **Audit Trail** | Generate complete decision trace |

### 1.2 Decision Hierarchy

```
                         DECISION SYNTHESIS HIERARCHY
    ════════════════════════════════════════════════════════════════

                         ┌─────────────────┐
                         │  RULE ENGINE    │
                         │  OUTPUT         │
                         └────────┬────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    │             │             │
                    ▼             ▼             ▼
              ┌─────────┐   ┌─────────┐   ┌─────────┐
              │  FAIL   │   │  FLAG   │   │  PASS   │
              └────┬────┘   └────┬────┘   └────┬────┘
                   │             │             │
                   │             │             ▼
                   │             │      ┌─────────────┐
                   │             │      │  ML ENGINE  │
                   │             │      │  OUTPUT     │
                   │             │      └──────┬──────┘
                   │             │             │
                   │             │    ┌────────┼────────┐
                   │             │    │        │        │
                   │             │    ▼        ▼        ▼
                   │             │  HIGH    MEDIUM    LOW
                   │             │  RISK    RISK      RISK
                   │             │    │        │        │
                   ▼             ▼    ▼        ▼        ▼
              ┌─────────────────────────────────────────────┐
              │          DECISION SYNTHESIS ENGINE          │
              │                                             │
              │  Precedence Rules:                          │
              │  1. Rule FAIL → AUTO_DECLINE (hard)         │
              │  2. Rule FLAG → MANUAL_REVIEW (always)      │
              │  3. ML HIGH_RISK → MANUAL_REVIEW           │
              │  4. ML MEDIUM_RISK → conditional review     │
              │  5. Rule PASS + ML LOW → AUTO_APPROVE       │
              │                                             │
              └─────────────────────────────────────────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    │             │             │
                    ▼             ▼             ▼
              ┌─────────┐   ┌─────────┐   ┌─────────┐
              │ AUTO    │   │ MANUAL  │   │ AUTO    │
              │ DECLINE │   │ REVIEW  │   │ APPROVE │
              └─────────┘   └─────────┘   └─────────┘

    ════════════════════════════════════════════════════════════════
```

---

## 2. Decision Logic Flow

### 2.1 Complete Decision Flow

```python
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime

class FinalRecommendation(Enum):
    AUTO_APPROVE = "AUTO_APPROVE"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    AUTO_DECLINE = "AUTO_DECLINE"

class ReviewQueue(Enum):
    AUTO_PROCESS = "AUTO_PROCESS"
    STANDARD_REVIEW = "STANDARD_REVIEW"
    SENIOR_REVIEW = "SENIOR_REVIEW"
    FRAUD_INVESTIGATION = "FRAUD_INVESTIGATION"
    MEDICAL_DIRECTOR = "MEDICAL_DIRECTOR"
    COMPLIANCE_REVIEW = "COMPLIANCE_REVIEW"

class DecisionPriority(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

@dataclass
class ClaimIntelligenceReport:
    """Final output of the Decision Synthesis Engine."""
    
    # Identifiers
    analysis_id: str
    claim_id: str
    timestamp: datetime
    
    # Decision
    recommendation: FinalRecommendation
    confidence_score: float  # 0.0 - 1.0
    risk_score: float       # 0.0 - 1.0
    
    # Queue assignment (if review needed)
    assigned_queue: Optional[ReviewQueue]
    priority: DecisionPriority
    sla_hours: int
    
    # Source results
    rule_engine_outcome: str
    rule_engine_details: Dict[str, Any]
    ml_engine_outcome: str
    ml_engine_details: Dict[str, Any]
    
    # Explanations
    primary_reasons: List[str]
    secondary_factors: List[str]
    risk_indicators: List[Dict[str, Any]]
    
    # For reviewers
    suggested_actions: List[str]
    related_claims: List[str]
    historical_context: Dict[str, Any]
    
    # Audit
    decision_trace: Dict[str, Any]
    processing_time_ms: float

class DecisionSynthesisEngine:
    """
    Synthesizes final decision from rule engine and ML engine outputs.
    Produces Claim Intelligence Report with full explainability.
    """
    
    def __init__(self, config: DecisionEngineConfig):
        self.config = config
        
        # Thresholds
        self.auto_approve_ml_threshold = config.auto_approve_ml_threshold  # 0.30
        self.medium_risk_threshold = config.medium_risk_threshold  # 0.50
        self.high_risk_threshold = config.high_risk_threshold  # 0.70
        self.min_confidence_for_auto = config.min_confidence_for_auto  # 0.85
        
        # Amount thresholds
        self.auto_approve_max_amount = config.auto_approve_max_amount
        
        self.engine_version = config.engine_version
    
    def synthesize_decision(
        self,
        claim_data: ClaimData,
        rule_result: RuleEngineResult,
        ml_result: MLEngineResult
    ) -> ClaimIntelligenceReport:
        """
        Synthesize final decision from gate outputs.
        """
        start_time = time.perf_counter()
        analysis_id = str(uuid.uuid4())
        timestamp = datetime.utcnow()
        
        # Initialize decision trace
        trace = DecisionTrace(analysis_id, timestamp)
        trace.add_stage("SYNTHESIS_START")
        
        # Step 1: Check rule engine outcome (highest precedence)
        recommendation, queue, priority = self._apply_rule_precedence(
            rule_result, trace
        )
        
        # Step 2: If not decided by rules, apply ML-based decision
        if recommendation is None:
            recommendation, queue, priority = self._apply_ml_decision(
                ml_result, claim_data, trace
            )
        
        # Step 3: Apply confidence check
        recommendation, queue = self._apply_confidence_gate(
            recommendation, queue, rule_result, ml_result, trace
        )
        
        # Step 4: Apply amount-based guardrails
        recommendation, queue = self._apply_amount_guardrails(
            recommendation, queue, claim_data, trace
        )
        
        # Step 5: Calculate final scores
        confidence_score = self._calculate_confidence_score(rule_result, ml_result)
        risk_score = self._calculate_risk_score(rule_result, ml_result)
        
        # Step 6: Determine SLA
        sla_hours = self._determine_sla(priority, queue)
        
        # Step 7: Generate explanations
        reasons = self._generate_reasons(rule_result, ml_result, recommendation)
        secondary = self._generate_secondary_factors(rule_result, ml_result)
        risk_indicators = self._extract_risk_indicators(rule_result, ml_result)
        
        # Step 8: Generate reviewer guidance
        suggested_actions = self._generate_suggested_actions(
            recommendation, rule_result, ml_result
        )
        related_claims = self._find_related_claims(claim_data)
        historical_context = self._build_historical_context(claim_data)
        
        # Finalize trace
        trace.add_stage("SYNTHESIS_COMPLETE", {
            'recommendation': recommendation.value,
            'queue': queue.value if queue else None,
            'confidence': confidence_score,
            'risk': risk_score
        })
        
        processing_time = (time.perf_counter() - start_time) * 1000
        
        return ClaimIntelligenceReport(
            analysis_id=analysis_id,
            claim_id=claim_data.claim.claim_id,
            timestamp=timestamp,
            recommendation=recommendation,
            confidence_score=confidence_score,
            risk_score=risk_score,
            assigned_queue=queue,
            priority=priority,
            sla_hours=sla_hours,
            rule_engine_outcome=rule_result.aggregate_outcome.value,
            rule_engine_details=self._summarize_rule_result(rule_result),
            ml_engine_outcome=ml_result.recommendation,
            ml_engine_details=self._summarize_ml_result(ml_result),
            primary_reasons=reasons['primary'],
            secondary_factors=secondary,
            risk_indicators=risk_indicators,
            suggested_actions=suggested_actions,
            related_claims=related_claims,
            historical_context=historical_context,
            decision_trace=trace.to_dict(),
            processing_time_ms=processing_time
        )
    
    def _apply_rule_precedence(
        self,
        rule_result: RuleEngineResult,
        trace: DecisionTrace
    ) -> tuple:
        """
        Apply rule engine precedence.
        Rule failures take absolute precedence.
        """
        trace.add_stage("RULE_PRECEDENCE_CHECK")
        
        # FAIL: Hard decline
        if rule_result.aggregate_outcome == RuleOutcome.FAIL:
            trace.add_decision(
                "RULE_HARD_FAIL",
                f"Critical rule failure(s) detected: {len(rule_result.rules_failed)} rule(s) failed"
            )
            
            # Determine queue based on failure type
            if self._is_fraud_related_failure(rule_result):
                queue = ReviewQueue.FRAUD_INVESTIGATION
                priority = DecisionPriority.CRITICAL
            else:
                queue = ReviewQueue.STANDARD_REVIEW
                priority = DecisionPriority.HIGH
            
            return FinalRecommendation.AUTO_DECLINE, queue, priority
        
        # FLAG: Force manual review
        if rule_result.aggregate_outcome == RuleOutcome.FLAG:
            flagged_rules = [r for r in rule_result.triggered_rules 
                           if r.outcome == RuleOutcome.FLAG]
            
            trace.add_decision(
                "RULE_FLAG",
                f"Rule flag(s) detected: {len(flagged_rules)} rule(s) flagged"
            )
            
            # Determine queue based on flag severity
            queue, priority = self._determine_flag_queue(flagged_rules)
            
            return FinalRecommendation.MANUAL_REVIEW, queue, priority
        
        # PASS: Rules passed, continue to ML decision
        trace.add_decision("RULE_PASS", "All rules passed, proceeding to ML evaluation")
        return None, None, None
    
    def _apply_ml_decision(
        self,
        ml_result: MLEngineResult,
        claim_data: ClaimData,
        trace: DecisionTrace
    ) -> tuple:
        """
        Apply ML-based decision logic.
        Only called when rules pass.
        """
        trace.add_stage("ML_DECISION", {
            'risk_score': ml_result.combined_risk_score,
            'confidence': ml_result.combined_confidence,
            'recommendation': ml_result.recommendation
        })
        
        risk_score = ml_result.combined_risk_score
        confidence = ml_result.combined_confidence
        
        # HIGH RISK: Fraud investigation
        if risk_score >= self.high_risk_threshold:
            trace.add_decision(
                "ML_HIGH_RISK",
                f"Risk score {risk_score:.2f} >= high threshold {self.high_risk_threshold}"
            )
            return (
                FinalRecommendation.MANUAL_REVIEW,
                ReviewQueue.FRAUD_INVESTIGATION,
                DecisionPriority.HIGH
            )
        
        # MEDIUM RISK: Senior review
        if risk_score >= self.medium_risk_threshold:
            trace.add_decision(
                "ML_MEDIUM_RISK",
                f"Risk score {risk_score:.2f} >= medium threshold {self.medium_risk_threshold}"
            )
            return (
                FinalRecommendation.MANUAL_REVIEW,
                ReviewQueue.SENIOR_REVIEW,
                DecisionPriority.MEDIUM
            )
        
        # LOW RISK with flags: Standard review
        if risk_score >= self.auto_approve_ml_threshold or ml_result.requires_review:
            trace.add_decision(
                "ML_LOW_RISK_FLAG",
                f"Risk score {risk_score:.2f} or ML requires review"
            )
            return (
                FinalRecommendation.MANUAL_REVIEW,
                ReviewQueue.STANDARD_REVIEW,
                DecisionPriority.LOW
            )
        
        # MINIMAL RISK: Auto approve candidate
        trace.add_decision(
            "ML_MINIMAL_RISK",
            f"Risk score {risk_score:.2f} < auto-approve threshold {self.auto_approve_ml_threshold}"
        )
        return (
            FinalRecommendation.AUTO_APPROVE,
            ReviewQueue.AUTO_PROCESS,
            DecisionPriority.LOW
        )
    
    def _apply_confidence_gate(
        self,
        recommendation: FinalRecommendation,
        queue: ReviewQueue,
        rule_result: RuleEngineResult,
        ml_result: MLEngineResult,
        trace: DecisionTrace
    ) -> tuple:
        """
        Apply confidence-based safety gate.
        Low confidence forces manual review.
        """
        trace.add_stage("CONFIDENCE_GATE")
        
        # Only apply to auto decisions
        if recommendation not in (FinalRecommendation.AUTO_APPROVE, FinalRecommendation.AUTO_DECLINE):
            return recommendation, queue
        
        combined_confidence = self._calculate_confidence_score(rule_result, ml_result)
        
        if combined_confidence < self.min_confidence_for_auto:
            trace.add_decision(
                "CONFIDENCE_OVERRIDE",
                f"Confidence {combined_confidence:.2f} < threshold {self.min_confidence_for_auto}, forcing review"
            )
            
            # Convert to manual review
            if recommendation == FinalRecommendation.AUTO_APPROVE:
                return FinalRecommendation.MANUAL_REVIEW, ReviewQueue.STANDARD_REVIEW
            else:
                return FinalRecommendation.MANUAL_REVIEW, ReviewQueue.SENIOR_REVIEW
        
        trace.add_decision(
            "CONFIDENCE_PASS",
            f"Confidence {combined_confidence:.2f} >= threshold {self.min_confidence_for_auto}"
        )
        return recommendation, queue
    
    def _apply_amount_guardrails(
        self,
        recommendation: FinalRecommendation,
        queue: ReviewQueue,
        claim_data: ClaimData,
        trace: DecisionTrace
    ) -> tuple:
        """
        Apply amount-based guardrails.
        High-value claims require review regardless of ML score.
        """
        trace.add_stage("AMOUNT_GUARDRAILS")
        
        amount = claim_data.claim.billed_amount
        
        # Only apply to auto-approve
        if recommendation != FinalRecommendation.AUTO_APPROVE:
            return recommendation, queue
        
        if amount > self.auto_approve_max_amount:
            trace.add_decision(
                "AMOUNT_OVERRIDE",
                f"Amount {amount} > auto-approve limit {self.auto_approve_max_amount}"
            )
            return FinalRecommendation.MANUAL_REVIEW, ReviewQueue.SENIOR_REVIEW
        
        trace.add_decision(
            "AMOUNT_PASS",
            f"Amount {amount} <= auto-approve limit {self.auto_approve_max_amount}"
        )
        return recommendation, queue
    
    def _calculate_confidence_score(
        self,
        rule_result: RuleEngineResult,
        ml_result: MLEngineResult
    ) -> float:
        """
        Calculate overall confidence score.
        Combines rule certainty and ML confidence.
        """
        # Rule engine is deterministic, so confidence is 1.0 or based on coverage
        rule_confidence = 1.0 if rule_result.rules_skipped == 0 else 0.9
        
        # ML confidence
        ml_confidence = ml_result.combined_confidence
        
        # Combined (geometric mean)
        combined = (rule_confidence * ml_confidence) ** 0.5
        
        return combined
    
    def _calculate_risk_score(
        self,
        rule_result: RuleEngineResult,
        ml_result: MLEngineResult
    ) -> float:
        """
        Calculate overall risk score.
        """
        # Rule risk contribution
        rule_risk = 0.0
        if rule_result.aggregate_outcome == RuleOutcome.FAIL:
            rule_risk = 1.0
        elif rule_result.aggregate_outcome == RuleOutcome.FLAG:
            # Weight by flag severity
            flag_weights = {
                RuleSeverity.CRITICAL: 1.0,
                RuleSeverity.MAJOR: 0.7,
                RuleSeverity.MINOR: 0.4,
                RuleSeverity.INFO: 0.1
            }
            triggered = rule_result.triggered_rules
            if triggered:
                rule_risk = max(flag_weights.get(r.severity, 0.5) for r in triggered)
        
        # ML risk
        ml_risk = ml_result.combined_risk_score
        
        # Combined risk (max of either source, weighted)
        combined = max(rule_risk * 0.6, ml_risk) if rule_risk > 0 else ml_risk
        
        return min(1.0, combined)
    
    def _generate_reasons(
        self,
        rule_result: RuleEngineResult,
        ml_result: MLEngineResult,
        recommendation: FinalRecommendation
    ) -> Dict[str, List[str]]:
        """Generate human-readable primary reasons."""
        primary = []
        
        # Rule-based reasons
        for rule in rule_result.triggered_rules:
            if rule.outcome in (RuleOutcome.FAIL, RuleOutcome.FLAG):
                primary.append(f"[{rule.rule_id}] {rule.message}")
        
        # ML-based reasons (top risk factors)
        for factor in ml_result.top_risk_factors[:3]:
            primary.append(
                f"ML Risk Factor: {factor['feature']} (contribution: {factor['avg_contribution']:.2f})"
            )
        
        # Add recommendation-specific summary
        if recommendation == FinalRecommendation.AUTO_APPROVE:
            primary.insert(0, "All validation checks passed with high confidence")
        elif recommendation == FinalRecommendation.AUTO_DECLINE:
            primary.insert(0, "Critical rule violation(s) detected")
        else:
            primary.insert(0, "Claim requires human review due to identified risk factors")
        
        return {'primary': primary}
    
    def _generate_secondary_factors(
        self,
        rule_result: RuleEngineResult,
        ml_result: MLEngineResult
    ) -> List[str]:
        """Generate secondary contributing factors."""
        secondary = []
        
        # Lower-priority rule results
        for rule in rule_result.all_results:
            if rule.outcome == RuleOutcome.PASS and rule.severity != RuleSeverity.INFO:
                secondary.append(f"[{rule.rule_id}] Passed: {rule.rule_name}")
        
        # Anomaly indicators
        for anomaly in ml_result.anomaly_summary:
            secondary.append(
                f"{anomaly['type']}: {anomaly['count']} indicator(s), max severity: {anomaly['max_severity']}"
            )
        
        return secondary[:10]  # Limit to 10
    
    def _extract_risk_indicators(
        self,
        rule_result: RuleEngineResult,
        ml_result: MLEngineResult
    ) -> List[Dict[str, Any]]:
        """Extract all risk indicators for display."""
        indicators = []
        
        # From rules
        for rule in rule_result.triggered_rules:
            indicators.append({
                'source': 'RULE_ENGINE',
                'type': rule.category.value,
                'severity': rule.severity.value,
                'indicator': rule.rule_id,
                'message': rule.message,
                'details': rule.details
            })
        
        # From ML
        for model_result in ml_result.model_results:
            for anomaly in model_result.anomaly_indicators:
                indicators.append({
                    'source': 'ML_ENGINE',
                    'type': anomaly['indicator_type'],
                    'severity': anomaly['severity'],
                    'indicator': model_result.model_id,
                    'message': anomaly['explanation'],
                    'score': anomaly['score']
                })
        
        # Sort by severity
        severity_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
        indicators.sort(key=lambda x: severity_order.get(x['severity'], 4))
        
        return indicators
    
    def _generate_suggested_actions(
        self,
        recommendation: FinalRecommendation,
        rule_result: RuleEngineResult,
        ml_result: MLEngineResult
    ) -> List[str]:
        """Generate suggested actions for reviewers."""
        actions = []
        
        if recommendation == FinalRecommendation.MANUAL_REVIEW:
            # Generic review actions
            actions.append("Review all flagged risk indicators")
            actions.append("Verify member eligibility status")
            actions.append("Check provider credentials and history")
            
            # Specific actions based on flags
            for rule in rule_result.triggered_rules:
                if 'DUPLICATE' in rule.rule_id:
                    actions.append("Check for potential duplicate claims")
                elif 'TARIFF' in rule.rule_id:
                    actions.append("Verify billed amounts against fee schedule")
                elif 'CODING' in rule.rule_id:
                    actions.append("Review diagnosis/procedure code compatibility")
            
            # ML-based suggestions
            if ml_result.combined_risk_score > 0.7:
                actions.append("Consider escalating to fraud investigation")
            
        elif recommendation == FinalRecommendation.AUTO_DECLINE:
            actions.append("Verify decline reason with policy documentation")
            actions.append("Ensure proper denial code is applied")
            actions.append("Prepare member notification")
        
        return actions[:8]  # Limit
    
    def _determine_flag_queue(
        self,
        flagged_rules: List[RuleResult]
    ) -> tuple:
        """Determine queue based on flagged rules."""
        # Count severities
        severities = [r.severity for r in flagged_rules]
        
        if RuleSeverity.CRITICAL in severities:
            return ReviewQueue.FRAUD_INVESTIGATION, DecisionPriority.CRITICAL
        
        major_count = severities.count(RuleSeverity.MAJOR)
        
        if major_count >= 2:
            return ReviewQueue.SENIOR_REVIEW, DecisionPriority.HIGH
        elif major_count == 1:
            return ReviewQueue.SENIOR_REVIEW, DecisionPriority.MEDIUM
        else:
            return ReviewQueue.STANDARD_REVIEW, DecisionPriority.LOW
    
    def _determine_sla(
        self,
        priority: DecisionPriority,
        queue: ReviewQueue
    ) -> int:
        """Determine SLA hours based on priority and queue."""
        sla_matrix = {
            DecisionPriority.CRITICAL: {
                ReviewQueue.FRAUD_INVESTIGATION: 4,
                ReviewQueue.MEDICAL_DIRECTOR: 8,
                ReviewQueue.COMPLIANCE_REVIEW: 8,
                ReviewQueue.SENIOR_REVIEW: 12,
                ReviewQueue.STANDARD_REVIEW: 24
            },
            DecisionPriority.HIGH: {
                ReviewQueue.FRAUD_INVESTIGATION: 8,
                ReviewQueue.MEDICAL_DIRECTOR: 24,
                ReviewQueue.COMPLIANCE_REVIEW: 24,
                ReviewQueue.SENIOR_REVIEW: 24,
                ReviewQueue.STANDARD_REVIEW: 48
            },
            DecisionPriority.MEDIUM: {
                ReviewQueue.FRAUD_INVESTIGATION: 24,
                ReviewQueue.MEDICAL_DIRECTOR: 48,
                ReviewQueue.COMPLIANCE_REVIEW: 48,
                ReviewQueue.SENIOR_REVIEW: 48,
                ReviewQueue.STANDARD_REVIEW: 72
            },
            DecisionPriority.LOW: {
                ReviewQueue.FRAUD_INVESTIGATION: 48,
                ReviewQueue.MEDICAL_DIRECTOR: 72,
                ReviewQueue.COMPLIANCE_REVIEW: 72,
                ReviewQueue.SENIOR_REVIEW: 72,
                ReviewQueue.STANDARD_REVIEW: 120
            }
        }
        
        return sla_matrix.get(priority, {}).get(queue, 72)
```

---

## 3. Decision Trace & Audit Trail

### 3.1 Decision Trace Structure

```python
class DecisionTrace:
    """
    Records complete decision-making trace for audit.
    Immutable after creation.
    """
    
    def __init__(self, analysis_id: str, timestamp: datetime):
        self.analysis_id = analysis_id
        self.start_timestamp = timestamp
        self._stages: List[Dict[str, Any]] = []
        self._decisions: List[Dict[str, Any]] = []
        self._locked = False
    
    def add_stage(self, stage_name: str, details: Dict[str, Any] = None) -> None:
        """Add a processing stage to trace."""
        if self._locked:
            raise ValueError("Cannot modify locked trace")
        
        self._stages.append({
            'stage': stage_name,
            'timestamp': datetime.utcnow().isoformat(),
            'details': details or {}
        })
    
    def add_decision(self, decision_type: str, reason: str, details: Dict[str, Any] = None) -> None:
        """Add a decision point to trace."""
        if self._locked:
            raise ValueError("Cannot modify locked trace")
        
        self._decisions.append({
            'type': decision_type,
            'reason': reason,
            'timestamp': datetime.utcnow().isoformat(),
            'details': details or {}
        })
    
    def lock(self) -> None:
        """Lock trace from further modifications."""
        self._locked = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert trace to dictionary for storage."""
        self.lock()
        
        return {
            'analysis_id': self.analysis_id,
            'trace_version': '1.0.0',
            'start_timestamp': self.start_timestamp.isoformat(),
            'end_timestamp': datetime.utcnow().isoformat(),
            'stages': self._stages,
            'decisions': self._decisions,
            'integrity_hash': self._compute_hash()
        }
    
    def _compute_hash(self) -> str:
        """Compute integrity hash of trace."""
        content = json.dumps({
            'analysis_id': self.analysis_id,
            'stages': self._stages,
            'decisions': self._decisions
        }, sort_keys=True)
        return f"sha256:{hashlib.sha256(content.encode()).hexdigest()}"
```

### 3.2 Audit Storage

```python
class DecisionAuditStore:
    """
    Immutable storage for decision audit records.
    Append-only with cryptographic chaining.
    """
    
    def __init__(self, db_config: DatabaseConfig):
        self.db = self._connect_db(db_config)
        self.last_hash = self._get_last_hash()
    
    def store_decision(self, report: ClaimIntelligenceReport) -> str:
        """
        Store decision with integrity chain.
        Returns audit record ID.
        """
        record_id = str(uuid.uuid4())
        
        # Create audit record
        audit_record = {
            'record_id': record_id,
            'analysis_id': report.analysis_id,
            'claim_id': report.claim_id,
            'timestamp': report.timestamp.isoformat(),
            'recommendation': report.recommendation.value,
            'confidence_score': report.confidence_score,
            'risk_score': report.risk_score,
            'assigned_queue': report.assigned_queue.value if report.assigned_queue else None,
            'priority': report.priority.value,
            'rule_outcome': report.rule_engine_outcome,
            'ml_outcome': report.ml_engine_outcome,
            'primary_reasons': report.primary_reasons,
            'risk_indicators': report.risk_indicators,
            'decision_trace': report.decision_trace,
            'processing_time_ms': report.processing_time_ms
        }
        
        # Compute integrity hash
        content_hash = self._compute_content_hash(audit_record)
        chain_hash = self._compute_chain_hash(content_hash, self.last_hash)
        
        audit_record['content_hash'] = content_hash
        audit_record['previous_hash'] = self.last_hash
        audit_record['chain_hash'] = chain_hash
        
        # Store atomically
        self._insert_record(audit_record)
        self.last_hash = chain_hash
        
        return record_id
    
    def verify_chain_integrity(self, start_record: str = None) -> IntegrityReport:
        """Verify integrity of audit chain."""
        records = self._get_records_from(start_record)
        
        broken_links = []
        previous_hash = records[0]['previous_hash'] if records else None
        
        for record in records:
            # Verify content hash
            computed_content = self._compute_content_hash(record)
            if computed_content != record['content_hash']:
                broken_links.append({
                    'record_id': record['record_id'],
                    'error': 'Content hash mismatch',
                    'expected': record['content_hash'],
                    'computed': computed_content
                })
            
            # Verify chain
            if record['previous_hash'] != previous_hash:
                broken_links.append({
                    'record_id': record['record_id'],
                    'error': 'Chain broken',
                    'expected_previous': previous_hash,
                    'actual_previous': record['previous_hash']
                })
            
            previous_hash = record['chain_hash']
        
        return IntegrityReport(
            verified_records=len(records),
            broken_links=broken_links,
            chain_valid=len(broken_links) == 0,
            verification_timestamp=datetime.utcnow()
        )
```

---

## 4. Queue Routing Logic

### 4.1 Queue Assignment Matrix

```python
class QueueRouter:
    """
    Routes claims to appropriate review queues.
    Based on risk profile, amount, and claim type.
    """
    
    def __init__(self, config: QueueConfig):
        self.config = config
        self.queue_capacity = config.queue_capacity
    
    def assign_queue(
        self,
        recommendation: FinalRecommendation,
        rule_result: RuleEngineResult,
        ml_result: MLEngineResult,
        claim_data: ClaimData
    ) -> tuple:
        """
        Assign claim to appropriate queue.
        Returns (queue, priority, sla_hours).
        """
        
        # Auto decisions don't need queue
        if recommendation == FinalRecommendation.AUTO_APPROVE:
            return ReviewQueue.AUTO_PROCESS, DecisionPriority.LOW, 0
        
        if recommendation == FinalRecommendation.AUTO_DECLINE:
            # Even auto-declines need audit trail in a queue
            return ReviewQueue.AUTO_PROCESS, DecisionPriority.LOW, 0
        
        # Determine queue based on multiple factors
        queue = self._determine_primary_queue(rule_result, ml_result, claim_data)
        
        # Adjust based on capacity
        queue = self._apply_capacity_routing(queue)
        
        # Determine priority
        priority = self._determine_priority(rule_result, ml_result, claim_data)
        
        # Calculate SLA
        sla = self._calculate_sla(queue, priority)
        
        return queue, priority, sla
    
    def _determine_primary_queue(
        self,
        rule_result: RuleEngineResult,
        ml_result: MLEngineResult,
        claim_data: ClaimData
    ) -> ReviewQueue:
        """Determine primary queue based on claim characteristics."""
        
        # Check for fraud indicators
        fraud_rules = [r for r in rule_result.triggered_rules 
                       if 'FRAUD' in r.rule_id or 'DUP' in r.rule_id]
        fraud_ml = ml_result.combined_risk_score >= 0.7
        
        if fraud_rules or fraud_ml:
            return ReviewQueue.FRAUD_INVESTIGATION
        
        # Check for medical necessity
        medical_rules = [r for r in rule_result.triggered_rules
                        if 'MEDICAL' in r.rule_id or 'CODING' in r.rule_id]
        
        if medical_rules and claim_data.claim.billed_amount > 50000:
            return ReviewQueue.MEDICAL_DIRECTOR
        
        # Check for compliance issues
        compliance_rules = [r for r in rule_result.triggered_rules
                          if 'COMPLIANCE' in r.rule_id or 'POLICY' in r.rule_id]
        
        if compliance_rules:
            return ReviewQueue.COMPLIANCE_REVIEW
        
        # High value claims
        if claim_data.claim.billed_amount > self.config.senior_review_amount_threshold:
            return ReviewQueue.SENIOR_REVIEW
        
        # Multiple flags
        if len(rule_result.triggered_rules) >= 3:
            return ReviewQueue.SENIOR_REVIEW
        
        return ReviewQueue.STANDARD_REVIEW
    
    def _apply_capacity_routing(self, queue: ReviewQueue) -> ReviewQueue:
        """Apply capacity-based load balancing."""
        current_depth = self._get_queue_depth(queue)
        max_depth = self.queue_capacity.get(queue.value, 1000)
        
        if current_depth >= max_depth * 0.9:
            # Queue near capacity, escalate
            escalation_map = {
                ReviewQueue.STANDARD_REVIEW: ReviewQueue.SENIOR_REVIEW,
                ReviewQueue.SENIOR_REVIEW: ReviewQueue.SENIOR_REVIEW,  # No change
                ReviewQueue.FRAUD_INVESTIGATION: ReviewQueue.FRAUD_INVESTIGATION,
                ReviewQueue.MEDICAL_DIRECTOR: ReviewQueue.MEDICAL_DIRECTOR,
                ReviewQueue.COMPLIANCE_REVIEW: ReviewQueue.COMPLIANCE_REVIEW,
            }
            return escalation_map.get(queue, queue)
        
        return queue
```

---

## 5. Claim Intelligence Report Output

### 5.1 Report Format (JSON)

```json
{
  "analysis_id": "550e8400-e29b-41d4-a716-446655440000",
  "claim_id": "CLM-2026-000123456",
  "timestamp": "2026-01-07T14:30:00.000Z",
  
  "recommendation": "MANUAL_REVIEW",
  "confidence_score": 0.78,
  "risk_score": 0.65,
  
  "assigned_queue": "SENIOR_REVIEW",
  "priority": "MEDIUM",
  "sla_hours": 48,
  
  "rule_engine_outcome": "FLAG",
  "rule_engine_details": {
    "rules_evaluated": 47,
    "rules_passed": 44,
    "rules_flagged": 3,
    "rules_failed": 0,
    "engine_version": "2.3.1",
    "ruleset_version": "2026.01.15"
  },
  
  "ml_engine_outcome": "MEDIUM_RISK",
  "ml_engine_details": {
    "combined_risk_score": 0.58,
    "combined_confidence": 0.82,
    "models_executed": 4,
    "engine_version": "1.2.0"
  },
  
  "primary_reasons": [
    "Claim requires human review due to identified risk factors",
    "[TAR-004] Billed amount exceeds 95th percentile for procedure code 99213",
    "[DUP-002] Possible duplicate claim detected on same service date",
    "ML Risk Factor: provider_claim_amount_zscore (contribution: 0.34)"
  ],
  
  "secondary_factors": [
    "[POL-001] Passed: Policy Active Status",
    "[PRV-001] Passed: Provider Active Status",
    "COST_ANOMALY: 1 indicator(s), max severity: MEDIUM"
  ],
  
  "risk_indicators": [
    {
      "source": "RULE_ENGINE",
      "type": "TARIFF_COMPLIANCE",
      "severity": "MINOR",
      "indicator": "TAR-004",
      "message": "Billed amount $1,850 exceeds 95th percentile ($1,200) for procedure 99213",
      "details": {
        "billed_amount": 1850,
        "percentile_95": 1200,
        "ratio": 1.54
      }
    },
    {
      "source": "RULE_ENGINE",
      "type": "DUPLICATE_DETECTION",
      "severity": "MINOR",
      "indicator": "DUP-002",
      "message": "Similar claim found on same service date",
      "details": {
        "similar_claim_id": "CLM-2026-000123400",
        "similarity_score": 0.85
      }
    },
    {
      "source": "ML_ENGINE",
      "type": "COST_ANOMALY",
      "severity": "MEDIUM",
      "indicator": "FRD-COST-001",
      "message": "Claim amount is 2.3 standard deviations above provider's average",
      "score": 0.67
    }
  ],
  
  "suggested_actions": [
    "Review all flagged risk indicators",
    "Verify billed amounts against fee schedule",
    "Check for potential duplicate claims",
    "Verify member eligibility status"
  ],
  
  "related_claims": [
    "CLM-2026-000123400",
    "CLM-2026-000123398"
  ],
  
  "historical_context": {
    "member_claims_30d": 5,
    "member_avg_claim": 450.00,
    "provider_claims_30d": 127,
    "provider_avg_claim": 780.00,
    "provider_denial_rate": 0.08
  },
  
  "decision_trace": {
    "analysis_id": "550e8400-e29b-41d4-a716-446655440000",
    "trace_version": "1.0.0",
    "start_timestamp": "2026-01-07T14:29:59.950Z",
    "end_timestamp": "2026-01-07T14:30:00.045Z",
    "stages": [
      {"stage": "SYNTHESIS_START", "timestamp": "2026-01-07T14:29:59.950Z"},
      {"stage": "RULE_PRECEDENCE_CHECK", "timestamp": "2026-01-07T14:29:59.955Z"},
      {"stage": "ML_DECISION", "timestamp": "2026-01-07T14:30:00.010Z"},
      {"stage": "CONFIDENCE_GATE", "timestamp": "2026-01-07T14:30:00.035Z"},
      {"stage": "AMOUNT_GUARDRAILS", "timestamp": "2026-01-07T14:30:00.040Z"},
      {"stage": "SYNTHESIS_COMPLETE", "timestamp": "2026-01-07T14:30:00.045Z"}
    ],
    "decisions": [
      {
        "type": "RULE_FLAG",
        "reason": "Rule flag(s) detected: 3 rule(s) flagged",
        "timestamp": "2026-01-07T14:29:59.958Z"
      },
      {
        "type": "CONFIDENCE_PASS",
        "reason": "Confidence 0.78 >= threshold 0.85",
        "timestamp": "2026-01-07T14:30:00.038Z"
      }
    ],
    "integrity_hash": "sha256:abc123def456..."
  },
  
  "processing_time_ms": 95.0
}
```

---

**END OF DECISION SYNTHESIS ENGINE SPECIFICATION**


