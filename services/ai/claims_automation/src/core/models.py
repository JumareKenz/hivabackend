"""
Core Data Models for DCAL
Defines all domain objects used across the system
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from enum import Enum
import hashlib
import json


# =============================================================================
# ENUMERATIONS
# =============================================================================

class ClaimType(str, Enum):
    PROFESSIONAL = "PROFESSIONAL"
    INSTITUTIONAL = "INSTITUTIONAL"
    DENTAL = "DENTAL"
    PHARMACY = "PHARMACY"
    VISION = "VISION"


class FacilityType(str, Enum):
    INPATIENT_HOSPITAL = "INPATIENT_HOSPITAL"
    OUTPATIENT_HOSPITAL = "OUTPATIENT_HOSPITAL"
    SKILLED_NURSING = "SKILLED_NURSING"
    PHYSICIAN_OFFICE = "PHYSICIAN_OFFICE"
    URGENT_CARE = "URGENT_CARE"
    EMERGENCY_ROOM = "EMERGENCY_ROOM"
    AMBULATORY_SURGERY = "AMBULATORY_SURGERY"
    HOME_HEALTH = "HOME_HEALTH"
    PHARMACY = "PHARMACY"
    LAB = "LAB"
    DME = "DME"
    OTHER = "OTHER"


class NetworkStatus(str, Enum):
    IN_NETWORK = "IN_NETWORK"
    OUT_OF_NETWORK = "OUT_OF_NETWORK"
    UNKNOWN = "UNKNOWN"


class RuleOutcome(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    FLAG = "FLAG"
    SKIP = "SKIP"


class RuleSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    MAJOR = "MAJOR"
    MINOR = "MINOR"
    INFO = "INFO"


class RuleCategory(str, Enum):
    CRITICAL = "CRITICAL"
    POLICY_COVERAGE = "POLICY_COVERAGE"
    PROVIDER_ELIGIBILITY = "PROVIDER_ELIGIBILITY"
    TARIFF_COMPLIANCE = "TARIFF_COMPLIANCE"
    CODING_VALIDATION = "CODING_VALIDATION"
    TEMPORAL_VALIDATION = "TEMPORAL_VALIDATION"
    DUPLICATE_DETECTION = "DUPLICATE_DETECTION"
    BENEFIT_LIMITS = "BENEFIT_LIMITS"
    CUSTOM = "CUSTOM"


class FinalRecommendation(str, Enum):
    AUTO_APPROVE = "AUTO_APPROVE"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    AUTO_DECLINE = "AUTO_DECLINE"


class ReviewQueue(str, Enum):
    AUTO_PROCESS = "AUTO_PROCESS"
    STANDARD_REVIEW = "STANDARD_REVIEW"
    SENIOR_REVIEW = "SENIOR_REVIEW"
    FRAUD_INVESTIGATION = "FRAUD_INVESTIGATION"
    MEDICAL_DIRECTOR = "MEDICAL_DIRECTOR"
    COMPLIANCE_REVIEW = "COMPLIANCE_REVIEW"


class DecisionPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# =============================================================================
# CLAIM DATA STRUCTURES
# =============================================================================

@dataclass
class ProcedureCode:
    """Procedure/service code on a claim"""
    code: str
    code_type: str  # CPT, HCPCS, ICD10_PCS, CDT, NDC
    quantity: int
    modifiers: List[str] = field(default_factory=list)
    line_amount: Optional[float] = None


@dataclass
class DiagnosisCode:
    """Diagnosis code on a claim"""
    code: str
    code_type: str  # ICD10_CM, ICD9_CM
    sequence: int  # 1 = primary diagnosis


@dataclass
class ClaimData:
    """
    Sanitized claim data structure.
    PII is hashed/masked before reaching this point.
    """
    # Identifiers
    claim_id: str
    policy_id: str
    provider_id: str
    member_id_hash: str  # SHA-256 hash of member ID
    
    # Codes
    procedure_codes: List[ProcedureCode]
    diagnosis_codes: List[DiagnosisCode]
    
    # Amounts
    billed_amount: float
    
    # Dates
    service_date: date
    service_date_end: Optional[date] = None
    submission_timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Classification
    claim_type: ClaimType = ClaimType.PROFESSIONAL
    facility_type: Optional[FacilityType] = None
    place_of_service: Optional[str] = None
    
    # Additional data
    admission_date: Optional[date] = None
    discharge_date: Optional[date] = None
    drg_code: Optional[str] = None
    referring_provider_id: Optional[str] = None
    prior_auth_number: Optional[str] = None
    network_status: NetworkStatus = NetworkStatus.UNKNOWN
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def compute_hash(self) -> str:
        """Compute deterministic hash of claim data"""
        content = json.dumps({
            'claim_id': self.claim_id,
            'billed_amount': self.billed_amount,
            'service_date': self.service_date.isoformat(),
            'procedure_codes': [p.code for p in self.procedure_codes],
            'diagnosis_codes': [d.code for d in self.diagnosis_codes]
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()


@dataclass
class PolicyData:
    """Policy information for coverage validation"""
    policy_id: str
    status: str  # ACTIVE, TERMINATED, SUSPENDED
    effective_date: date
    termination_date: Optional[date]
    covered_members: List[str]  # Hashed member IDs
    covered_benefits: List[str]
    network_ids: List[str]
    annual_maximum: Optional[float]
    lifetime_maximum: Optional[float]
    deductible: float = 0.0
    pre_existing_waiting_days: int = 0


@dataclass
class ProviderData:
    """Provider information for eligibility checks"""
    provider_id: str
    status: str  # ACTIVE, SUSPENDED, TERMINATED
    effective_date: date
    termination_date: Optional[date]
    network_id: str
    license_status: str
    license_expiry: Optional[date]
    license_types: List[str]
    specialties: List[str]
    contract_id: Optional[str] = None


@dataclass
class MemberHistory:
    """Historical claim data for a member"""
    member_id_hash: str
    claims_30d: int = 0
    claims_90d: int = 0
    claims_365d: int = 0
    total_billed_30d: float = 0.0
    total_billed_90d: float = 0.0
    avg_claim_amount: float = 0.0
    std_claim_amount: float = 0.0
    unique_providers_30d: int = 0
    unique_providers_90d: int = 0
    has_fraud_flag: bool = False
    denial_rate: float = 0.0


@dataclass
class ProviderHistory:
    """Historical claim data for a provider"""
    provider_id: str
    claims_30d: int = 0
    claims_90d: int = 0
    total_billed_30d: float = 0.0
    avg_claim_amount: float = 0.0
    std_claim_amount: float = 0.0
    unique_members_30d: int = 0
    denial_rate: float = 0.0
    fraud_rate: float = 0.0
    peer_percentile: float = 0.5


# =============================================================================
# RULE ENGINE STRUCTURES
# =============================================================================

@dataclass
class RuleDefinition:
    """Immutable rule definition"""
    rule_id: str
    version: str
    name: str
    description: str
    category: RuleCategory
    severity: RuleSeverity
    enabled: bool
    
    # Rule logic
    condition_expression: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    # Applicability
    applies_to_claim_types: List[str] = field(default_factory=lambda: ["ALL"])
    applies_to_jurisdictions: List[str] = field(default_factory=lambda: ["ALL"])
    
    # Metadata
    effective_date: datetime = field(default_factory=datetime.utcnow)
    expiration_date: Optional[datetime] = None
    created_by: str = "system"
    created_at: datetime = field(default_factory=datetime.utcnow)
    documentation_url: Optional[str] = None
    
    # Audit
    checksum: str = ""
    
    def __post_init__(self):
        if not self.checksum:
            self.checksum = self._compute_checksum()
    
    def _compute_checksum(self) -> str:
        """Compute SHA-256 checksum of rule logic"""
        content = json.dumps({
            'rule_id': self.rule_id,
            'version': self.version,
            'condition_expression': self.condition_expression,
            'parameters': self.parameters
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()


@dataclass
class RuleResult:
    """Result of evaluating a single rule"""
    rule_id: str
    rule_version: str
    rule_name: str
    category: RuleCategory
    outcome: RuleOutcome
    severity: RuleSeverity
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    execution_time_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # For debugging and audit
    input_snapshot: Dict[str, Any] = field(default_factory=dict)
    expression_evaluated: str = ""
    parameter_values: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RuleEngineResult:
    """Aggregated result from rule engine"""
    aggregate_outcome: RuleOutcome
    rules_evaluated: int
    rules_passed: int
    rules_failed: int
    rules_flagged: int
    rules_skipped: int
    
    triggered_rules: List[RuleResult]
    all_results: List[RuleResult]
    
    engine_version: str
    ruleset_version: str
    execution_time_ms: float
    timestamp: datetime = field(default_factory=datetime.utcnow)


# =============================================================================
# ML ENGINE STRUCTURES
# =============================================================================

@dataclass
class ModelInferenceResult:
    """Result from a single ML model inference"""
    model_id: str
    model_version: str
    model_hash: str
    
    risk_score: float  # 0.0 - 1.0
    confidence: float  # 0.0 - 1.0
    
    feature_contributions: List[Dict[str, Any]] = field(default_factory=list)
    anomaly_indicators: List[Dict[str, Any]] = field(default_factory=list)
    
    inference_time_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class MLEngineResult:
    """Aggregated result from ML engine"""
    combined_risk_score: float
    combined_confidence: float
    
    model_results: List[ModelInferenceResult]
    
    top_risk_factors: List[Dict[str, Any]]
    anomaly_summary: List[Dict[str, Any]]
    
    recommendation: str  # HIGH_RISK, MEDIUM_RISK, LOW_RISK
    requires_review: bool
    
    engine_version: str
    execution_time_ms: float
    timestamp: datetime = field(default_factory=datetime.utcnow)


# =============================================================================
# DECISION ENGINE STRUCTURES
# =============================================================================

@dataclass
class ClaimIntelligenceReport:
    """Final output of Decision Synthesis Engine"""
    
    # Identifiers
    analysis_id: str
    claim_id: str
    timestamp: datetime
    
    # Decision
    recommendation: FinalRecommendation
    confidence_score: float
    risk_score: float
    
    # Queue assignment
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
    related_claims: List[str] = field(default_factory=list)
    historical_context: Dict[str, Any] = field(default_factory=dict)
    
    # Audit
    decision_trace: Dict[str, Any] = field(default_factory=dict)
    processing_time_ms: float = 0.0


# =============================================================================
# AUDIT STRUCTURES
# =============================================================================

@dataclass
class AuditEvent:
    """Immutable audit event structure"""
    
    # Event identification
    event_id: str
    event_type: str
    event_category: str
    
    # Timestamp
    timestamp: datetime
    
    # Actor information
    actor_type: str
    actor_id: str
    
    # Action details
    action: str
    resource_type: str
    resource_id: str
    
    # Request context
    request_id: str
    
    # Optional fields with defaults
    timezone: str = "UTC"
    actor_role: Optional[str] = None
    actor_ip: Optional[str] = None
    session_id: Optional[str] = None
    
    # Context (optional with defaults)
    previous_state: Optional[Dict] = None
    new_state: Optional[Dict] = None
    change_summary: Optional[str] = None
    
    # Security context
    authentication_method: str = "unknown"
    authorization_decision: str = "ALLOW"
    
    # Integrity
    sequence_number: int = 0
    previous_hash: str = ""
    event_hash: str = ""
    
    def compute_hash(self) -> str:
        """Compute SHA-256 hash of event"""
        content = json.dumps({
            'event_id': self.event_id,
            'event_type': self.event_type,
            'timestamp': self.timestamp.isoformat(),
            'actor_id': self.actor_id,
            'action': self.action,
            'resource_type': self.resource_type,
            'resource_id': self.resource_id,
            'previous_hash': self.previous_hash,
            'sequence_number': self.sequence_number
        }, sort_keys=True)
        return f"sha256:{hashlib.sha256(content.encode()).hexdigest()}"

