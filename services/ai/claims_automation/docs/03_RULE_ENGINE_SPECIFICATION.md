# Deterministic Rule Engine Specification

**Version:** 1.0.0  
**Date:** January 7, 2026  
**Classification:** CONFIDENTIAL - Technical Specification

---

## 1. Overview

The Deterministic Rule Engine is the **first gate** in the claims automation pipeline. It applies strict, versioned, rule-based checks that produce deterministic pass/fail/flag outcomes. These rules are non-ML, fully auditable, and operate independently of the ML fraud detection engine.

### 1.1 Core Principles

| Principle | Implementation |
|-----------|----------------|
| **Deterministic** | Same input → Same output (always) |
| **Versioned** | Every rule has semantic versioning |
| **Auditable** | Complete execution trace for every claim |
| **Immutable History** | Historical rule versions preserved |
| **Fast** | Sub-10ms for full rule evaluation |
| **Safe** | Rule failures → Manual review (never silent) |

### 1.2 Rule Engine Position in Pipeline

```
                        GATE 1: DETERMINISTIC RULE ENGINE
    ════════════════════════════════════════════════════════════════

    ┌─────────────────┐
    │  Claim Input    │
    │  (Sanitized)    │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                    RULE ENGINE ORCHESTRATOR                      │
    │                                                                  │
    │  ┌──────────────────────────────────────────────────────────┐  │
    │  │                  RULE CATEGORIES (Ordered)                │  │
    │  │                                                           │  │
    │  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │  │
    │  │  │ 1. CRITICAL │  │ 2. COVERAGE │  │ 3. PROVIDER │      │  │
    │  │  │   (Blocking)│  │   RULES     │  │   RULES     │      │  │
    │  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘      │  │
    │  │         │                │                │              │  │
    │  │  ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐      │  │
    │  │  │ 4. TARIFF   │  │ 5. CODING   │  │ 6. TEMPORAL │      │  │
    │  │  │   RULES     │  │   RULES     │  │   RULES     │      │  │
    │  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘      │  │
    │  │         │                │                │              │  │
    │  │  ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐      │  │
    │  │  │ 7. DUPLICATE│  │ 8. BENEFIT  │  │ 9. CUSTOM   │      │  │
    │  │  │   RULES     │  │   RULES     │  │   RULES     │      │  │
    │  │  └─────────────┘  └─────────────┘  └─────────────┘      │  │
    │  └───────────────────────────────────────────────────────────┘  │
    │                              │                                   │
    │                              ▼                                   │
    │  ┌───────────────────────────────────────────────────────────┐  │
    │  │                  OUTCOME AGGREGATOR                        │  │
    │  │                                                            │  │
    │  │    PASS: All rules passed                                  │  │
    │  │    FAIL: Any critical rule failed (hard deny)              │  │
    │  │    FLAG: One or more rules flagged (needs review)          │  │
    │  │                                                            │  │
    │  └───────────────────────────────────────────────────────────┘  │
    └─────────────────────────────────────────────────────────────────┘
             │
             ▼
    ┌─────────────────┐
    │  Rule Output    │
    │  + Audit Trail  │
    └─────────────────┘

    ════════════════════════════════════════════════════════════════
```

---

## 2. Rule Definition Schema

### 2.1 Rule Structure

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime

class RuleCategory(Enum):
    CRITICAL = "CRITICAL"              # Blocking rules (hard fail)
    POLICY_COVERAGE = "POLICY_COVERAGE"
    PROVIDER_ELIGIBILITY = "PROVIDER_ELIGIBILITY"
    TARIFF_COMPLIANCE = "TARIFF_COMPLIANCE"
    CODING_VALIDATION = "CODING_VALIDATION"
    TEMPORAL_VALIDATION = "TEMPORAL_VALIDATION"
    DUPLICATE_DETECTION = "DUPLICATE_DETECTION"
    BENEFIT_LIMITS = "BENEFIT_LIMITS"
    CUSTOM = "CUSTOM"

class RuleOutcome(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    FLAG = "FLAG"
    SKIP = "SKIP"  # Rule not applicable

class RuleSeverity(Enum):
    CRITICAL = "CRITICAL"    # Hard deny
    MAJOR = "MAJOR"          # Flag for review
    MINOR = "MINOR"          # Flag for review
    INFO = "INFO"            # Informational only

@dataclass(frozen=True)  # Immutable
class RuleDefinition:
    """
    Immutable rule definition. Once created, cannot be modified.
    New versions create new RuleDefinition instances.
    """
    rule_id: str                          # Unique identifier (e.g., "POL-001")
    version: str                          # Semantic version (e.g., "1.2.3")
    name: str                             # Human-readable name
    description: str                      # Detailed description
    category: RuleCategory                # Rule category
    severity: RuleSeverity               # Outcome severity
    enabled: bool                         # Active status
    
    # Rule logic
    condition_expression: str             # Boolean expression
    parameters: Dict[str, Any]            # Configurable parameters
    
    # Applicability
    applies_to_claim_types: List[str]     # e.g., ["PROFESSIONAL", "INSTITUTIONAL"]
    applies_to_jurisdictions: List[str]   # e.g., ["NG", "NG-LA", "NG-KN"]
    
    # Metadata
    effective_date: datetime
    expiration_date: Optional[datetime]
    created_by: str
    created_at: datetime
    documentation_url: Optional[str]
    
    # Audit
    checksum: str                         # SHA-256 of rule logic
    
    def __hash__(self):
        return hash((self.rule_id, self.version))

@dataclass
class RuleResult:
    """Result of evaluating a single rule."""
    rule_id: str
    rule_version: str
    rule_name: str
    category: RuleCategory
    outcome: RuleOutcome
    severity: RuleSeverity
    message: str
    details: Dict[str, Any]
    execution_time_ms: float
    timestamp: datetime
    
    # For debugging and audit
    input_snapshot: Dict[str, Any]       # Relevant input values
    expression_evaluated: str            # Actual expression evaluated
    parameter_values: Dict[str, Any]     # Parameter values used

@dataclass
class RuleEngineResult:
    """Aggregated result from rule engine."""
    aggregate_outcome: RuleOutcome       # PASS, FAIL, or FLAG
    rules_evaluated: int
    rules_passed: int
    rules_failed: int
    rules_flagged: int
    rules_skipped: int
    
    triggered_rules: List[RuleResult]    # Rules that didn't pass
    all_results: List[RuleResult]        # Complete evaluation results
    
    engine_version: str
    ruleset_version: str
    execution_time_ms: float
    timestamp: datetime
```

### 2.2 Rule Expression Language

The rule engine uses a safe, sandboxed expression language for defining conditions:

```python
class RuleExpressionLanguage:
    """
    Safe expression language for rule conditions.
    NO arbitrary code execution.
    NO external calls.
    Deterministic evaluation only.
    """
    
    # Allowed operators
    OPERATORS = {
        # Comparison
        '==', '!=', '<', '<=', '>', '>=',
        # Logical
        'and', 'or', 'not',
        # Membership
        'in', 'not in',
        # String
        'startswith', 'endswith', 'contains', 'matches',
        # Numeric
        'between', 'abs', 'round',
        # Date
        'days_since', 'days_until', 'within_days',
        # Collection
        'any', 'all', 'count', 'sum', 'avg', 'min', 'max',
        # Null checking
        'is_null', 'is_not_null', 'coalesce',
    }
    
    # Available context variables (read-only)
    CONTEXT_VARIABLES = {
        'claim': 'ClaimData',
        'policy': 'PolicyData',
        'provider': 'ProviderData',
        'member': 'MemberData',
        'history': 'ClaimHistoryData',
        'tariff': 'TariffData',
        'params': 'RuleParameters',
    }
    
    # Example expressions
    EXPRESSION_EXAMPLES = [
        # Policy coverage check
        "claim.service_date >= policy.effective_date and claim.service_date <= policy.termination_date",
        
        # Provider eligibility
        "provider.status == 'ACTIVE' and provider.network == policy.network",
        
        # Tariff compliance
        "claim.billed_amount <= tariff.max_allowed_amount * params.tolerance_factor",
        
        # Duplicate detection
        "not any(history.claims, c => c.procedure_codes == claim.procedure_codes and days_since(c.service_date) < params.duplicate_window_days)",
        
        # Temporal validation
        "claim.service_date <= today() and days_since(claim.service_date) <= params.max_filing_days",
        
        # Benefit limits
        "sum(history.claims_ytd, c => c.approved_amount) + claim.billed_amount <= policy.annual_limit",
    ]
```

---

## 3. Rule Categories & Definitions

### 3.1 Category 1: Critical Rules (Blocking)

These rules cause immediate FAIL with no override possible.

```yaml
rules:
  - rule_id: "CRT-001"
    version: "1.0.0"
    name: "Claim ID Format Validation"
    description: "Validates claim ID matches required format"
    category: CRITICAL
    severity: CRITICAL
    condition_expression: "matches(claim.claim_id, '^CLM-[0-9]{4}-[0-9]{6,12}$')"
    applies_to_claim_types: ["ALL"]
    
  - rule_id: "CRT-002"
    version: "1.0.0"
    name: "Policy Existence Check"
    description: "Verifies policy exists in system"
    category: CRITICAL
    severity: CRITICAL
    condition_expression: "is_not_null(policy) and policy.exists == true"
    applies_to_claim_types: ["ALL"]
    
  - rule_id: "CRT-003"
    version: "1.0.0"
    name: "Member-Policy Association"
    description: "Confirms member is covered under the policy"
    category: CRITICAL
    severity: CRITICAL
    condition_expression: "member.member_id in policy.covered_members"
    applies_to_claim_types: ["ALL"]
    
  - rule_id: "CRT-004"
    version: "1.0.0"
    name: "Future Date Rejection"
    description: "Rejects claims with future service dates"
    category: CRITICAL
    severity: CRITICAL
    condition_expression: "claim.service_date <= today()"
    applies_to_claim_types: ["ALL"]
    
  - rule_id: "CRT-005"
    version: "1.0.0"
    name: "Negative Amount Rejection"
    description: "Rejects claims with negative or zero amounts"
    category: CRITICAL
    severity: CRITICAL
    condition_expression: "claim.billed_amount > 0"
    applies_to_claim_types: ["ALL"]
```

### 3.2 Category 2: Policy Coverage Rules

```yaml
rules:
  - rule_id: "POL-001"
    version: "2.1.0"
    name: "Policy Active Status"
    description: "Verifies policy is active on service date"
    category: POLICY_COVERAGE
    severity: MAJOR
    condition_expression: >
      policy.status == 'ACTIVE' and
      claim.service_date >= policy.effective_date and
      claim.service_date <= coalesce(policy.termination_date, '9999-12-31')
    applies_to_claim_types: ["ALL"]
    
  - rule_id: "POL-002"
    version: "1.3.0"
    name: "Benefit Category Coverage"
    description: "Checks if service category is covered by policy"
    category: POLICY_COVERAGE
    severity: MAJOR
    condition_expression: >
      claim.benefit_category in policy.covered_benefits or
      'ALL' in policy.covered_benefits
    applies_to_claim_types: ["ALL"]
    
  - rule_id: "POL-003"
    version: "1.0.0"
    name: "Pre-Existing Condition Waiting Period"
    description: "Enforces waiting period for pre-existing conditions"
    category: POLICY_COVERAGE
    severity: MAJOR
    condition_expression: >
      not any(claim.diagnosis_codes, dx => dx.code in member.pre_existing_conditions) or
      days_since(policy.effective_date) >= policy.pre_existing_waiting_days
    parameters:
      default_waiting_days: 365
    applies_to_claim_types: ["PROFESSIONAL", "INSTITUTIONAL"]
    
  - rule_id: "POL-004"
    version: "1.1.0"
    name: "Prior Authorization Required"
    description: "Checks if required prior authorization exists"
    category: POLICY_COVERAGE
    severity: MAJOR
    condition_expression: >
      not any(claim.procedure_codes, p => p.code in params.prior_auth_required_codes) or
      is_not_null(claim.prior_auth_number) and
      claim.prior_auth_number in policy.approved_authorizations
    parameters:
      prior_auth_required_codes: []  # Loaded from tariff config
    applies_to_claim_types: ["PROFESSIONAL", "INSTITUTIONAL"]
```

### 3.3 Category 3: Provider Eligibility Rules

```yaml
rules:
  - rule_id: "PRV-001"
    version: "1.2.0"
    name: "Provider Active Status"
    description: "Verifies provider is active on service date"
    category: PROVIDER_ELIGIBILITY
    severity: MAJOR
    condition_expression: >
      provider.status == 'ACTIVE' and
      claim.service_date >= provider.effective_date and
      claim.service_date <= coalesce(provider.termination_date, '9999-12-31')
    applies_to_claim_types: ["ALL"]
    
  - rule_id: "PRV-002"
    version: "1.0.0"
    name: "Provider Network Match"
    description: "Checks provider is in-network for the policy"
    category: PROVIDER_ELIGIBILITY
    severity: MINOR
    condition_expression: >
      provider.network_id in policy.network_ids or
      claim.network_status == 'OUT_OF_NETWORK'
    applies_to_claim_types: ["PROFESSIONAL", "INSTITUTIONAL"]
    
  - rule_id: "PRV-003"
    version: "1.1.0"
    name: "Provider License Validation"
    description: "Verifies provider license is valid for services rendered"
    category: PROVIDER_ELIGIBILITY
    severity: MAJOR
    condition_expression: >
      provider.license_status == 'VALID' and
      provider.license_expiry >= claim.service_date and
      any(provider.license_types, lt => lt in params.allowed_license_types_for_service)
    parameters:
      allowed_license_types_for_service: {}  # Mapped by service type
    applies_to_claim_types: ["PROFESSIONAL"]
    
  - rule_id: "PRV-004"
    version: "1.0.0"
    name: "Provider Specialty Match"
    description: "Flags if service doesn't match provider specialty"
    category: PROVIDER_ELIGIBILITY
    severity: MINOR
    condition_expression: >
      any(claim.procedure_codes, p => 
        p.specialty_requirement in provider.specialties or
        p.specialty_requirement == 'ANY'
      )
    applies_to_claim_types: ["PROFESSIONAL"]
```

### 3.4 Category 4: Tariff Compliance Rules

```yaml
rules:
  - rule_id: "TAR-001"
    version: "2.0.0"
    name: "Maximum Allowable Amount"
    description: "Checks billed amount against tariff maximum"
    category: TARIFF_COMPLIANCE
    severity: MINOR
    condition_expression: >
      all(claim.procedure_codes, p =>
        p.line_amount <= tariff.get_max_amount(p.code) * params.tolerance_factor
      )
    parameters:
      tolerance_factor: 1.25  # 25% tolerance
    applies_to_claim_types: ["ALL"]
    
  - rule_id: "TAR-002"
    version: "1.1.0"
    name: "Total Claim Amount Threshold"
    description: "Flags claims exceeding threshold for review"
    category: TARIFF_COMPLIANCE
    severity: MINOR
    condition_expression: >
      claim.billed_amount <= params.auto_approve_threshold
    parameters:
      auto_approve_threshold: 1000000  # 1M units
    applies_to_claim_types: ["ALL"]
    
  - rule_id: "TAR-003"
    version: "1.0.0"
    name: "Fee Schedule Compliance"
    description: "Validates against contracted fee schedule"
    category: TARIFF_COMPLIANCE
    severity: MINOR
    condition_expression: >
      claim.network_status == 'OUT_OF_NETWORK' or
      all(claim.procedure_codes, p =>
        p.line_amount <= tariff.get_contracted_rate(provider.contract_id, p.code)
      )
    applies_to_claim_types: ["PROFESSIONAL"]
    
  - rule_id: "TAR-004"
    version: "1.2.0"
    name: "Percentile Threshold Flag"
    description: "Flags claims above 95th percentile for procedure"
    category: TARIFF_COMPLIANCE
    severity: MINOR
    condition_expression: >
      all(claim.procedure_codes, p =>
        p.line_amount <= tariff.get_percentile(p.code, 95)
      )
    applies_to_claim_types: ["ALL"]
```

### 3.5 Category 5: Coding Validation Rules

```yaml
rules:
  - rule_id: "COD-001"
    version: "1.0.0"
    name: "Valid Procedure Code"
    description: "Validates procedure codes exist in code set"
    category: CODING_VALIDATION
    severity: MAJOR
    condition_expression: >
      all(claim.procedure_codes, p =>
        tariff.is_valid_code(p.code, p.code_type)
      )
    applies_to_claim_types: ["ALL"]
    
  - rule_id: "COD-002"
    version: "1.0.0"
    name: "Valid Diagnosis Code"
    description: "Validates diagnosis codes exist in ICD-10"
    category: CODING_VALIDATION
    severity: MAJOR
    condition_expression: >
      all(claim.diagnosis_codes, dx =>
        tariff.is_valid_diagnosis(dx.code, dx.code_type)
      )
    applies_to_claim_types: ["ALL"]
    
  - rule_id: "COD-003"
    version: "1.1.0"
    name: "Procedure-Diagnosis Compatibility"
    description: "Checks procedure codes are valid for diagnoses"
    category: CODING_VALIDATION
    severity: MINOR
    condition_expression: >
      any(claim.procedure_codes, p =>
        any(claim.diagnosis_codes, dx =>
          tariff.is_compatible(p.code, dx.code)
        )
      )
    applies_to_claim_types: ["PROFESSIONAL", "INSTITUTIONAL"]
    
  - rule_id: "COD-004"
    version: "1.0.0"
    name: "Gender-Specific Procedure Check"
    description: "Validates gender-specific procedures match member gender"
    category: CODING_VALIDATION
    severity: MAJOR
    condition_expression: >
      all(claim.procedure_codes, p =>
        tariff.get_gender_requirement(p.code) == 'ANY' or
        tariff.get_gender_requirement(p.code) == member.gender
      )
    applies_to_claim_types: ["PROFESSIONAL"]
    
  - rule_id: "COD-005"
    version: "1.0.0"
    name: "Age-Appropriate Procedure Check"
    description: "Validates procedures are age-appropriate"
    category: CODING_VALIDATION
    severity: MAJOR
    condition_expression: >
      all(claim.procedure_codes, p =>
        member.age >= tariff.get_min_age(p.code) and
        member.age <= tariff.get_max_age(p.code)
      )
    applies_to_claim_types: ["PROFESSIONAL"]
    
  - rule_id: "COD-006"
    version: "1.2.0"
    name: "Unbundling Detection"
    description: "Detects potential code unbundling"
    category: CODING_VALIDATION
    severity: MINOR
    condition_expression: >
      not any(claim.procedure_codes, p1 =>
        any(claim.procedure_codes, p2 =>
          p1.code != p2.code and
          tariff.is_component_of(p1.code, p2.code)
        )
      )
    applies_to_claim_types: ["PROFESSIONAL"]
```

### 3.6 Category 6: Temporal Validation Rules

```yaml
rules:
  - rule_id: "TMP-001"
    version: "1.0.0"
    name: "Timely Filing Limit"
    description: "Checks claim submitted within filing deadline"
    category: TEMPORAL_VALIDATION
    severity: MAJOR
    condition_expression: >
      days_since(claim.service_date) <= params.timely_filing_days
    parameters:
      timely_filing_days: 90
    applies_to_claim_types: ["ALL"]
    
  - rule_id: "TMP-002"
    version: "1.0.0"
    name: "Service Date Sequence"
    description: "Validates service date range is logical"
    category: TEMPORAL_VALIDATION
    severity: MAJOR
    condition_expression: >
      is_null(claim.service_date_end) or
      claim.service_date <= claim.service_date_end
    applies_to_claim_types: ["ALL"]
    
  - rule_id: "TMP-003"
    version: "1.0.0"
    name: "Admission-Discharge Sequence"
    description: "Validates admission/discharge dates for inpatient"
    category: TEMPORAL_VALIDATION
    severity: MAJOR
    condition_expression: >
      claim.claim_type != 'INSTITUTIONAL' or
      is_null(claim.admission_date) or
      (claim.admission_date <= claim.service_date and
       claim.service_date <= coalesce(claim.discharge_date, today()))
    applies_to_claim_types: ["INSTITUTIONAL"]
    
  - rule_id: "TMP-004"
    version: "1.1.0"
    name: "Minimum Service Interval"
    description: "Flags services performed too quickly after previous"
    category: TEMPORAL_VALIDATION
    severity: MINOR
    condition_expression: >
      all(claim.procedure_codes, p =>
        not any(history.claims_90d, h =>
          p.code in h.procedure_codes and
          days_since(h.service_date) < tariff.get_min_interval(p.code)
        )
      )
    applies_to_claim_types: ["PROFESSIONAL"]
```

### 3.7 Category 7: Duplicate Detection Rules

```yaml
rules:
  - rule_id: "DUP-001"
    version: "1.0.0"
    name: "Exact Duplicate Detection"
    description: "Detects exact duplicate claims"
    category: DUPLICATE_DETECTION
    severity: CRITICAL
    condition_expression: >
      not any(history.claims, h =>
        h.claim_id != claim.claim_id and
        h.member_id_hash == claim.member_id_hash and
        h.service_date == claim.service_date and
        h.procedure_codes == claim.procedure_codes and
        h.billed_amount == claim.billed_amount
      )
    applies_to_claim_types: ["ALL"]
    
  - rule_id: "DUP-002"
    version: "1.1.0"
    name: "Possible Duplicate (Same Day)"
    description: "Flags possible duplicates on same service date"
    category: DUPLICATE_DETECTION
    severity: MINOR
    condition_expression: >
      count(history.claims, h =>
        h.claim_id != claim.claim_id and
        h.member_id_hash == claim.member_id_hash and
        h.service_date == claim.service_date and
        any(h.procedure_codes, hp => hp.code in claim.procedure_codes_list)
      ) == 0
    applies_to_claim_types: ["ALL"]
    
  - rule_id: "DUP-003"
    version: "1.0.0"
    name: "Overlapping Inpatient Stay"
    description: "Detects overlapping inpatient claims"
    category: DUPLICATE_DETECTION
    severity: MAJOR
    condition_expression: >
      claim.claim_type != 'INSTITUTIONAL' or
      not any(history.institutional_claims, h =>
        h.claim_id != claim.claim_id and
        h.member_id_hash == claim.member_id_hash and
        h.facility_type in ['INPATIENT_HOSPITAL', 'SKILLED_NURSING'] and
        (
          (claim.admission_date between h.admission_date and h.discharge_date) or
          (claim.discharge_date between h.admission_date and h.discharge_date)
        )
      )
    applies_to_claim_types: ["INSTITUTIONAL"]
```

### 3.8 Category 8: Benefit Limits Rules

```yaml
rules:
  - rule_id: "BEN-001"
    version: "1.0.0"
    name: "Annual Maximum Check"
    description: "Checks against annual benefit maximum"
    category: BENEFIT_LIMITS
    severity: MAJOR
    condition_expression: >
      sum(history.claims_ytd, h => h.approved_amount) + claim.billed_amount <= policy.annual_maximum
    applies_to_claim_types: ["ALL"]
    
  - rule_id: "BEN-002"
    version: "1.0.0"
    name: "Lifetime Maximum Check"
    description: "Checks against lifetime benefit maximum"
    category: BENEFIT_LIMITS
    severity: MAJOR
    condition_expression: >
      is_null(policy.lifetime_maximum) or
      sum(history.claims_lifetime, h => h.approved_amount) + claim.billed_amount <= policy.lifetime_maximum
    applies_to_claim_types: ["ALL"]
    
  - rule_id: "BEN-003"
    version: "1.1.0"
    name: "Visit Limit Check"
    description: "Checks against annual visit limits by category"
    category: BENEFIT_LIMITS
    severity: MINOR
    condition_expression: >
      all(claim.procedure_codes, p =>
        is_null(policy.visit_limits[p.benefit_category]) or
        count(history.claims_ytd, h => 
          any(h.procedure_codes, hp => hp.benefit_category == p.benefit_category)
        ) < policy.visit_limits[p.benefit_category]
      )
    applies_to_claim_types: ["PROFESSIONAL"]
    
  - rule_id: "BEN-004"
    version: "1.0.0"
    name: "Deductible Status"
    description: "Calculates deductible remaining"
    category: BENEFIT_LIMITS
    severity: INFO
    condition_expression: >
      sum(history.claims_ytd, h => min(h.member_responsibility, policy.deductible)) >= policy.deductible
    applies_to_claim_types: ["ALL"]
```

---

## 4. Rule Engine Implementation

### 4.1 Engine Architecture

```python
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import time

class DeterministicRuleEngine:
    """
    Thread-safe, deterministic rule engine.
    Produces identical outputs for identical inputs.
    """
    
    def __init__(self, config: RuleEngineConfig):
        self.config = config
        self.rule_store = RuleStore(config.rule_store_path)
        self.expression_evaluator = SafeExpressionEvaluator()
        self.context_builder = RuleContextBuilder()
        self.audit_logger = RuleAuditLogger()
        
        # Load active ruleset
        self.active_ruleset: Dict[str, RuleDefinition] = {}
        self.ruleset_version: str = ""
        self._load_active_ruleset()
    
    def _load_active_ruleset(self) -> None:
        """Load the active ruleset version."""
        self.active_ruleset = self.rule_store.get_active_ruleset()
        self.ruleset_version = self.rule_store.get_active_version()
        
        # Verify checksums
        for rule_id, rule in self.active_ruleset.items():
            computed_checksum = self._compute_checksum(rule)
            if computed_checksum != rule.checksum:
                raise RuleIntegrityError(
                    f"Rule {rule_id} checksum mismatch: expected {rule.checksum}, got {computed_checksum}"
                )
    
    def evaluate_claim(self, claim_data: ClaimData) -> RuleEngineResult:
        """
        Evaluate all applicable rules against a claim.
        Returns deterministic result with full audit trail.
        """
        start_time = time.perf_counter()
        timestamp = datetime.utcnow()
        
        # Build evaluation context
        context = self.context_builder.build_context(claim_data)
        
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
                    timestamp=timestamp,
                    input_snapshot={},
                    expression_evaluated=rule.condition_expression,
                    parameter_values={}
                )
            else:
                result = self._evaluate_rule(rule, context, timestamp)
                
                if result.outcome == RuleOutcome.FAIL and rule.severity == RuleSeverity.CRITICAL:
                    critical_failure = True
            
            results.append(result)
        
        # Aggregate results
        execution_time_ms = (time.perf_counter() - start_time) * 1000
        engine_result = self._aggregate_results(results, execution_time_ms, timestamp)
        
        # Audit log
        self.audit_logger.log_evaluation(claim_data.claim_id, engine_result)
        
        return engine_result
    
    def _evaluate_rule(
        self,
        rule: RuleDefinition,
        context: RuleContext,
        timestamp: datetime
    ) -> RuleResult:
        """Evaluate a single rule."""
        start_time = time.perf_counter()
        
        try:
            # Evaluate expression
            outcome_bool = self.expression_evaluator.evaluate(
                expression=rule.condition_expression,
                context=context,
                parameters=rule.parameters
            )
            
            # Determine outcome
            if outcome_bool:
                outcome = RuleOutcome.PASS
                message = f"Rule {rule.name} passed"
            else:
                if rule.severity == RuleSeverity.CRITICAL:
                    outcome = RuleOutcome.FAIL
                    message = f"Critical rule {rule.name} failed"
                else:
                    outcome = RuleOutcome.FLAG
                    message = f"Rule {rule.name} flagged for review"
            
            details = {}
            
        except RuleEvaluationError as e:
            # Rule evaluation errors should flag, not crash
            outcome = RuleOutcome.FLAG
            message = f"Rule evaluation error: {str(e)}"
            details = {"error": str(e), "error_type": type(e).__name__}
        
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
            input_snapshot=context.get_snapshot_for_rule(rule.rule_id),
            expression_evaluated=rule.condition_expression,
            parameter_values=rule.parameters
        )
    
    def _get_applicable_rules(self, claim_data: ClaimData) -> List[RuleDefinition]:
        """Get rules applicable to this claim, in evaluation order."""
        applicable = []
        
        # Define category evaluation order
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
                if claim_data.claim_type not in rule.applies_to_claim_types and 'ALL' not in rule.applies_to_claim_types:
                    continue
                
                applicable.append(rule)
        
        return applicable
    
    def _aggregate_results(
        self,
        results: List[RuleResult],
        execution_time_ms: float,
        timestamp: datetime
    ) -> RuleEngineResult:
        """Aggregate individual rule results into final outcome."""
        
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
            engine_version=self.config.engine_version,
            ruleset_version=self.ruleset_version,
            execution_time_ms=execution_time_ms,
            timestamp=timestamp
        )
    
    def _compute_checksum(self, rule: RuleDefinition) -> str:
        """Compute deterministic checksum of rule logic."""
        checksum_data = {
            "rule_id": rule.rule_id,
            "version": rule.version,
            "condition_expression": rule.condition_expression,
            "parameters": rule.parameters,
        }
        checksum_bytes = json.dumps(checksum_data, sort_keys=True).encode()
        return hashlib.sha256(checksum_bytes).hexdigest()
```

### 4.2 Safe Expression Evaluator

```python
import ast
import operator
from typing import Any, Dict

class SafeExpressionEvaluator:
    """
    Sandboxed expression evaluator.
    Only allows pre-defined safe operations.
    NO arbitrary code execution.
    """
    
    # Allowed binary operators
    BINARY_OPS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Mod: operator.mod,
        ast.Eq: operator.eq,
        ast.NotEq: operator.ne,
        ast.Lt: operator.lt,
        ast.LtE: operator.le,
        ast.Gt: operator.gt,
        ast.GtE: operator.ge,
        ast.And: lambda a, b: a and b,
        ast.Or: lambda a, b: a or b,
        ast.In: lambda a, b: a in b,
        ast.NotIn: lambda a, b: a not in b,
    }
    
    # Allowed unary operators
    UNARY_OPS = {
        ast.Not: operator.not_,
        ast.USub: operator.neg,
    }
    
    # Allowed builtin functions (safe subset)
    SAFE_FUNCTIONS = {
        'abs': abs,
        'round': round,
        'min': min,
        'max': max,
        'sum': sum,
        'len': len,
        'all': all,
        'any': any,
        'str': str,
        'int': int,
        'float': float,
        'bool': bool,
    }
    
    def __init__(self):
        self.custom_functions = {}
        self._register_custom_functions()
    
    def _register_custom_functions(self):
        """Register domain-specific safe functions."""
        self.custom_functions = {
            'days_since': self._days_since,
            'days_until': self._days_until,
            'within_days': self._within_days,
            'today': self._today,
            'is_null': lambda x: x is None,
            'is_not_null': lambda x: x is not None,
            'coalesce': self._coalesce,
            'matches': self._matches,
            'startswith': lambda s, p: str(s).startswith(p),
            'endswith': lambda s, p: str(s).endswith(p),
            'contains': lambda s, p: p in str(s),
            'between': lambda v, a, b: a <= v <= b,
            'count': self._count,
        }
    
    def evaluate(
        self,
        expression: str,
        context: Dict[str, Any],
        parameters: Dict[str, Any]
    ) -> bool:
        """
        Safely evaluate an expression.
        Returns boolean result.
        """
        # Parse expression into AST
        try:
            tree = ast.parse(expression, mode='eval')
        except SyntaxError as e:
            raise RuleExpressionError(f"Invalid expression syntax: {e}")
        
        # Build evaluation namespace
        namespace = {
            **context,
            'params': parameters,
            **self.SAFE_FUNCTIONS,
            **self.custom_functions,
        }
        
        # Evaluate with safety checks
        try:
            result = self._safe_eval(tree.body, namespace)
            return bool(result)
        except Exception as e:
            raise RuleEvaluationError(f"Expression evaluation failed: {e}")
    
    def _safe_eval(self, node: ast.AST, namespace: Dict[str, Any]) -> Any:
        """Recursively evaluate AST node with safety checks."""
        
        if isinstance(node, ast.Constant):
            return node.value
        
        elif isinstance(node, ast.Name):
            if node.id not in namespace:
                raise RuleEvaluationError(f"Unknown variable: {node.id}")
            return namespace[node.id]
        
        elif isinstance(node, ast.Attribute):
            value = self._safe_eval(node.value, namespace)
            if not hasattr(value, node.attr):
                raise RuleEvaluationError(f"Unknown attribute: {node.attr}")
            return getattr(value, node.attr)
        
        elif isinstance(node, ast.Subscript):
            value = self._safe_eval(node.value, namespace)
            key = self._safe_eval(node.slice, namespace)
            return value[key]
        
        elif isinstance(node, ast.BinOp):
            op_type = type(node.op)
            if op_type not in self.BINARY_OPS:
                raise RuleEvaluationError(f"Unsupported operator: {op_type}")
            left = self._safe_eval(node.left, namespace)
            right = self._safe_eval(node.right, namespace)
            return self.BINARY_OPS[op_type](left, right)
        
        elif isinstance(node, ast.Compare):
            left = self._safe_eval(node.left, namespace)
            for op, comparator in zip(node.ops, node.comparators):
                op_type = type(op)
                if op_type not in self.BINARY_OPS:
                    raise RuleEvaluationError(f"Unsupported comparison: {op_type}")
                right = self._safe_eval(comparator, namespace)
                if not self.BINARY_OPS[op_type](left, right):
                    return False
                left = right
            return True
        
        elif isinstance(node, ast.BoolOp):
            op_type = type(node.op)
            if op_type == ast.And:
                return all(self._safe_eval(v, namespace) for v in node.values)
            elif op_type == ast.Or:
                return any(self._safe_eval(v, namespace) for v in node.values)
            else:
                raise RuleEvaluationError(f"Unsupported boolean operator: {op_type}")
        
        elif isinstance(node, ast.UnaryOp):
            op_type = type(node.op)
            if op_type not in self.UNARY_OPS:
                raise RuleEvaluationError(f"Unsupported unary operator: {op_type}")
            operand = self._safe_eval(node.operand, namespace)
            return self.UNARY_OPS[op_type](operand)
        
        elif isinstance(node, ast.Call):
            func = self._safe_eval(node.func, namespace)
            if not callable(func):
                raise RuleEvaluationError(f"Not callable: {func}")
            args = [self._safe_eval(arg, namespace) for arg in node.args]
            kwargs = {kw.arg: self._safe_eval(kw.value, namespace) for kw in node.keywords}
            return func(*args, **kwargs)
        
        elif isinstance(node, ast.List):
            return [self._safe_eval(elt, namespace) for elt in node.elts]
        
        elif isinstance(node, ast.Dict):
            return {
                self._safe_eval(k, namespace): self._safe_eval(v, namespace)
                for k, v in zip(node.keys, node.values)
            }
        
        elif isinstance(node, ast.IfExp):
            test = self._safe_eval(node.test, namespace)
            if test:
                return self._safe_eval(node.body, namespace)
            else:
                return self._safe_eval(node.orelse, namespace)
        
        else:
            raise RuleEvaluationError(f"Unsupported expression type: {type(node)}")
    
    # Custom function implementations
    def _days_since(self, date_value) -> int:
        if isinstance(date_value, str):
            date_value = datetime.fromisoformat(date_value)
        return (datetime.utcnow().date() - date_value.date()).days
    
    def _days_until(self, date_value) -> int:
        if isinstance(date_value, str):
            date_value = datetime.fromisoformat(date_value)
        return (date_value.date() - datetime.utcnow().date()).days
    
    def _within_days(self, date_value, days: int) -> bool:
        return abs(self._days_since(date_value)) <= days
    
    def _today(self) -> date:
        return datetime.utcnow().date()
    
    def _coalesce(self, *args):
        for arg in args:
            if arg is not None:
                return arg
        return None
    
    def _matches(self, value: str, pattern: str) -> bool:
        import re
        return bool(re.match(pattern, str(value)))
    
    def _count(self, collection, predicate=None) -> int:
        if predicate is None:
            return len(collection)
        return sum(1 for item in collection if predicate(item))
```

---

## 5. Rule Versioning & Deployment

### 5.1 Version Control Strategy

```yaml
# Rule deployment pipeline
rule_versioning:
  format: "MAJOR.MINOR.PATCH"
  
  major_change:
    - Logic change affecting outcomes
    - Parameter type changes
    - Expression structure changes
    triggers: Manual approval required
    
  minor_change:
    - New optional parameters
    - Documentation updates
    - Performance optimizations
    triggers: Automated review
    
  patch_change:
    - Bug fixes
    - Typo corrections
    triggers: Automated deployment
  
  deployment:
    stages:
      - name: "development"
        validation: Unit tests
        
      - name: "staging"
        validation: Integration tests + Historical replay
        duration: "7 days"
        
      - name: "canary"
        validation: 5% traffic, monitor outcomes
        duration: "3 days"
        
      - name: "production"
        validation: Full deployment
        rollback_window: "24 hours"
```

### 5.2 Rule Store Schema

```sql
-- PostgreSQL schema for rule storage
CREATE TABLE rule_definitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_id VARCHAR(50) NOT NULL,
    version VARCHAR(20) NOT NULL,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    category VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    condition_expression TEXT NOT NULL,
    parameters JSONB DEFAULT '{}',
    applies_to_claim_types TEXT[] NOT NULL,
    applies_to_jurisdictions TEXT[] DEFAULT ARRAY['ALL'],
    effective_date TIMESTAMPTZ NOT NULL,
    expiration_date TIMESTAMPTZ,
    enabled BOOLEAN DEFAULT true,
    checksum VARCHAR(64) NOT NULL,
    created_by VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    approved_by VARCHAR(100),
    approved_at TIMESTAMPTZ,
    
    UNIQUE(rule_id, version),
    
    CONSTRAINT valid_category CHECK (category IN (
        'CRITICAL', 'POLICY_COVERAGE', 'PROVIDER_ELIGIBILITY',
        'TARIFF_COMPLIANCE', 'CODING_VALIDATION', 'TEMPORAL_VALIDATION',
        'DUPLICATE_DETECTION', 'BENEFIT_LIMITS', 'CUSTOM'
    )),
    
    CONSTRAINT valid_severity CHECK (severity IN (
        'CRITICAL', 'MAJOR', 'MINOR', 'INFO'
    ))
);

CREATE TABLE rule_sets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    rule_ids TEXT[] NOT NULL,
    status VARCHAR(20) DEFAULT 'DRAFT',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    activated_at TIMESTAMPTZ,
    deactivated_at TIMESTAMPTZ,
    
    CONSTRAINT valid_status CHECK (status IN (
        'DRAFT', 'TESTING', 'CANARY', 'ACTIVE', 'DEPRECATED'
    ))
);

CREATE TABLE rule_execution_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_id VARCHAR(50) NOT NULL,
    ruleset_version VARCHAR(50) NOT NULL,
    rule_id VARCHAR(50) NOT NULL,
    rule_version VARCHAR(20) NOT NULL,
    outcome VARCHAR(10) NOT NULL,
    execution_time_ms DECIMAL(10,3),
    input_snapshot JSONB,
    message TEXT,
    details JSONB,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    
    INDEX idx_rule_execution_claim (claim_id),
    INDEX idx_rule_execution_time (timestamp),
    INDEX idx_rule_execution_rule (rule_id, rule_version)
);

-- Immutable audit log (append-only)
CREATE TABLE rule_audit_log (
    id BIGSERIAL PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    rule_id VARCHAR(50),
    rule_version VARCHAR(20),
    ruleset_version VARCHAR(50),
    actor VARCHAR(100) NOT NULL,
    action_details JSONB NOT NULL,
    previous_state JSONB,
    new_state JSONB,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    integrity_hash VARCHAR(128) NOT NULL
);

-- Prevent updates/deletes on audit log
CREATE RULE rule_audit_no_update AS ON UPDATE TO rule_audit_log DO INSTEAD NOTHING;
CREATE RULE rule_audit_no_delete AS ON DELETE TO rule_audit_log DO INSTEAD NOTHING;
```

---

## 6. Testing & Validation

### 6.1 Rule Testing Framework

```python
class RuleTestCase:
    """Test case for rule validation."""
    
    def __init__(
        self,
        name: str,
        rule_id: str,
        input_data: Dict[str, Any],
        expected_outcome: RuleOutcome,
        description: str = ""
    ):
        self.name = name
        self.rule_id = rule_id
        self.input_data = input_data
        self.expected_outcome = expected_outcome
        self.description = description

class RuleTestSuite:
    """Comprehensive test suite for rules."""
    
    def __init__(self, engine: DeterministicRuleEngine):
        self.engine = engine
        self.test_cases: List[RuleTestCase] = []
    
    def add_test(self, test_case: RuleTestCase) -> None:
        self.test_cases.append(test_case)
    
    def run_all(self) -> TestReport:
        """Run all test cases and generate report."""
        results = []
        
        for test in self.test_cases:
            result = self._run_single_test(test)
            results.append(result)
        
        return TestReport(
            total=len(results),
            passed=sum(1 for r in results if r.passed),
            failed=sum(1 for r in results if not r.passed),
            results=results
        )
    
    def _run_single_test(self, test: RuleTestCase) -> TestResult:
        """Run a single test case."""
        try:
            claim_data = ClaimData.from_dict(test.input_data)
            result = self.engine.evaluate_claim(claim_data)
            
            # Find the specific rule result
            rule_result = next(
                (r for r in result.all_results if r.rule_id == test.rule_id),
                None
            )
            
            if rule_result is None:
                return TestResult(
                    test_name=test.name,
                    passed=False,
                    expected=test.expected_outcome,
                    actual=None,
                    error=f"Rule {test.rule_id} not found in results"
                )
            
            passed = rule_result.outcome == test.expected_outcome
            
            return TestResult(
                test_name=test.name,
                passed=passed,
                expected=test.expected_outcome,
                actual=rule_result.outcome,
                execution_time_ms=rule_result.execution_time_ms,
                details=rule_result.details if not passed else None
            )
            
        except Exception as e:
            return TestResult(
                test_name=test.name,
                passed=False,
                expected=test.expected_outcome,
                actual=None,
                error=str(e)
            )

# Example test cases
STANDARD_TEST_CASES = [
    RuleTestCase(
        name="POL-001: Active policy passes",
        rule_id="POL-001",
        input_data={
            "claim": {"service_date": "2026-01-07"},
            "policy": {
                "status": "ACTIVE",
                "effective_date": "2025-01-01",
                "termination_date": "2026-12-31"
            }
        },
        expected_outcome=RuleOutcome.PASS,
        description="Policy active on service date should pass"
    ),
    RuleTestCase(
        name="POL-001: Expired policy fails",
        rule_id="POL-001",
        input_data={
            "claim": {"service_date": "2026-01-07"},
            "policy": {
                "status": "ACTIVE",
                "effective_date": "2024-01-01",
                "termination_date": "2024-12-31"
            }
        },
        expected_outcome=RuleOutcome.FLAG,
        description="Policy expired before service date should flag"
    ),
    RuleTestCase(
        name="DUP-001: Exact duplicate detected",
        rule_id="DUP-001",
        input_data={
            "claim": {
                "claim_id": "CLM-2026-000002",
                "member_id_hash": "abc123",
                "service_date": "2026-01-05",
                "procedure_codes": [{"code": "99213"}],
                "billed_amount": 150.00
            },
            "history": {
                "claims": [{
                    "claim_id": "CLM-2026-000001",
                    "member_id_hash": "abc123",
                    "service_date": "2026-01-05",
                    "procedure_codes": [{"code": "99213"}],
                    "billed_amount": 150.00
                }]
            }
        },
        expected_outcome=RuleOutcome.FAIL,
        description="Exact duplicate should hard fail"
    ),
]
```

---

**END OF RULE ENGINE SPECIFICATION**


