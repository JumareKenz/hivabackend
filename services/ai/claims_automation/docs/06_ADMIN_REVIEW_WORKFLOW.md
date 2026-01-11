# Admin Review Workflow & Portal Specification

**Version:** 1.0.0  
**Date:** January 7, 2026  
**Classification:** CONFIDENTIAL - Technical Specification

---

## 1. Overview

The Admin Review Portal provides a human-in-the-loop interface for claims requiring manual review. It is hosted separately from the backend and AI engine, communicating only through secure APIs. All admin actions are logged, timestamped, and immutable.

### 1.1 Core Principles

| Principle | Implementation |
|-----------|-------------|
| **Separation of Concerns** | Portal hosted in separate DMZ |
| **Audit Everything** | Every action logged immutably |
| **Role-Based Access** | Strict RBAC enforcement |
| **Decision Traceability** | Every decision linked to reviewer |
| **No Direct DB Access** | All actions through API only |
| **Session Security** | MFA, session timeout, audit trail |

---

## 2. User Roles & Permissions

### 2.1 Role Hierarchy

```
                              ADMIN PORTAL ROLE HIERARCHY
    ════════════════════════════════════════════════════════════════

                              ┌─────────────────────┐
                              │   SYSTEM ADMIN      │
                              │   (Infrastructure)  │
                              └──────────┬──────────┘
                                         │
                    ┌────────────────────┼────────────────────┐
                    │                    │                    │
                    ▼                    ▼                    ▼
          ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
          │ COMPLIANCE      │  │ FRAUD           │  │ MEDICAL         │
          │ OFFICER         │  │ DIRECTOR        │  │ DIRECTOR        │
          │                 │  │                 │  │                 │
          │ • Audit access  │  │ • Fraud cases   │  │ • Medical cases │
          │ • Policy config │  │ • Escalations   │  │ • Clinical edits│
          │ • Reports       │  │ • Investigations│  │ • Overrides     │
          └────────┬────────┘  └────────┬────────┘  └────────┬────────┘
                   │                    │                    │
                   └────────────────────┼────────────────────┘
                                        │
                              ┌─────────▼─────────┐
                              │    SUPERVISOR     │
                              │                   │
                              │ • Team management │
                              │ • Escalation recv │
                              │ • Quality review  │
                              │ • Override limits │
                              └─────────┬─────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    │                   │                   │
                    ▼                   ▼                   ▼
          ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
          │ SENIOR          │ │ FRAUD           │ │ CLAIMS          │
          │ PROCESSOR       │ │ INVESTIGATOR    │ │ PROCESSOR       │
          │                 │ │                 │ │                 │
          │ • High value    │ │ • Fraud queue   │ │ • Standard queue│
          │ • Complex cases │ │ • Investigation │ │ • Basic review  │
          │ • Escalation    │ │ • SIU referrals │ │ • Limited auth  │
          └─────────────────┘ └─────────────────┘ └─────────────────┘

    ════════════════════════════════════════════════════════════════
```

### 2.2 Permission Matrix

```yaml
permissions:
  CLAIMS_PROCESSOR:
    queues:
      - STANDARD_REVIEW
    actions:
      - VIEW_CLAIM
      - APPROVE_CLAIM
      - DECLINE_CLAIM
      - REQUEST_INFO
      - ESCALATE
    limits:
      max_approve_amount: 50000
      can_override_rules: false
      can_override_ml: false
    
  SENIOR_PROCESSOR:
    queues:
      - STANDARD_REVIEW
      - SENIOR_REVIEW
    actions:
      - VIEW_CLAIM
      - APPROVE_CLAIM
      - DECLINE_CLAIM
      - REQUEST_INFO
      - ESCALATE
      - OVERRIDE_MINOR_FLAG
    limits:
      max_approve_amount: 500000
      can_override_rules: true  # Minor only
      can_override_ml: false
    
  FRAUD_INVESTIGATOR:
    queues:
      - STANDARD_REVIEW
      - SENIOR_REVIEW
      - FRAUD_INVESTIGATION
    actions:
      - VIEW_CLAIM
      - APPROVE_CLAIM
      - DECLINE_CLAIM
      - REQUEST_INFO
      - ESCALATE
      - OVERRIDE_MINOR_FLAG
      - FLAG_FOR_SIU
      - VIEW_PROVIDER_HISTORY
      - VIEW_MEMBER_HISTORY
    limits:
      max_approve_amount: 500000
      can_override_rules: true
      can_override_ml: true  # With justification
    
  SUPERVISOR:
    queues:
      - STANDARD_REVIEW
      - SENIOR_REVIEW
      - FRAUD_INVESTIGATION
    actions:
      - VIEW_CLAIM
      - APPROVE_CLAIM
      - DECLINE_CLAIM
      - REQUEST_INFO
      - ESCALATE
      - OVERRIDE_MINOR_FLAG
      - OVERRIDE_MAJOR_FLAG
      - REASSIGN_CLAIM
      - VIEW_TEAM_METRICS
      - QUALITY_REVIEW
    limits:
      max_approve_amount: 1000000
      can_override_rules: true
      can_override_ml: true
    
  MEDICAL_DIRECTOR:
    queues:
      - MEDICAL_DIRECTOR
      - SENIOR_REVIEW
    actions:
      - VIEW_CLAIM
      - APPROVE_CLAIM
      - DECLINE_CLAIM
      - MEDICAL_OVERRIDE
      - CLINICAL_EDIT
      - PEER_REVIEW_REQUEST
    limits:
      max_approve_amount: 5000000
      can_override_rules: true
      can_override_ml: true
      can_override_medical: true
    
  FRAUD_DIRECTOR:
    queues:
      - FRAUD_INVESTIGATION
      - SENIOR_REVIEW
    actions:
      - VIEW_CLAIM
      - APPROVE_CLAIM
      - DECLINE_CLAIM
      - SIU_REFERRAL
      - INVESTIGATION_COMPLETE
      - PROVIDER_SUSPENSION
      - MEMBER_SUSPENSION
    limits:
      max_approve_amount: unlimited
      can_override_rules: true
      can_override_ml: true
    
  COMPLIANCE_OFFICER:
    queues:
      - COMPLIANCE_REVIEW
      - "*"  # Read-only all queues
    actions:
      - VIEW_CLAIM
      - VIEW_AUDIT_LOG
      - GENERATE_REPORT
      - EXPORT_DATA
      - CONFIGURE_RULES
    limits:
      read_only_mode: true
      can_export_pii: true  # With audit
```

---

## 3. Review Workflow

### 3.1 Claim Review Lifecycle

```
                         CLAIM REVIEW LIFECYCLE
    ════════════════════════════════════════════════════════════════

    ┌─────────────────┐
    │  CLAIM QUEUED   │
    │  (From AI)      │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐     ┌─────────────────┐
    │  UNASSIGNED     │────▶│  ASSIGNED       │
    │                 │     │  (To Reviewer)  │
    └─────────────────┘     └────────┬────────┘
                                     │
                    ┌────────────────┼────────────────┐
                    │                │                │
                    ▼                ▼                ▼
          ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
          │  IN_REVIEW      │ │  PENDING_INFO   │ │  ESCALATED      │
          │  (Active work)  │ │  (Waiting)      │ │  (Higher tier)  │
          └────────┬────────┘ └────────┬────────┘ └────────┬────────┘
                   │                   │                   │
                   │    ┌──────────────┘                   │
                   │    │                                  │
                   ▼    ▼                                  │
          ┌─────────────────┐                              │
          │  DECISION       │◀─────────────────────────────┘
          │  PENDING        │
          └────────┬────────┘
                   │
         ┌─────────┼─────────┐
         │         │         │
         ▼         ▼         ▼
    ┌─────────┐ ┌─────────┐ ┌─────────┐
    │ APPROVED│ │ DECLINED│ │ PARTIAL │
    └────┬────┘ └────┬────┘ └────┬────┘
         │         │         │
         └─────────┼─────────┘
                   │
                   ▼
          ┌─────────────────┐
          │  COMPLETED      │
          │  (Final)        │
          └────────┬────────┘
                   │
                   ▼
          ┌─────────────────┐
          │  FEEDBACK       │
          │  SUBMITTED      │
          │  (Training)     │
          └─────────────────┘

    ════════════════════════════════════════════════════════════════
```

### 3.2 State Machine Implementation

```python
from enum import Enum
from typing import Optional, List
from datetime import datetime, timedelta

class ReviewState(Enum):
    QUEUED = "QUEUED"
    UNASSIGNED = "UNASSIGNED"
    ASSIGNED = "ASSIGNED"
    IN_REVIEW = "IN_REVIEW"
    PENDING_INFO = "PENDING_INFO"
    ESCALATED = "ESCALATED"
    DECISION_PENDING = "DECISION_PENDING"
    APPROVED = "APPROVED"
    DECLINED = "DECLINED"
    PARTIAL = "PARTIAL"
    COMPLETED = "COMPLETED"
    FEEDBACK_SUBMITTED = "FEEDBACK_SUBMITTED"

class ReviewAction(Enum):
    ASSIGN = "ASSIGN"
    START_REVIEW = "START_REVIEW"
    REQUEST_INFO = "REQUEST_INFO"
    RECEIVE_INFO = "RECEIVE_INFO"
    ESCALATE = "ESCALATE"
    SUBMIT_DECISION = "SUBMIT_DECISION"
    APPROVE = "APPROVE"
    DECLINE = "DECLINE"
    PARTIAL_APPROVE = "PARTIAL_APPROVE"
    COMPLETE = "COMPLETE"
    SUBMIT_FEEDBACK = "SUBMIT_FEEDBACK"

class ReviewStateMachine:
    """
    State machine for claim review workflow.
    Enforces valid state transitions.
    """
    
    VALID_TRANSITIONS = {
        ReviewState.QUEUED: [
            (ReviewAction.ASSIGN, ReviewState.ASSIGNED),
        ],
        ReviewState.UNASSIGNED: [
            (ReviewAction.ASSIGN, ReviewState.ASSIGNED),
        ],
        ReviewState.ASSIGNED: [
            (ReviewAction.START_REVIEW, ReviewState.IN_REVIEW),
            (ReviewAction.ESCALATE, ReviewState.ESCALATED),
        ],
        ReviewState.IN_REVIEW: [
            (ReviewAction.REQUEST_INFO, ReviewState.PENDING_INFO),
            (ReviewAction.ESCALATE, ReviewState.ESCALATED),
            (ReviewAction.SUBMIT_DECISION, ReviewState.DECISION_PENDING),
        ],
        ReviewState.PENDING_INFO: [
            (ReviewAction.RECEIVE_INFO, ReviewState.IN_REVIEW),
            (ReviewAction.ESCALATE, ReviewState.ESCALATED),
        ],
        ReviewState.ESCALATED: [
            (ReviewAction.ASSIGN, ReviewState.ASSIGNED),
        ],
        ReviewState.DECISION_PENDING: [
            (ReviewAction.APPROVE, ReviewState.APPROVED),
            (ReviewAction.DECLINE, ReviewState.DECLINED),
            (ReviewAction.PARTIAL_APPROVE, ReviewState.PARTIAL),
        ],
        ReviewState.APPROVED: [
            (ReviewAction.COMPLETE, ReviewState.COMPLETED),
        ],
        ReviewState.DECLINED: [
            (ReviewAction.COMPLETE, ReviewState.COMPLETED),
        ],
        ReviewState.PARTIAL: [
            (ReviewAction.COMPLETE, ReviewState.COMPLETED),
        ],
        ReviewState.COMPLETED: [
            (ReviewAction.SUBMIT_FEEDBACK, ReviewState.FEEDBACK_SUBMITTED),
        ],
    }
    
    def __init__(self, claim_id: str, initial_state: ReviewState = ReviewState.QUEUED):
        self.claim_id = claim_id
        self.current_state = initial_state
        self.state_history: List[dict] = []
        self._record_state_change(None, initial_state, None, None)
    
    def can_transition(self, action: ReviewAction) -> bool:
        """Check if action is valid from current state."""
        valid = self.VALID_TRANSITIONS.get(self.current_state, [])
        return any(a == action for a, _ in valid)
    
    def transition(
        self,
        action: ReviewAction,
        user_id: str,
        details: dict = None
    ) -> ReviewState:
        """
        Execute state transition.
        Raises InvalidTransitionError if not allowed.
        """
        valid = self.VALID_TRANSITIONS.get(self.current_state, [])
        
        for valid_action, next_state in valid:
            if valid_action == action:
                previous_state = self.current_state
                self.current_state = next_state
                self._record_state_change(previous_state, next_state, action, user_id, details)
                return next_state
        
        raise InvalidTransitionError(
            f"Cannot perform {action.value} from state {self.current_state.value}"
        )
    
    def _record_state_change(
        self,
        from_state: Optional[ReviewState],
        to_state: ReviewState,
        action: Optional[ReviewAction],
        user_id: Optional[str],
        details: dict = None
    ) -> None:
        """Record state change in history."""
        self.state_history.append({
            'from_state': from_state.value if from_state else None,
            'to_state': to_state.value,
            'action': action.value if action else None,
            'user_id': user_id,
            'timestamp': datetime.utcnow().isoformat(),
            'details': details or {}
        })
```

---

## 4. Admin Portal UI Components

### 4.1 Dashboard Layout

```
┌────────────────────────────────────────────────────────────────────────────┐
│  ╔══════════════════════════════════════════════════════════════════════╗  │
│  ║  🏥 Claims Review Portal              [Sarah Chen ▼] [🔔 3] [⚙️] [🚪] ║  │
│  ╚══════════════════════════════════════════════════════════════════════╝  │
│                                                                            │
│  ┌─────────────────┐  ┌────────────────────────────────────────────────┐  │
│  │                 │  │                                                │  │
│  │  📊 DASHBOARD   │  │  MY QUEUE (12)           ⏱️ SLA: 4h avg       │  │
│  │  ─────────────  │  │  ════════════════════════════════════════════  │  │
│  │                 │  │                                                │  │
│  │  📋 My Queue    │  │  ┌────────────────────────────────────────┐  │  │
│  │     (12)        │  │  │ 🔴 CLM-2026-123456  $12,450  CRITICAL  │  │  │
│  │                 │  │  │    Fraud Investigation • 2h remaining   │  │  │
│  │  📥 Unassigned  │  │  └────────────────────────────────────────┘  │  │
│  │     (45)        │  │                                                │  │
│  │                 │  │  ┌────────────────────────────────────────┐  │  │
│  │  🔍 Search      │  │  │ 🟡 CLM-2026-123457  $5,200   HIGH      │  │  │
│  │                 │  │  │    Senior Review • 12h remaining        │  │  │
│  │  📈 Reports     │  │  └────────────────────────────────────────┘  │  │
│  │                 │  │                                                │  │
│  │  ⚙️ Settings    │  │  ┌────────────────────────────────────────┐  │  │
│  │                 │  │  │ 🟢 CLM-2026-123458  $890    MEDIUM     │  │  │
│  │  ─────────────  │  │  │    Standard Review • 36h remaining     │  │  │
│  │                 │  │  └────────────────────────────────────────┘  │  │
│  │  QUEUES         │  │                                                │  │
│  │  ─────────────  │  │  ... (9 more)                                 │  │
│  │  Standard (234) │  │                                                │  │
│  │  Senior (89)    │  ├────────────────────────────────────────────────┤  │
│  │  Fraud (23)     │  │                                                │  │
│  │  Medical (12)   │  │  📊 TODAY'S METRICS                           │  │
│  │  Compliance (5) │  │  ════════════════════════════════════════════  │  │
│  │                 │  │                                                │  │
│  │                 │  │  Reviewed: 24    Approved: 18    Declined: 4  │  │
│  │                 │  │  Pending: 12     Escalated: 2    Avg Time: 8m │  │
│  │                 │  │                                                │  │
│  └─────────────────┘  └────────────────────────────────────────────────┘  │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Claim Review Screen

```
┌────────────────────────────────────────────────────────────────────────────┐
│  ◄ Back to Queue    CLM-2026-000123456    🔴 CRITICAL    ⏱️ 2h remaining  │
│  ══════════════════════════════════════════════════════════════════════════│
│                                                                            │
│  ┌──────────────────────────────────┬─────────────────────────────────┐  │
│  │  CLAIM DETAILS                   │  AI ANALYSIS SUMMARY            │  │
│  │  ────────────────────────────    │  ────────────────────────────   │  │
│  │                                  │                                  │  │
│  │  Policy: POL-ABC12345            │  Recommendation: MANUAL_REVIEW   │  │
│  │  Member: M-*****7890             │  Confidence: 78%                 │  │
│  │  Provider: PRV-XYZ789            │  Risk Score: 0.65 (MEDIUM)      │  │
│  │  Facility: Outpatient Hospital   │                                  │  │
│  │                                  │  ┌─────────────────────────┐    │  │
│  │  Service Date: 2026-01-05        │  │    Risk Meter           │    │  │
│  │  Submission: 2026-01-07          │  │  ░░░░░░░▓▓▓░░░░░░      │    │  │
│  │                                  │  │  0    0.65    1.0      │    │  │
│  │  Billed Amount: $12,450.00       │  └─────────────────────────┘    │  │
│  │                                  │                                  │  │
│  │  ──────────────────────────────  │  Rule Engine: FLAG (3 flags)    │  │
│  │  PROCEDURE CODES                 │  ML Engine: MEDIUM_RISK         │  │
│  │  ──────────────────────────────  │                                  │  │
│  │  99223 - Initial hospital care   │                                  │  │
│  │  94640 - Aerosol treatment       │                                  │  │
│  │  71046 - Chest X-ray             │                                  │  │
│  │                                  │                                  │  │
│  │  ──────────────────────────────  │                                  │  │
│  │  DIAGNOSIS CODES                 │                                  │  │
│  │  ──────────────────────────────  │                                  │  │
│  │  J18.9 - Pneumonia (Primary)     │                                  │  │
│  │  R05 - Cough                     │                                  │  │
│  │                                  │                                  │  │
│  └──────────────────────────────────┴─────────────────────────────────┘  │
│                                                                            │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │  🚨 RISK INDICATORS                                                  │ │
│  │  ════════════════════════════════════════════════════════════════════│ │
│  │                                                                       │ │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │ │
│  │  │ 🔴 RULE: TAR-004 - Amount exceeds 95th percentile               │ │ │
│  │  │    Billed: $12,450  |  95th %ile: $8,200  |  Ratio: 1.52x       │ │ │
│  │  │    [View Fee Schedule] [Override ▼]                              │ │ │
│  │  └─────────────────────────────────────────────────────────────────┘ │ │
│  │                                                                       │ │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │ │
│  │  │ 🟡 RULE: DUP-002 - Possible duplicate detected                  │ │ │
│  │  │    Similar claim: CLM-2026-000123400 (same day, same provider)  │ │ │
│  │  │    [View Similar Claim] [Mark Not Duplicate]                     │ │ │
│  │  └─────────────────────────────────────────────────────────────────┘ │ │
│  │                                                                       │ │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │ │
│  │  │ 🟡 ML: Cost Anomaly - 2.3 std dev above provider average        │ │ │
│  │  │    Provider Avg: $4,200  |  This claim: $12,450                 │ │ │
│  │  │    [View Provider History]                                       │ │ │
│  │  └─────────────────────────────────────────────────────────────────┘ │ │
│  │                                                                       │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │  📜 SUGGESTED ACTIONS                                                │ │
│  │  ────────────────────────────────────────────────────────────────────│ │
│  │  • Review all flagged risk indicators                                │ │
│  │  • Verify billed amounts against fee schedule                        │ │
│  │  • Check for potential duplicate claims                              │ │
│  │  • Review provider claim history for patterns                        │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │  DECISION                                                            │  │
│  │  ═══════════════════════════════════════════════════════════════════ │  │
│  │                                                                       │  │
│  │  [✓ APPROVE]  [✓ APPROVE PARTIAL]  [✗ DECLINE]  [↑ ESCALATE]        │  │
│  │                                                                       │  │
│  │  Approved Amount: $____________    (Billed: $12,450.00)              │  │
│  │                                                                       │  │
│  │  Adjustment Reason: [Select ▼]                                       │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │  │
│  │  │ Full Approval                                                    │ │  │
│  │  │ Fee Schedule Adjustment                                          │ │  │
│  │  │ Bundling Adjustment                                              │ │  │
│  │  │ Medical Necessity (Partial)                                      │ │  │
│  │  │ Coverage Limitation                                              │ │  │
│  │  │ Duplicate Service                                                │ │  │
│  │  └─────────────────────────────────────────────────────────────────┘ │  │
│  │                                                                       │  │
│  │  Justification (Required):                                           │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │  │
│  │  │                                                                  │ │  │
│  │  │                                                                  │ │  │
│  │  │                                                                  │ │  │
│  │  └─────────────────────────────────────────────────────────────────┘ │  │
│  │                                                                       │  │
│  │  Override Flags: [TAR-004 ☐] [DUP-002 ☐]                            │  │
│  │  Override Justification (if checked): __________________________     │  │
│  │                                                                       │  │
│  │                              [Submit Decision]                        │  │
│  │                                                                       │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Review Decision Processing

### 5.1 Decision Handler

```python
class ReviewDecisionHandler:
    """
    Handles admin review decisions.
    Validates, records, and publishes decisions.
    """
    
    def __init__(self, config: DecisionHandlerConfig):
        self.config = config
        self.state_machine = ReviewStateMachine
        self.audit_logger = ReviewAuditLogger()
        self.event_publisher = EventPublisher()
        self.permission_checker = PermissionChecker()
    
    async def submit_decision(
        self,
        claim_id: str,
        decision: ReviewDecision,
        user: User
    ) -> DecisionResult:
        """
        Process and record a review decision.
        """
        # Step 1: Validate permissions
        await self._validate_permissions(user, decision)
        
        # Step 2: Validate decision data
        await self._validate_decision(decision)
        
        # Step 3: Validate overrides
        if decision.override_flags:
            await self._validate_overrides(decision.override_flags, user)
        
        # Step 4: Start transaction
        async with self.db.transaction():
            # Record decision
            review_record = await self._create_review_record(
                claim_id, decision, user
            )
            
            # Update state machine
            state_machine = await self._load_state_machine(claim_id)
            state_machine.transition(
                ReviewAction.SUBMIT_DECISION,
                user.user_id,
                {'decision': decision.decision}
            )
            
            # Apply final decision state
            if decision.decision == 'APPROVE':
                state_machine.transition(ReviewAction.APPROVE, user.user_id)
            elif decision.decision == 'DECLINE':
                state_machine.transition(ReviewAction.DECLINE, user.user_id)
            elif decision.decision == 'PARTIAL':
                state_machine.transition(ReviewAction.PARTIAL_APPROVE, user.user_id)
            
            state_machine.transition(ReviewAction.COMPLETE, user.user_id)
            
            # Save state
            await self._save_state_machine(state_machine)
            
            # Log audit record
            await self.audit_logger.log_decision(
                claim_id=claim_id,
                decision=decision,
                user=user,
                review_record=review_record
            )
        
        # Step 5: Publish event (outside transaction)
        await self._publish_decision_event(claim_id, decision, user, review_record)
        
        # Step 6: Submit training feedback
        await self._submit_training_feedback(claim_id, decision, review_record)
        
        return DecisionResult(
            review_id=review_record.review_id,
            claim_id=claim_id,
            decision=decision.decision,
            status='COMPLETED',
            timestamp=datetime.utcnow()
        )
    
    async def _validate_permissions(
        self,
        user: User,
        decision: ReviewDecision
    ) -> None:
        """Validate user has permission for this decision."""
        # Check role allows decision type
        if not self.permission_checker.can_make_decision(user.role, decision.decision):
            raise PermissionDeniedError(
                f"Role {user.role} cannot make {decision.decision} decisions"
            )
        
        # Check amount limits
        if decision.approved_amount:
            max_amount = self.permission_checker.get_max_approve_amount(user.role)
            if decision.approved_amount > max_amount:
                raise PermissionDeniedError(
                    f"Approved amount ${decision.approved_amount} exceeds limit ${max_amount}"
                )
    
    async def _validate_overrides(
        self,
        overrides: List[FlagOverride],
        user: User
    ) -> None:
        """Validate override permissions."""
        for override in overrides:
            flag_severity = await self._get_flag_severity(override.flag_type)
            
            if flag_severity == 'MAJOR':
                if not self.permission_checker.can_override_major(user.role):
                    raise PermissionDeniedError(
                        f"Role {user.role} cannot override MAJOR flags"
                    )
            
            # Require justification for all overrides
            if not override.justification or len(override.justification) < 20:
                raise ValidationError(
                    f"Override for {override.flag_type} requires justification (min 20 chars)"
                )
    
    async def _publish_decision_event(
        self,
        claim_id: str,
        decision: ReviewDecision,
        user: User,
        review_record: ReviewRecord
    ) -> None:
        """Publish decision event to message queue."""
        event = ClaimReviewedEvent(
            envelope_version="1.0.0",
            claim_id=claim_id,
            analysis_id=review_record.analysis_id,
            review_id=review_record.review_id,
            timestamp=datetime.utcnow(),
            decision=decision.decision,
            decision_amount=decision.approved_amount,
            adjustment_reason=decision.adjustment_reason,
            notes=decision.justification,
            override_flags=[
                {
                    'flag_type': o.flag_type,
                    'original_value': o.original_value,
                    'override_value': o.override_value,
                    'justification': o.justification
                }
                for o in (decision.override_flags or [])
            ],
            reviewer={
                'user_id': user.user_id,
                'role': user.role.value,
                'timestamp': datetime.utcnow().isoformat(),
                'session_id': user.session_id
            },
            review_duration_seconds=review_record.duration_seconds,
            signature=self._sign_event(review_record)
        )
        
        await self.event_publisher.publish(
            topic='claims.reviewed',
            event=event
        )
    
    async def _submit_training_feedback(
        self,
        claim_id: str,
        decision: ReviewDecision,
        review_record: ReviewRecord
    ) -> None:
        """Submit feedback for ML model training."""
        # Determine feedback type
        analysis = await self._get_claim_analysis(claim_id)
        
        ai_recommended = analysis.recommendation
        human_decided = decision.decision
        
        if ai_recommended == human_decided:
            feedback_type = 'CORRECT_PREDICTION'
        elif ai_recommended == 'AUTO_APPROVE' and human_decided == 'DECLINE':
            feedback_type = 'FALSE_NEGATIVE'
        elif ai_recommended == 'AUTO_DECLINE' and human_decided == 'APPROVE':
            feedback_type = 'FALSE_POSITIVE'
        else:
            feedback_type = 'PARTIAL_AGREEMENT'
        
        # Check for fraud determination
        is_fraud = decision.adjustment_reason in [
            'FRAUD_DENIAL',
            'DUPLICATE_DENIAL'
        ]
        
        feedback = ClaimFeedbackEvent(
            envelope_version="1.0.0",
            feedback_id=str(uuid.uuid4()),
            claim_id=claim_id,
            analysis_id=analysis.analysis_id,
            review_id=review_record.review_id,
            timestamp=datetime.utcnow(),
            feedback_type=feedback_type,
            ground_truth={
                'final_decision': human_decided,
                'is_fraudulent': is_fraud,
                'fraud_type': self._determine_fraud_type(decision) if is_fraud else 'NONE',
                'confidence': 1.0  # Human decisions are ground truth
            },
            model_performance={
                'prediction_correct': feedback_type == 'CORRECT_PREDICTION',
                'risk_score_accuracy': None  # Calculated later
            },
            metadata={
                'reviewer_experience_level': review_record.reviewer_experience,
                'review_difficulty': self._assess_difficulty(analysis),
                'review_duration_seconds': review_record.duration_seconds
            }
        )
        
        await self.event_publisher.publish(
            topic='claims.feedback',
            event=feedback
        )
```

---

## 6. SLA Management

### 6.1 SLA Tracker

```python
class SLATracker:
    """
    Tracks and enforces SLA deadlines for review queue.
    """
    
    def __init__(self, config: SLAConfig):
        self.config = config
        self.alert_manager = AlertManager()
    
    def calculate_deadline(
        self,
        priority: DecisionPriority,
        queue: ReviewQueue,
        queued_at: datetime
    ) -> datetime:
        """Calculate SLA deadline based on priority and queue."""
        sla_hours = self.config.get_sla_hours(priority, queue)
        
        # Adjust for business hours if configured
        if self.config.business_hours_only:
            return self._add_business_hours(queued_at, sla_hours)
        else:
            return queued_at + timedelta(hours=sla_hours)
    
    def check_sla_status(self, claim: ReviewQueueItem) -> SLAStatus:
        """Check SLA status for a claim."""
        now = datetime.utcnow()
        deadline = claim.sla_deadline
        
        if now > deadline:
            return SLAStatus.BREACHED
        
        remaining = deadline - now
        total_sla = claim.sla_deadline - claim.queued_at
        
        if remaining < total_sla * 0.1:  # Less than 10% remaining
            return SLAStatus.CRITICAL
        elif remaining < total_sla * 0.25:  # Less than 25% remaining
            return SLAStatus.WARNING
        else:
            return SLAStatus.ON_TRACK
    
    async def run_sla_monitor(self) -> None:
        """Background task to monitor SLA compliance."""
        while True:
            # Check all pending claims
            pending_claims = await self._get_pending_claims()
            
            for claim in pending_claims:
                status = self.check_sla_status(claim)
                
                if status == SLAStatus.BREACHED:
                    await self._handle_sla_breach(claim)
                elif status == SLAStatus.CRITICAL:
                    await self._send_critical_alert(claim)
                elif status == SLAStatus.WARNING:
                    await self._send_warning_alert(claim)
            
            # Sleep before next check
            await asyncio.sleep(300)  # 5 minutes
    
    async def _handle_sla_breach(self, claim: ReviewQueueItem) -> None:
        """Handle SLA breach - escalate and alert."""
        # Log breach
        await self.audit_logger.log_sla_breach(claim)
        
        # Auto-escalate if configured
        if self.config.auto_escalate_on_breach:
            await self._escalate_claim(claim)
        
        # Alert supervisor
        await self.alert_manager.send_alert(
            alert_type='SLA_BREACH',
            severity='HIGH',
            claim_id=claim.claim_id,
            message=f"SLA breached for claim {claim.claim_id}",
            recipients=self._get_supervisors(claim.assigned_queue)
        )
```

---

## 7. Audit & Compliance

### 7.1 Audit Event Types

```python
class AuditEventType(Enum):
    # Authentication
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    LOGIN_FAILED = "LOGIN_FAILED"
    SESSION_TIMEOUT = "SESSION_TIMEOUT"
    
    # Queue actions
    CLAIM_ASSIGNED = "CLAIM_ASSIGNED"
    CLAIM_UNASSIGNED = "CLAIM_UNASSIGNED"
    CLAIM_ESCALATED = "CLAIM_ESCALATED"
    CLAIM_REASSIGNED = "CLAIM_REASSIGNED"
    
    # Review actions
    REVIEW_STARTED = "REVIEW_STARTED"
    REVIEW_PAUSED = "REVIEW_PAUSED"
    REVIEW_RESUMED = "REVIEW_RESUMED"
    INFO_REQUESTED = "INFO_REQUESTED"
    INFO_RECEIVED = "INFO_RECEIVED"
    
    # Decision actions
    DECISION_APPROVED = "DECISION_APPROVED"
    DECISION_DECLINED = "DECISION_DECLINED"
    DECISION_PARTIAL = "DECISION_PARTIAL"
    DECISION_ESCALATED = "DECISION_ESCALATED"
    
    # Override actions
    FLAG_OVERRIDDEN = "FLAG_OVERRIDDEN"
    RULE_OVERRIDDEN = "RULE_OVERRIDDEN"
    ML_OVERRIDDEN = "ML_OVERRIDDEN"
    
    # Admin actions
    USER_CREATED = "USER_CREATED"
    USER_MODIFIED = "USER_MODIFIED"
    ROLE_CHANGED = "ROLE_CHANGED"
    PERMISSION_CHANGED = "PERMISSION_CHANGED"
    
    # System actions
    CONFIG_CHANGED = "CONFIG_CHANGED"
    RULE_DEPLOYED = "RULE_DEPLOYED"
    MODEL_DEPLOYED = "MODEL_DEPLOYED"
    
    # Compliance
    DATA_EXPORTED = "DATA_EXPORTED"
    REPORT_GENERATED = "REPORT_GENERATED"
    AUDIT_ACCESSED = "AUDIT_ACCESSED"

class AdminAuditLogger:
    """
    Immutable audit logger for admin actions.
    All actions are logged with full context.
    """
    
    def __init__(self, db_config: DatabaseConfig):
        self.db = self._connect_db(db_config)
        self._init_audit_table()
    
    async def log_event(
        self,
        event_type: AuditEventType,
        user: User,
        resource_type: str,
        resource_id: str,
        action_details: Dict[str, Any],
        ip_address: str,
        user_agent: str
    ) -> str:
        """Log an audit event. Returns event ID."""
        event_id = str(uuid.uuid4())
        
        record = {
            'event_id': event_id,
            'event_type': event_type.value,
            'timestamp': datetime.utcnow(),
            'user_id': user.user_id,
            'user_role': user.role.value,
            'session_id': user.session_id,
            'resource_type': resource_type,
            'resource_id': resource_id,
            'action_details': action_details,
            'ip_address': ip_address,
            'user_agent': user_agent,
            'integrity_hash': None  # Set below
        }
        
        # Compute integrity hash
        record['integrity_hash'] = self._compute_hash(record)
        
        # Insert atomically
        await self._insert_audit_record(record)
        
        return event_id
    
    async def get_audit_trail(
        self,
        resource_type: str,
        resource_id: str,
        start_date: datetime = None,
        end_date: datetime = None
    ) -> List[Dict[str, Any]]:
        """Get audit trail for a resource."""
        query = """
            SELECT * FROM admin_audit_log
            WHERE resource_type = $1 AND resource_id = $2
        """
        params = [resource_type, resource_id]
        
        if start_date:
            query += " AND timestamp >= $3"
            params.append(start_date)
        
        if end_date:
            query += f" AND timestamp <= ${len(params) + 1}"
            params.append(end_date)
        
        query += " ORDER BY timestamp ASC"
        
        return await self.db.fetch(query, *params)
```

### 7.2 Compliance Reports

```python
class ComplianceReporter:
    """
    Generates compliance and audit reports.
    """
    
    async def generate_sla_report(
        self,
        start_date: datetime,
        end_date: datetime,
        queue: ReviewQueue = None
    ) -> SLAReport:
        """Generate SLA compliance report."""
        query_params = {'start': start_date, 'end': end_date}
        
        if queue:
            query_params['queue'] = queue.value
        
        # Get completion data
        completions = await self.db.fetch("""
            SELECT 
                assigned_queue,
                priority,
                COUNT(*) as total,
                SUM(CASE WHEN completed_at <= sla_deadline THEN 1 ELSE 0 END) as on_time,
                AVG(EXTRACT(EPOCH FROM (completed_at - queued_at))/3600) as avg_hours,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY 
                    EXTRACT(EPOCH FROM (completed_at - queued_at))/3600
                ) as p95_hours
            FROM review_records
            WHERE queued_at BETWEEN :start AND :end
            AND completed_at IS NOT NULL
            GROUP BY assigned_queue, priority
        """, query_params)
        
        return SLAReport(
            period_start=start_date,
            period_end=end_date,
            overall_compliance=self._calculate_compliance(completions),
            by_queue=self._group_by_queue(completions),
            by_priority=self._group_by_priority(completions),
            breaches=await self._get_breaches(start_date, end_date),
            recommendations=self._generate_recommendations(completions)
        )
    
    async def generate_reviewer_report(
        self,
        start_date: datetime,
        end_date: datetime,
        reviewer_id: str = None
    ) -> ReviewerReport:
        """Generate reviewer performance report."""
        query_params = {'start': start_date, 'end': end_date}
        
        if reviewer_id:
            query_params['reviewer'] = reviewer_id
        
        metrics = await self.db.fetch("""
            SELECT 
                reviewer_id,
                COUNT(*) as total_reviews,
                SUM(CASE WHEN decision = 'APPROVE' THEN 1 ELSE 0 END) as approvals,
                SUM(CASE WHEN decision = 'DECLINE' THEN 1 ELSE 0 END) as declines,
                AVG(review_duration_seconds) as avg_duration,
                COUNT(DISTINCT DATE(completed_at)) as active_days,
                SUM(CASE WHEN override_flags IS NOT NULL THEN 1 ELSE 0 END) as overrides
            FROM review_records
            WHERE completed_at BETWEEN :start AND :end
            GROUP BY reviewer_id
        """, query_params)
        
        return ReviewerReport(
            period_start=start_date,
            period_end=end_date,
            reviewers=metrics,
            top_performers=self._identify_top_performers(metrics),
            quality_metrics=await self._get_quality_metrics(start_date, end_date)
        )
```

---

**END OF ADMIN REVIEW WORKFLOW SPECIFICATION**


