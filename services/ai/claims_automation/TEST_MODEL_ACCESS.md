# How to Access and Test DCAL ML Models

## 🎯 Quick Access Methods

### Method 1: Interactive API Documentation (Easiest)

**Access Swagger UI:**
```
http://localhost:8300/docs
```

**Steps:**
1. Open the URL in your browser
2. Click on `/api/claims/process` endpoint
3. Click "Try it out"
4. Fill in the request body
5. Click "Execute"
6. View the ML analysis results in the response

---

### Method 2: Direct API Calls (curl/HTTP)

**Note:** Protected endpoints require JWT authentication. See "Authentication Setup" below.

**Test Health (No Auth Required):**
```bash
curl http://localhost:8300/health
```

**Test API Info (No Auth Required):**
```bash
curl http://localhost:8300/api/info
```

---

### Method 3: Python Script Testing (Recommended)

Use the provided test scripts to test the ML models directly:

```bash
# Test ML Engine directly
cd /root/hiva/services/ai/claims_automation
python3 tests/test_ml_engine.py

# Test complete pipeline
python3 tests/test_complete_pipeline.py

# Test system integration
python3 test_dcal_system.py
```

---

## 🔐 Authentication Setup

To test protected endpoints, you need a JWT token. The system uses JWT authentication.

### Option 1: Create Test User (If login endpoint exists)

```bash
# Check if login endpoint exists
curl http://localhost:8300/docs
# Look for /api/auth/login or similar
```

### Option 2: Generate Test Token (For Development)

Create a simple script to generate a test token:

```python
# test_token_gen.py
from datetime import datetime, timedelta
from jose import jwt
import os

# Get secret from environment or use default for testing
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "test-secret-key-change-in-production")
ALGORITHM = "HS256"

# Create test token
token_data = {
    "sub": "test-user",
    "username": "testuser",
    "roles": ["reviewer", "admin"],
    "exp": datetime.utcnow() + timedelta(hours=24)
}

token = jwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)
print(f"Bearer {token}")
```

---

## 📊 Testing ML Models

### Test 1: Process a Claim (Full Pipeline)

**Request:**
```bash
curl -X POST http://localhost:8300/api/claims/process \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "claim_id": "TEST-001",
    "policy_id": "POL-001",
    "provider_id": "PROV-001",
    "member_id_hash": "abc123",
    "procedure_codes": [
      {"code": "99213", "code_type": "CPT", "quantity": 1, "line_amount": 150.0}
    ],
    "diagnosis_codes": [
      {"code": "J06.9", "code_type": "ICD10_CM", "sequence": 1}
    ],
    "billed_amount": 150.0,
    "service_date": "2026-01-05",
    "claim_type": "PROFESSIONAL"
  }'
```

**Response includes:**
- `risk_score`: ML fraud risk (0.0 - 1.0)
- `confidence_score`: Model confidence
- `ml_engine_details`: Detailed ML analysis
- `rule_engine_details`: Rule evaluation results
- `recommendation`: APPROVE / REVIEW / DECLINE

### Test 2: Get Claim Intelligence Report

```bash
curl -X GET http://localhost:8300/api/claims/TEST-001/intelligence \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Test 3: View ML Model Details

The response includes:
```json
{
  "ml_engine_details": {
    "risk_score": 0.75,
    "confidence": 0.92,
    "models": {
      "cost_anomaly": 0.80,
      "behavioral_fraud": 0.70,
      "provider_abuse": 0.65,
      "frequency_spike": 0.55,
      "network_analysis": 0.60,
      "temporal_pattern": 0.50
    },
    "explanations": {
      "top_features": [...],
      "shap_values": {...}
    }
  }
}
```

---

## 🧪 Direct ML Engine Testing

### Test ML Models Directly (Python)

```python
import asyncio
from src.core.models import ClaimData, ProcedureCode, DiagnosisCode, ClaimType
from src.ml_engine.engine import MLFraudDetectionEngine
from datetime import date

async def test_ml_models():
    # Initialize ML engine
    ml_engine = MLFraudDetectionEngine()
    await ml_engine.initialize()
    
    # Create test claim
    claim = ClaimData(
        claim_id="ML-TEST-001",
        policy_id="POL-001",
        provider_id="PROV-001",
        member_id_hash="test_member_hash",
        procedure_codes=[
            ProcedureCode(code="99213", code_type="CPT", quantity=1, line_amount=50000.0)
        ],
        diagnosis_codes=[
            DiagnosisCode(code="A00.0", code_type="ICD10_CM", sequence=1)
        ],
        billed_amount=50000.0,
        service_date=date(2026, 1, 5),
        claim_type=ClaimType.PROFESSIONAL
    )
    
    # Run ML analysis
    result = await ml_engine.analyze_claim(claim)
    
    print(f"Risk Score: {result.combined_risk_score:.2%}")
    print(f"Confidence: {result.combined_confidence:.2%}")
    print(f"Recommendation: {result.recommendation}")
    
    # View individual model scores
    for model_name, score in result.model_results.items():
        print(f"{model_name}: {score:.2%}")

asyncio.run(test_ml_models())
```

---

## 📈 Understanding ML Model Outputs

### 6 ML Models in DCAL:

1. **Cost Anomaly Detector** - Flags unusually high costs
2. **Behavioral Fraud Model** - Detects suspicious patterns
3. **Provider Abuse Detector** - Identifies provider anomalies
4. **Frequency Spike Model** - Detects claim frequency anomalies
5. **Network Analysis Model** - Analyzes provider-member networks
6. **Temporal Pattern Model** - Detects time-based patterns

### Risk Score Interpretation:

- **0.0 - 0.3**: Low Risk (Likely Approve)
- **0.3 - 0.6**: Medium Risk (Review Recommended)
- **0.6 - 0.8**: High Risk (Manual Review Required)
- **0.8 - 1.0**: Very High Risk (Decline/Investigate)

### Confidence Score:

- **> 0.8**: High confidence in prediction
- **0.5 - 0.8**: Moderate confidence
- **< 0.5**: Low confidence (may need more data)

---

## 🚀 Quick Test Commands

```bash
# 1. Check server status
curl http://localhost:8300/health

# 2. View API documentation
# Open: http://localhost:8300/docs

# 3. Test ML engine directly
cd /root/hiva/services/ai/claims_automation
python3 tests/test_ml_engine.py -v

# 4. Test complete pipeline
python3 tests/test_complete_pipeline.py -v

# 5. Run all tests
pytest tests/ -v
```

---

## 📝 Example Test Scenarios

### Scenario 1: Low-Risk Claim
- Normal procedure codes
- Standard billing amounts
- Established provider
- **Expected**: Low risk score, Approve recommendation

### Scenario 2: High-Risk Claim
- Unusually high billed amount
- Rare procedure codes
- New provider
- **Expected**: High risk score, Review/Decline recommendation

### Scenario 3: Suspicious Pattern
- Multiple claims from same provider
- Rapid frequency increase
- Network anomalies
- **Expected**: Medium-High risk, Review required

---

## 🔍 Debugging Tips

1. **Check ML Engine Status:**
   ```bash
   curl http://localhost:8300/api/info
   # Look for "ml_engine": true
   ```

2. **View Server Logs:**
   ```bash
   tail -f /root/hiva/services/ai/claims_automation/server.log
   ```

3. **Test Individual Components:**
   ```python
   # Test feature engineering
   from src.ml_engine.feature_engineering import FeatureEngineer
   # Test individual models
   from src.ml_engine.models import CostAnomalyModel
   ```

4. **Check Model Files:**
   ```bash
   ls -la /root/hiva/services/ai/claims_automation/models/
   ```

---

## 📚 Additional Resources

- **API Documentation**: http://localhost:8300/docs
- **OpenAPI Spec**: http://localhost:8300/openapi.json
- **Test Scripts**: `/root/hiva/services/ai/claims_automation/tests/`
- **ML Documentation**: `/root/hiva/services/ai/claims_automation/docs/04_ML_FRAUD_DETECTION.md`
