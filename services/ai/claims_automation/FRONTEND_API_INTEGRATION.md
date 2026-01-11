# DCAL Frontend API Integration Guide

## 🌐 Base URL

**Development:**
```
http://localhost:8300
```

**Production (via NGINX Gateway):**
```
https://dcal-ai-engine.api.hiva.chat
```

---

## 🔐 Authentication

**Bearer Token (Valid 24 hours):**
```
Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoidXNlcl90ZXN0dXNlciIsInVzZXJuYW1lIjoidGVzdHVzZXIiLCJyb2xlcyI6WyJyZXZpZXdlciIsImFkbWluIl0sImV4cCI6MTc2ODA1NDU0Nn0.fkj76XqRvoWpC7Tu_s2qihAr4NOBr2hDH-ob0eUwW0w
```

**Include in all requests:**
```javascript
headers: {
  'Authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoidXNlcl90ZXN0dXNlciIsInVzZXJuYW1lIjoidGVzdHVzZXIiLCJyb2xlcyI6WyJyZXZpZXdlciIsImFkbWluIl0sImV4cCI6MTc2ODA1NDU0Nn0.fkj76XqRvoWpC7Tu_s2qihAr4NOBr2hDH-ob0eUwW0w',
  'Content-Type': 'application/json'
}
```

---

## 📋 Core Frontend Endpoints

### 1. Health Check (No Auth Required)

**GET** `/health`

**Response:**
```json
{
  "status": "healthy",
  "orchestrator_initialized": true,
  "timestamp": "2026-01-09T13:46:22.007729"
}
```

**Usage:**
```javascript
fetch('http://localhost:8300/health')
  .then(res => res.json())
  .then(data => console.log(data));
```

---

### 2. Process Claim (Submit New Claim)

**POST** `/api/claims/process`

**Request Body:**
```json
{
  "claim_id": "CLM-2026-001",
  "policy_id": "POL-2026-12345",
  "provider_id": "PROV-001",
  "member_id_hash": "abc123def456",
  "procedure_codes": [
    {
      "code": "99213",
      "code_type": "CPT",
      "quantity": 1,
      "line_amount": 150.0
    }
  ],
  "diagnosis_codes": [
    {
      "code": "J06.9",
      "code_type": "ICD10_CM",
      "sequence": 1
    }
  ],
  "billed_amount": 150.0,
  "service_date": "2026-01-05",
  "claim_type": "PROFESSIONAL"
}
```

**Response:**
```json
{
  "analysis_id": "ANL-2026-001",
  "claim_id": "CLM-2026-001",
  "timestamp": "2026-01-09T13:46:22.007729",
  "recommendation": "APPROVE",
  "confidence_score": 0.85,
  "risk_score": 0.0669,
  "assigned_queue": "STANDARD_REVIEW",
  "priority": "MEDIUM",
  "sla_hours": 24,
  "primary_reasons": [
    "All rules passed",
    "Low ML risk score"
  ],
  "secondary_factors": [],
  "suggested_actions": [
    "Approve claim",
    "Process payment"
  ],
  "rule_engine_details": {
    "total_rules": 17,
    "passed": 15,
    "flagged": 2,
    "failed": 0
  },
  "ml_engine_details": {
    "risk_score": 0.0669,
    "confidence": 0.5917,
    "models": {
      "cost_anomaly": 0.05,
      "behavioral_fraud": 0.08,
      "provider_abuse": 0.06,
      "frequency_spike": 0.07,
      "network_analysis": 0.05,
      "temporal_pattern": 0.06
    }
  }
}
```

**JavaScript Example:**
```javascript
async function processClaim(claimData) {
  const response = await fetch('http://localhost:8300/api/claims/process', {
    method: 'POST',
    headers: {
      'Authorization': 'Bearer YOUR_TOKEN',
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(claimData)
  });
  
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  
  return await response.json();
}

// Usage
const claim = {
  claim_id: "CLM-2026-001",
  policy_id: "POL-2026-12345",
  provider_id: "PROV-001",
  member_id_hash: "abc123",
  procedure_codes: [
    { code: "99213", code_type: "CPT", quantity: 1, line_amount: 150.0 }
  ],
  diagnosis_codes: [
    { code: "J06.9", code_type: "ICD10_CM", sequence: 1 }
  ],
  billed_amount: 150.0,
  service_date: "2026-01-05",
  claim_type: "PROFESSIONAL"
};

processClaim(claim)
  .then(result => {
    console.log('Recommendation:', result.recommendation);
    console.log('Risk Score:', result.risk_score);
    console.log('ML Details:', result.ml_engine_details);
  })
  .catch(error => console.error('Error:', error));
```

---

### 3. Get Claim Details

**GET** `/api/claims/{claim_id}`

**Response:**
```json
{
  "claim_id": "CLM-2026-001",
  "policy_id": "POL-2026-12345",
  "provider_id": "PROV-001",
  "status": "PROCESSED",
  "recommendation": "APPROVE",
  "risk_score": 0.0669,
  "assigned_queue": "STANDARD_REVIEW",
  "priority": "MEDIUM"
}
```

**JavaScript Example:**
```javascript
async function getClaimDetails(claimId) {
  const response = await fetch(
    `http://localhost:8300/api/claims/${claimId}`,
    {
      headers: {
        'Authorization': 'Bearer YOUR_TOKEN'
      }
    }
  );
  return await response.json();
}
```

---

### 4. Get Claim Intelligence Report

**GET** `/api/claims/{claim_id}/intelligence`

**Response:** Full intelligence report with rules, ML analysis, and recommendations.

**JavaScript Example:**
```javascript
async function getClaimIntelligence(claimId) {
  const response = await fetch(
    `http://localhost:8300/api/claims/${claimId}/intelligence`,
    {
      headers: {
        'Authorization': 'Bearer YOUR_TOKEN'
      }
    }
  );
  return await response.json();
}
```

---

### 5. Get Queue Summary (Dashboard)

**GET** `/api/queues/summary`

**Response:**
```json
[
  {
    "queue_name": "STANDARD_REVIEW",
    "total_claims": 45,
    "overdue_claims": 3,
    "high_priority": 5,
    "medium_priority": 30,
    "low_priority": 10,
    "avg_risk_score": 0.35
  },
  {
    "queue_name": "SENIOR_REVIEW",
    "total_claims": 12,
    "overdue_claims": 1,
    "high_priority": 8,
    "medium_priority": 4,
    "low_priority": 0,
    "avg_risk_score": 0.65
  },
  {
    "queue_name": "FRAUD_INVESTIGATION",
    "total_claims": 8,
    "overdue_claims": 0,
    "high_priority": 8,
    "medium_priority": 0,
    "low_priority": 0,
    "avg_risk_score": 0.82
  }
]
```

**JavaScript Example:**
```javascript
async function getQueueSummary() {
  const response = await fetch('http://localhost:8300/api/queues/summary', {
    headers: {
      'Authorization': 'Bearer YOUR_TOKEN'
    }
  });
  return await response.json();
}

// Usage in dashboard
getQueueSummary().then(queues => {
  queues.forEach(queue => {
    console.log(`${queue.queue_name}: ${queue.total_claims} claims`);
  });
});
```

---

### 6. Get Claims in Queue

**GET** `/api/queues/{queue_name}/claims`

**Query Parameters:**
- `limit` (optional): Number of claims to return (default: 50)
- `offset` (optional): Pagination offset (default: 0)
- `priority` (optional): Filter by priority (HIGH, MEDIUM, LOW)
- `status` (optional): Filter by status

**Response:**
```json
{
  "queue_name": "STANDARD_REVIEW",
  "total": 45,
  "limit": 50,
  "offset": 0,
  "claims": [
    {
      "claim_id": "CLM-2026-001",
      "policy_id": "POL-2026-12345",
      "provider_id": "PROV-001",
      "billed_amount": 150.0,
      "service_date": "2026-01-05",
      "recommendation": "APPROVE",
      "risk_score": 0.0669,
      "priority": "MEDIUM",
      "sla_hours": 24,
      "submitted_at": "2026-01-09T10:00:00Z"
    }
  ]
}
```

**JavaScript Example:**
```javascript
async function getQueueClaims(queueName, options = {}) {
  const params = new URLSearchParams({
    limit: options.limit || 50,
    offset: options.offset || 0,
    ...(options.priority && { priority: options.priority }),
    ...(options.status && { status: options.status })
  });
  
  const response = await fetch(
    `http://localhost:8300/api/queues/${queueName}/claims?${params}`,
    {
      headers: {
        'Authorization': 'Bearer YOUR_TOKEN'
      }
    }
  );
  return await response.json();
}

// Usage
getQueueClaims('STANDARD_REVIEW', { limit: 20, priority: 'HIGH' })
  .then(data => {
    console.log(`Found ${data.total} claims`);
    data.claims.forEach(claim => {
      console.log(claim.claim_id, claim.risk_score);
    });
  });
```

---

### 7. Get My Assignments

**GET** `/api/queues/my-assignments`

**Response:** List of claims assigned to the current user.

**JavaScript Example:**
```javascript
async function getMyAssignments() {
  const response = await fetch('http://localhost:8300/api/queues/my-assignments', {
    headers: {
      'Authorization': 'Bearer YOUR_TOKEN'
    }
  });
  return await response.json();
}
```

---

### 8. Submit Decision

**POST** `/api/decisions/submit`

**Request Body:**
```json
{
  "claim_id": "CLM-2026-001",
  "decision": "APPROVE",
  "reasoning": "All checks passed, low risk score",
  "notes": "Processed by reviewer",
  "override_ai": false
}
```

**Response:**
```json
{
  "decision_id": "DEC-2026-001",
  "claim_id": "CLM-2026-001",
  "decision": "APPROVE",
  "submitted_at": "2026-01-09T14:00:00Z",
  "reviewer": "testuser",
  "status": "SUBMITTED"
}
```

**JavaScript Example:**
```javascript
async function submitDecision(claimId, decision, reasoning, notes = '') {
  const response = await fetch('http://localhost:8300/api/decisions/submit', {
    method: 'POST',
    headers: {
      'Authorization': 'Bearer YOUR_TOKEN',
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      claim_id: claimId,
      decision: decision, // "APPROVE", "DECLINE", "REVIEW"
      reasoning: reasoning,
      notes: notes,
      override_ai: false
    })
  });
  return await response.json();
}
```

---

### 9. Assign Claim to Reviewer

**POST** `/api/decisions/{claim_id}/assign`

**Request Body:**
```json
{
  "reviewer_username": "reviewer1",
  "queue": "STANDARD_REVIEW",
  "priority": "HIGH",
  "notes": "Assigned for urgent review"
}
```

**JavaScript Example:**
```javascript
async function assignClaim(claimId, reviewerUsername, queue, priority) {
  const response = await fetch(
    `http://localhost:8300/api/decisions/${claimId}/assign`,
    {
      method: 'POST',
      headers: {
        'Authorization': 'Bearer YOUR_TOKEN',
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        reviewer_username: reviewerUsername,
        queue: queue,
        priority: priority
      })
    }
  );
  return await response.json();
}
```

---

### 10. Get Decision History

**GET** `/api/decisions/{claim_id}/history`

**Response:** Complete history of decisions for a claim.

**JavaScript Example:**
```javascript
async function getDecisionHistory(claimId) {
  const response = await fetch(
    `http://localhost:8300/api/decisions/${claimId}/history`,
    {
      headers: {
        'Authorization': 'Bearer YOUR_TOKEN'
      }
    }
  );
  return await response.json();
}
```

---

### 11. Get Audit Events

**GET** `/api/audit/events`

**Query Parameters:**
- `claim_id` (optional): Filter by claim ID
- `event_type` (optional): Filter by event type
- `start_date` (optional): Start date filter
- `end_date` (optional): End date filter
- `limit` (optional): Number of events (default: 100)
- `offset` (optional): Pagination offset

**JavaScript Example:**
```javascript
async function getAuditEvents(filters = {}) {
  const params = new URLSearchParams();
  if (filters.claim_id) params.append('claim_id', filters.claim_id);
  if (filters.event_type) params.append('event_type', filters.event_type);
  if (filters.start_date) params.append('start_date', filters.start_date);
  if (filters.end_date) params.append('end_date', filters.end_date);
  params.append('limit', filters.limit || 100);
  params.append('offset', filters.offset || 0);
  
  const response = await fetch(
    `http://localhost:8300/api/audit/events?${params}`,
    {
      headers: {
        'Authorization': 'Bearer YOUR_TOKEN'
      }
    }
  );
  return await response.json();
}
```

---

### 12. Get Audit Statistics

**GET** `/api/audit/stats`

**Response:** Audit statistics and metrics.

**JavaScript Example:**
```javascript
async function getAuditStats() {
  const response = await fetch('http://localhost:8300/api/audit/stats', {
    headers: {
      'Authorization': 'Bearer YOUR_TOKEN'
    }
  });
  return await response.json();
}
```

---

## 🎯 Complete Frontend Integration Example

```javascript
// DCAL API Client
class DCALClient {
  constructor(baseURL, token) {
    this.baseURL = baseURL || 'http://localhost:8300';
    this.token = token;
  }
  
  async request(endpoint, options = {}) {
    const url = `${this.baseURL}${endpoint}`;
    const headers = {
      'Authorization': `Bearer ${this.token}`,
      'Content-Type': 'application/json',
      ...options.headers
    };
    
    const response = await fetch(url, {
      ...options,
      headers
    });
    
    if (!response.ok) {
      throw new Error(`API Error: ${response.status} ${response.statusText}`);
    }
    
    return await response.json();
  }
  
  // Health check
  async health() {
    return await fetch(`${this.baseURL}/health`).then(r => r.json());
  }
  
  // Process claim
  async processClaim(claimData) {
    return await this.request('/api/claims/process', {
      method: 'POST',
      body: JSON.stringify(claimData)
    });
  }
  
  // Get claim details
  async getClaim(claimId) {
    return await this.request(`/api/claims/${claimId}`);
  }
  
  // Get claim intelligence
  async getClaimIntelligence(claimId) {
    return await this.request(`/api/claims/${claimId}/intelligence`);
  }
  
  // Get queue summary
  async getQueueSummary() {
    return await this.request('/api/queues/summary');
  }
  
  // Get queue claims
  async getQueueClaims(queueName, options = {}) {
    const params = new URLSearchParams(options);
    return await this.request(`/api/queues/${queueName}/claims?${params}`);
  }
  
  // Get my assignments
  async getMyAssignments() {
    return await this.request('/api/queues/my-assignments');
  }
  
  // Submit decision
  async submitDecision(claimId, decision, reasoning, notes = '') {
    return await this.request('/api/decisions/submit', {
      method: 'POST',
      body: JSON.stringify({
        claim_id: claimId,
        decision,
        reasoning,
        notes,
        override_ai: false
      })
    });
  }
  
  // Assign claim
  async assignClaim(claimId, reviewerUsername, queue, priority) {
    return await this.request(`/api/decisions/${claimId}/assign`, {
      method: 'POST',
      body: JSON.stringify({
        reviewer_username: reviewerUsername,
        queue,
        priority
      })
    });
  }
  
  // Get decision history
  async getDecisionHistory(claimId) {
    return await this.request(`/api/decisions/${claimId}/history`);
  }
  
  // Get audit events
  async getAuditEvents(filters = {}) {
    const params = new URLSearchParams(filters);
    return await this.request(`/api/audit/events?${params}`);
  }
  
  // Get audit stats
  async getAuditStats() {
    return await this.request('/api/audit/stats');
  }
}

// Usage
const client = new DCALClient(
  'http://localhost:8300',
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoidXNlcl90ZXN0dXNlciIsInVzZXJuYW1lIjoidGVzdHVzZXIiLCJyb2xlcyI6WyJyZXZpZXdlciIsImFkbWluIl0sImV4cCI6MTc2ODA1NDU0Nn0.fkj76XqRvoWpC7Tu_s2qihAr4NOBr2hDH-ob0eUwW0w'
);

// Example: Process a claim
const claim = {
  claim_id: "CLM-2026-001",
  policy_id: "POL-2026-12345",
  provider_id: "PROV-001",
  member_id_hash: "abc123",
  procedure_codes: [
    { code: "99213", code_type: "CPT", quantity: 1, line_amount: 150.0 }
  ],
  diagnosis_codes: [
    { code: "J06.9", code_type: "ICD10_CM", sequence: 1 }
  ],
  billed_amount: 150.0,
  service_date: "2026-01-05",
  claim_type: "PROFESSIONAL"
};

client.processClaim(claim)
  .then(result => {
    console.log('Recommendation:', result.recommendation);
    console.log('Risk Score:', result.risk_score);
  })
  .catch(error => console.error('Error:', error));
```

---

## 📊 Frontend Workflow Examples

### Workflow 1: Submit and Review Claim

```javascript
// 1. Submit claim
const result = await client.processClaim(claimData);

// 2. Check recommendation
if (result.recommendation === 'APPROVE' && result.risk_score < 0.3) {
  // Auto-approve low-risk claims
  await client.submitDecision(result.claim_id, 'APPROVE', 'Low risk, auto-approved');
} else {
  // Send to review queue
  await client.assignClaim(
    result.claim_id,
    'reviewer1',
    result.assigned_queue,
    result.priority
  );
}
```

### Workflow 2: Dashboard Load

```javascript
// Load dashboard data
async function loadDashboard() {
  const [queues, myAssignments, stats] = await Promise.all([
    client.getQueueSummary(),
    client.getMyAssignments(),
    client.getAuditStats()
  ]);
  
  return { queues, myAssignments, stats };
}
```

### Workflow 3: Review Queue

```javascript
// Load queue for review
async function loadReviewQueue(queueName) {
  const queueData = await client.getQueueClaims(queueName, {
    limit: 50,
    priority: 'HIGH'
  });
  
  return queueData.claims;
}
```

---

## 🔄 Error Handling

```javascript
async function handleAPIError(error) {
  if (error.message.includes('401')) {
    // Token expired, refresh token
    console.error('Authentication failed');
  } else if (error.message.includes('403')) {
    // Insufficient permissions
    console.error('Access denied');
  } else if (error.message.includes('404')) {
    // Resource not found
    console.error('Resource not found');
  } else {
    // Other errors
    console.error('API Error:', error);
  }
}
```

---

## 📝 Notes

- All endpoints except `/health` require authentication
- Token expires after 24 hours (generate new one with `generate_test_token.py`)
- Use proper error handling in production
- Implement token refresh mechanism
- Add request retry logic for network failures
- Cache queue summaries for better performance

---

## 🔗 Related Documentation

- Bearer Token Reference: `BEARER_TOKEN_REFERENCE.md`
- API Documentation: http://localhost:8300/docs
- OpenAPI Spec: http://localhost:8300/openapi.json
