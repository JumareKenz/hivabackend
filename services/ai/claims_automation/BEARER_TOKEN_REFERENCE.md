# DCAL API Bearer Token Reference

## 🔐 Your Test Bearer Token

**Token (Valid for 24 hours):**
```
Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoidXNlcl90ZXN0dXNlciIsInVzZXJuYW1lIjoidGVzdHVzZXIiLCJyb2xlcyI6WyJyZXZpZXdlciIsImFkbWluIl0sImV4cCI6MTc2ODA1NDU0Nn0.fkj76XqRvoWpC7Tu_s2qihAr4NOBr2hDH-ob0eUwW0w
```

**Token Details:**
- Username: `testuser`
- Roles: `reviewer`, `admin` (full access)
- Expires: 24 hours from generation
- Status: ✅ **VERIFIED WORKING**

---

## 🚀 How to Use the Token

### Method 1: curl Command

```bash
TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoidXNlcl90ZXN0dXNlciIsInVzZXJuYW1lIjoidGVzdHVzZXIiLCJyb2xlcyI6WyJyZXZpZXdlciIsImFkbWluIl0sImV4cCI6MTc2ODA1NDU0Nn0.fkj76XqRvoWpC7Tu_s2qihAr4NOBr2hDH-ob0eUwW0w"

# Test protected endpoint
curl -X GET http://localhost:8300/api/queues/summary \
  -H "Authorization: Bearer $TOKEN"

# Process a claim
curl -X POST http://localhost:8300/api/claims/process \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
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

### Method 2: Swagger UI (Interactive)

1. Open: http://localhost:8300/docs
2. Click the **🔒 Authorize** button at the top
3. In the "Value" field, enter:
   ```
   eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoidXNlcl90ZXN0dXNlciIsInVzZXJuYW1lIjoidGVzdHVzZXIiLCJyb2xlcyI6WyJyZXZpZXdlciIsImFkbWluIl0sImV4cCI6MTc2ODA1NDU0Nn0.fkj76XqRvoWpC7Tu_s2qihAr4NOBr2hDH-ob0eUwW0w
   ```
   (Swagger automatically adds "Bearer" prefix)
4. Click **Authorize**
5. Now you can test all protected endpoints!

### Method 3: Python requests

```python
import requests

token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoidXNlcl90ZXN0dXNlciIsInVzZXJuYW1lIjoidGVzdHVzZXIiLCJyb2xlcyI6WyJyZXZpZXdlciIsImFkbWluIl0sImV4cCI6MTc2ODA1NDU0Nn0.fkj76XqRvoWpC7Tu_s2qihAr4NOBr2hDH-ob0eUwW0w"

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

# Test endpoint
response = requests.get(
    "http://localhost:8300/api/queues/summary",
    headers=headers
)
print(response.json())
```

### Method 4: JavaScript/fetch

```javascript
const token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoidXNlcl90ZXN0dXNlciIsInVzZXJuYW1lIjoidGVzdHVzZXIiLCJyb2xlcyI6WyJyZXZpZXdlciIsImFkbWluIl0sImV4cCI6MTc2ODA1NDU0Nn0.fkj76XqRvoWpC7Tu_s2qihAr4NOBr2hDH-ob0eUwW0w";

fetch("http://localhost:8300/api/queues/summary", {
  headers: {
    "Authorization": `Bearer ${token}`
  }
})
.then(res => res.json())
.then(data => console.log(data));
```

---

## 🔄 Generate New Token

If you need a new token or want different roles:

```bash
cd /root/hiva/services/ai/claims_automation

# Default (reviewer + admin)
python3 generate_test_token.py

# Custom username and roles
python3 generate_test_token.py --username myuser --roles reviewer admin fraud_investigator

# Just get the token (no extra output)
python3 generate_test_token.py --format token

# Get curl command ready
python3 generate_test_token.py --format curl
```

---

## 📋 Available Roles

- `admin` - Full access
- `senior_reviewer` - Senior review access
- `reviewer` - Standard review access
- `fraud_investigator` - Fraud investigation access
- `medical_director` - Medical director access
- `compliance_officer` - Compliance access
- `read_only` - Read-only access

---

## ✅ Token Verification

The token has been tested and verified working:
- ✅ Can access protected endpoints
- ✅ Has reviewer and admin roles
- ✅ Valid for 24 hours
- ✅ Properly signed with JWT_SECRET_KEY

---

## 🔒 Security Notes

⚠️ **This is a TEST token for development only!**

For production:
- Use proper user authentication
- Implement login endpoint
- Store tokens securely
- Use shorter expiration times
- Implement token refresh

---

## 📚 Related Files

- Token Generator: `/root/hiva/services/ai/claims_automation/generate_test_token.py`
- Auth Module: `/root/hiva/services/ai/claims_automation/src/api/auth.py`
- Config: `/root/hiva/services/ai/claims_automation/src/core/config.py`

---

**Last Updated:** Token generated and verified working ✅
