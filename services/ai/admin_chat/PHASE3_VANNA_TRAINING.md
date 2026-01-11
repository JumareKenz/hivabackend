# Phase 3: Vanna Training Set - Clinical Claims & Diagnosis

## Goal
Teach Vanna to:
- Generate correct joins
- Return human-readable answers
- Apply proper aggregation
- Avoid IDs, codes, and shortcuts

## Minimal Schema Context (Only What Matters)

### Core Tables Only:
```sql
claims (
  id,
  created_at,
  total_cost
);

service_summaries (
  id,
  claim_id
);

service_summary_diagnosis (
  service_summary_id,
  diagnosis_id
);

diagnoses (
  id,
  name
);

claims_services (
  claims_id,
  services_id,
  cost
);

services (
  id,
  description
);
```

## Authoritative Join Rules (Must Be Included Verbatim)

**Diagnoses are connected to claims ONLY through:**
```
claims → service_summaries → service_summary_diagnosis → diagnoses
```

**Services are connected ONLY through:**
```
claims → claims_services → services
```

This single instruction eliminates 70% of bad SQL.

## Core Training Pairs (High-Precision)

### Example 1 — Most Common Diagnosis
**Question:** Which diagnosis has the most claims?

**SQL:**
```sql
SELECT
    d.name AS diagnosis,
    COUNT(DISTINCT c.id) AS total_claims
FROM claims c
JOIN service_summaries ss ON ss.claim_id = c.id
JOIN service_summary_diagnosis ssd ON ssd.service_summary_id = ss.id
JOIN diagnoses d ON d.id = ssd.diagnosis_id
GROUP BY d.name
ORDER BY total_claims DESC
LIMIT 1;
```

### Example 2 — Diagnosis Trend (Monthly)
**Question:** Show monthly trends of diagnoses.

**SQL:**
```sql
SELECT
    d.name AS diagnosis,
    DATE_FORMAT(c.created_at, '%Y-%m') AS month,
    COUNT(DISTINCT c.id) AS total_claims
FROM claims c
JOIN service_summaries ss ON ss.claim_id = c.id
JOIN service_summary_diagnosis ssd ON ssd.service_summary_id = ss.id
JOIN diagnoses d ON d.id = ssd.diagnosis_id
GROUP BY d.name, month
ORDER BY month;
```

### Example 3 — Average Claim Cost per Diagnosis
**Question:** What is the average claim cost per diagnosis?

**SQL:**
```sql
SELECT
    d.name AS diagnosis,
    AVG(c.total_cost) AS avg_claim_cost
FROM claims c
JOIN service_summaries ss ON ss.claim_id = c.id
JOIN service_summary_diagnosis ssd ON ssd.service_summary_id = ss.id
JOIN diagnoses d ON d.id = ssd.diagnosis_id
WHERE c.total_cost IS NOT NULL
GROUP BY d.name
ORDER BY avg_claim_cost DESC;
```

### Example 4 — Services Used Per Diagnosis
**Question:** What services are most commonly used for each diagnosis?

**SQL:**
```sql
SELECT
    d.name AS diagnosis,
    s.description AS service,
    COUNT(*) AS usage_count
FROM claims c
JOIN service_summaries ss ON ss.claim_id = c.id
JOIN service_summary_diagnosis ssd ON ssd.service_summary_id = ss.id
JOIN diagnoses d ON d.id = ssd.diagnosis_id
JOIN claims_services cs ON cs.claims_id = c.id
JOIN services s ON s.id = cs.services_id
GROUP BY d.name, s.description
ORDER BY usage_count DESC;
```

### Example 5 — Top Diagnoses Last Year
**Question:** What were the top diagnoses last year?

**SQL:**
```sql
SELECT
    d.name AS diagnosis,
    COUNT(DISTINCT c.id) AS total_claims
FROM claims c
JOIN service_summaries ss ON ss.claim_id = c.id
JOIN service_summary_diagnosis ssd ON ssd.service_summary_id = ss.id
JOIN diagnoses d ON d.id = ssd.diagnosis_id
WHERE YEAR(c.created_at) = YEAR(CURRENT_DATE) - 1
GROUP BY d.name
ORDER BY total_claims DESC;
```

## Negative Training (Critical)

### ❌ Bad Example 1
**Question:** Show diagnosis IDs with most cases

**Bad SQL:**
```sql
SELECT diagnosis_id, COUNT(*)
FROM service_summary_diagnosis
GROUP BY diagnosis_id;
```

**Instruction:** Never return diagnosis IDs. Always resolve to diagnoses.name and aggregate by claims.

### ❌ Bad Example 2
**Question:** Show diagnosis codes

**Bad SQL:**
```sql
SELECT diagnosis_code, COUNT(*)
FROM diagnoses
GROUP BY diagnosis_code;
```

**Instruction:** Never return diagnosis_code. Always use diagnoses.name for human-readable output.

### ❌ Bad Example 3
**Question:** Count service summaries

**Bad SQL:**
```sql
SELECT COUNT(*) FROM service_summaries;
```

**Instruction:** Never count service_summaries directly. Always count DISTINCT claims.id.

## Output Enforcement Rules

### Block output if SQL contains:
- `diagnosis_id` in SELECT
- `service_summary_diagnosis.*` in SELECT
- `GROUP BY id`
- `SELECT id` (unless for counting)
- `diagnosis_code` in SELECT

### Rewrite if:
- Grouping is done on IDs
- Joins bypass service_summaries
- Labels are missing




