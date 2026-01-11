# Phase 1: Canonical Domain Definition - Clinical Claims & Diagnosis

## Domain Scope
**ONLY answers questions about:**
- diagnoses
- claims
- clinical services
- volumes, trends, and costs tied to diagnoses

**Explicitly excluded:**
- users
- providers
- payments
- roles/permissions
- accreditation
- telescope
- admin metadata

## Authoritative Tables (LOCKED)

### Core Tables
- `claims`
- `service_summaries`
- `service_summary_diagnosis`
- `diagnoses`
- `claims_services`
- `services`

## Canonical Join Graph (SINGLE SOURCE OF TRUTH)

```
claims.id
  └── service_summaries.claim_id

service_summaries.id
  └── service_summary_diagnosis.service_summary_id

service_summary_diagnosis.diagnosis_id
  └── diagnoses.id

claims.id
  └── claims_services.claims_id

claims_services.services_id
  └── services.id
```

🚫 Any alternative join path is invalid.

## Semantic Meaning

### diagnoses
- **Represents:** Medical diagnosis definitions
- **Human label:** `diagnoses.name`
- **Forbidden:** `diagnoses.id`, `diagnoses.diagnosis_code`

### claims
- **Represents:** Financial/administrative record of care
- **Used for:** counting, time filtering, cost aggregation
- **Primary date:** `claims.created_at`

### service_summaries
- **Represents:** Clinical encounter summary
- **Bridge between diagnosis and claim**

### service_summary_diagnosis
- **Represents:** Diagnosis ↔ encounter mapping
- **Never exposed directly to users**

### claims_services
- **Represents:** Itemized services/drugs per claim
- **Used for:** cost & service analysis

### services
- **Represents:** Named clinical services
- **Human label:** `services.description`

## Mandatory Label Resolution Rules

### ALWAYS resolve:
- **Diagnosis** → `diagnoses.name`
- **Service** → `services.description`

### NEVER return:
- `id`
- `*_id`
- `diagnosis_code`
- foreign keys

## Allowed Question Types

✅ **Valid:**
- "Most common diagnosis last year"
- "Diagnosis trends by month"
- "Average claim cost per diagnosis"
- "Top diagnoses by service volume"

❌ **Invalid:**
- "Diagnosis code 77 details"
- "Show raw diagnosis IDs"
- "Which user made the claim"

## Aggregation Rules

### Legal GROUP BY:
- `diagnoses.name`
- `DATE(claims.created_at)`

### Illegal GROUP BY:
- `diagnoses.id`
- `service_summary_diagnosis.diagnosis_id`

## Gold-Standard SQL Example

**Question:** Which diagnosis had the most claims last year?

```sql
SELECT
    d.name AS diagnosis,
    COUNT(DISTINCT c.id) AS total_claims
FROM claims c
JOIN service_summaries ss
    ON ss.claim_id = c.id
JOIN service_summary_diagnosis ssd
    ON ssd.service_summary_id = ss.id
JOIN diagnoses d
    ON d.id = ssd.diagnosis_id
WHERE YEAR(c.created_at) = YEAR(CURRENT_DATE) - 1
GROUP BY d.name
ORDER BY total_claims DESC
LIMIT 1;
```

✔ Human-readable
✔ Deterministic
✔ Auditable
✔ No codes, no IDs




