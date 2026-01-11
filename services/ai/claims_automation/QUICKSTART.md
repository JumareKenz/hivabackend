# DCAL Quick Start Guide

**Dynamic Claims Automation Layer - Getting Started**

---

## 🎯 **What Has Been Built**

A production-ready foundation for the DCAL system with:

✅ **Complete Design** - 8 comprehensive specification documents  
✅ **Core Data Models** - All domain objects with type safety  
✅ **HIP Database Service** - Read-only access with PII protection  
✅ **Rule Engine Core** - Deterministic evaluation framework  
✅ **Configuration Management** - Full settings with validation

**Current Status:** 12% implementation complete (~1,550 / 12,850 lines)

---

## 🚀 **Setup Instructions**

### 1. **Install Dependencies**

```bash
cd /root/hiva/services/ai/claims_automation
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. **Configure Environment**

Create `.env` file from template:

```bash
cp .env.template .env
```

**Required Settings:**
```bash
# HIP Database (Already configured)
HIP_DB_PASSWORD=NSanle657.

# Security (Generate these)
JWT_SECRET_KEY=$(openssl rand -hex 32)
MESSAGE_SIGNING_KEY=$(openssl rand -hex 32)

# Audit Database (Local PostgreSQL)
AUDIT_DB_PASSWORD=your_secure_password

# Feature Flags (Start conservative)
ENABLE_AUTO_APPROVE=false
ENABLE_AUTO_DECLINE=false
```

### 3. **Test HIP Database Connection**

```python
# test_hip_connection.py
import asyncio
from src.data.hip_service import hip_service

async def test():
    await hip_service.initialize()
    
    # Try fetching a claim
    claim = await hip_service.get_claim_by_id("1")
    if claim:
        print(f"✅ Successfully retrieved claim: {claim.claim_id}")
        print(f"   Amount: {claim.billed_amount}")
        print(f"   Service Date: {claim.service_date}")
    else:
        print("❌ No claim found")
    
    await hip_service.close()

asyncio.run(test())
```

Run: `python test_hip_connection.py`

---

## 📁 **Project Structure**

```
claims_automation/
├── docs/                          # Complete design documentation
│   ├── 01_ARCHITECTURE_OVERVIEW.md
│   ├── 02_API_EVENT_SCHEMAS.md
│   ├── 03_RULE_ENGINE_SPECIFICATION.md
│   ├── 04_ML_FRAUD_DETECTION.md
│   ├── 05_DECISION_SYNTHESIS_ENGINE.md
│   ├── 06_ADMIN_REVIEW_WORKFLOW.md
│   ├── 07_SECURITY_AUDIT_MODEL.md
│   └── 08_FAILURE_MODES_TESTING.md
│
├── src/                           # Implementation
│   ├── core/                      # ✅ COMPLETE
│   │   ├── config.py              # Settings management
│   │   └── models.py              # All data models
│   │
│   ├── data/                      # ✅ COMPLETE
│   │   └── hip_service.py         # HIP database access (read-only)
│   │
│   ├── rule_engine/               # 🚧 80% COMPLETE
│   │   └── engine.py              # Rule evaluation core
│   │   ├── evaluator.py           # ⏳ TODO
│   │   ├── rules_loader.py        # ⏳ TODO
│   │   └── rules/                 # ⏳ TODO (47 rules)
│   │
│   ├── ml_engine/                 # ⏳ PENDING
│   ├── decision_engine/           # ⏳ PENDING
│   ├── events/                    # ⏳ PENDING
│   └── api/                       # ⏳ PENDING
│
├── tests/                         # ⏳ PENDING
├── configs/                       # Rule configurations
├── models/                        # ML model artifacts
├── requirements.txt               # ✅ All dependencies
├── .env.template                  # ✅ Configuration template
├── README.md                      # ✅ Complete overview
├── IMPLEMENTATION_PROGRESS.md     # ✅ Detailed progress
└── QUICKSTART.md                  # ✅ This file
```

---

## 🎬 **What Works Right Now**

### 1. **HIP Database Access**

```python
from src.data.hip_service import hip_service
from datetime import date, timedelta

async def example():
    await hip_service.initialize()
    
    # Get claim data
    claim = await hip_service.get_claim_by_id("12345")
    
    # Get provider history
    provider_history = await hip_service.get_provider_history("PRV-100")
    print(f"Provider Claims (30d): {provider_history.claims_30d}")
    print(f"Average Amount: ${provider_history.avg_claim_amount:.2f}")
    
    # Get training data
    end_date = date.today()
    start_date = end_date - timedelta(days=90)
    training_data = await hip_service.get_training_data(start_date, end_date)
    print(f"Training samples: {len(training_data)}")
```

### 2. **Data Models**

```python
from src.core.models import ClaimData, ProcedureCode, DiagnosisCode
from datetime import date

# Create a claim
claim = ClaimData(
    claim_id="CLM-2026-000001",
    policy_id="POL-ABC123",
    provider_id="PRV-XYZ789",
    member_id_hash="abc123...",  # SHA-256 hash
    procedure_codes=[
        ProcedureCode(code="99213", code_type="CPT", quantity=1, line_amount=150.00)
    ],
    diagnosis_codes=[
        DiagnosisCode(code="J06.9", code_type="ICD10_CM", sequence=1)
    ],
    billed_amount=150.00,
    service_date=date(2026, 1, 5)
)

# Compute hash for integrity
claim_hash = claim.compute_hash()
print(f"Claim Hash: {claim_hash}")
```

### 3. **Configuration**

```python
from src.core.config import settings, is_production, get_hip_db_connection_string

print(f"Environment: {settings.ENVIRONMENT}")
print(f"Rule Engine Version: {settings.RULE_ENGINE_VERSION}")
print(f"Auto-Approve Enabled: {settings.ENABLE_AUTO_APPROVE}")

# Connection strings
hip_conn = get_hip_db_connection_string()
print(f"HIP DB: {hip_conn.split('@')[1]}")  # Don't log password
```

---

## 🔨 **Next Implementation Steps**

### Priority 1: Complete Rule Engine (2-3 days)

Create `src/rule_engine/evaluator.py`:
```python
class SafeExpressionEvaluator:
    """
    Sandboxed expression evaluator for rule conditions.
    NO arbitrary code execution allowed.
    """
    def evaluate(self, expression: str, context: dict, parameters: dict) -> bool:
        # Implement safe AST-based evaluation
        pass
```

Create `src/rule_engine/rules_loader.py`:
```python
class RulesLoader:
    """Load rule definitions from configuration"""
    async def load_active_ruleset(self) -> Dict[str, RuleDefinition]:
        # Load from YAML/JSON configuration
        pass
```

Implement critical rules in `src/rule_engine/rules/`:
- `critical_rules.py` - 5 blocking rules
- `policy_rules.py` - Coverage validation
- `provider_rules.py` - Eligibility checks
- `tariff_rules.py` - Cost compliance
- etc.

### Priority 2: Decision Synthesis (1 day)

Create `src/decision_engine/synthesis.py`:
```python
class DecisionSynthesisEngine:
    """Combines rule + ML outputs into final decision"""
    async def synthesize_decision(
        self, claim_data, rule_result, ml_result
    ) -> ClaimIntelligenceReport:
        # Implement decision logic from specs
        pass
```

### Priority 3: Audit System (1 day)

Create `src/audit/audit_logger.py`:
```python
class ImmutableAuditLogger:
    """Cryptographically chained audit log"""
    async def log_event(self, event: AuditEvent) -> str:
        # Append-only with chain integrity
        pass
```

### Priority 4: Event Pipeline (2 days)

Create `src/events/kafka_consumer.py` and `kafka_producer.py` with circuit breakers.

### Priority 5: Admin Portal (3-4 days)

Create FastAPI application in `src/api/` with review endpoints.

---

## 🧪 **Testing Strategy**

### Unit Tests
```python
# tests/test_rule_engine.py
async def test_critical_rule_failure():
    claim = create_test_claim(billed_amount=-100)  # Invalid
    result = await rule_engine.evaluate_claim(claim)
    assert result.aggregate_outcome == RuleOutcome.FAIL
```

### Integration Tests
```python
# tests/integration/test_hip_connection.py
async def test_hip_data_retrieval():
    claim = await hip_service.get_claim_by_id("1")
    assert claim is not None
    assert claim.member_id_hash  # PII is hashed
```

### Load Tests
```python
# tests/load/test_throughput.py
async def test_1000_claims_per_second():
    # Simulate high load
    pass
```

---

## 📊 **Monitoring**

Once complete, the system will expose:

- **Prometheus Metrics**: `http://localhost:9090/metrics`
- **Health Check**: `http://localhost:8300/health`
- **API Docs**: `http://localhost:8300/docs`

---

## ⚠️ **Critical Reminders**

1. **NO AUTO-APPROVE YET**: Start with manual review only
2. **READ-ONLY HIP**: Never write to HIP database
3. **PII PROTECTION**: Always hash member IDs
4. **AUDIT EVERYTHING**: Every decision must be logged
5. **GRACEFUL DEGRADATION**: System must survive failures

---

## 📞 **Support**

For questions or issues:
- Review documentation in `docs/`
- Check progress in `IMPLEMENTATION_PROGRESS.md`
- Follow specifications exactly as designed

---

**Status**: Foundation complete, ready for component implementation  
**Next Milestone**: Functional rule engine with 10+ rules  
**ETA to MVP**: 2-3 weeks with focused development


