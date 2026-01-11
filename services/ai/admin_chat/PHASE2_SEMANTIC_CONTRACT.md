# Phase 2: Semantic Contract - Clinical Claims & Diagnosis

## Canonical Intents (Locked)

### A. Frequency / Volume
**Examples:**
- "Most common diagnosis"
- "Top 10 diagnoses"
- "Diagnosis with highest number of claims"

**Semantic meaning:**
- Count of distinct claims associated with a diagnosis

**SQL rule:**
- `COUNT(DISTINCT claims.id)`
- 🚫 Never count: service_summary rows, diagnosis mappings, raw joins

### B. Trend / Time Series
**Examples:**
- "Diagnosis trend over time"
- "Monthly diagnosis counts"
- "Increase in malaria cases"

**Semantic meaning:**
- Diagnosis frequency grouped by time unit

**SQL rule:**
- `GROUP BY DATE_FORMAT(claims.created_at, '%Y-%m')`

**Time defaults:**
- If not specified → monthly
- If "last year" → previous calendar year

### C. Cost / Financial Impact
**Examples:**
- "Average claim cost per diagnosis"
- "Most expensive diagnosis"

**Semantic meaning:**
- Cost derived only from claims or claim services

**Allowed measures:**
- `AVG(claims.total_cost)`
- `SUM(claims_services.cost)`
- 🚫 Never infer cost from services.price alone

### D. Service Utilization
**Examples:**
- "Most common service per diagnosis"
- "Services used for diabetes"

**Semantic meaning:**
- Join diagnosis → claim → services

**Mandatory output labels:**
- `diagnoses.name`
- `services.description`

## Mandatory Disambiguation Rules

### Rule 1: "Most / Highest / Top"
If user says: "Most common diagnosis"
- Implicit meaning: `ORDER BY COUNT(DISTINCT claims.id) DESC LIMIT 1`

### Rule 2: Time References
| Phrase | Interpretation |
|--------|----------------|
| last year | previous calendar year |
| this year | current calendar year |
| recent | last 90 days |
| no time mentioned | ALL available data |

### Rule 3: "Cases" ≠ "Claims"
- Cases → clinical encounters → mapped via service_summaries
- Claims → administrative record
- Default interpretation: `cases = DISTINCT claims.id`

## Output Contract (Non-Negotiable)

### Required:
- Human-readable labels
- Aggregated metrics
- Ordered results (if ranking)

### Forbidden:
- IDs
- codes
- foreign keys
- raw junction tables

## Canonical SQL Patterns

### Pattern 1: Most Common Diagnosis
```sql
SELECT
    d.name AS diagnosis,
    COUNT(DISTINCT c.id) AS total_claims
FROM claims c
JOIN service_summaries ss ON ss.claim_id = c.id
JOIN service_summary_diagnosis ssd ON ssd.service_summary_id = ss.id
JOIN diagnoses d ON d.id = ssd.diagnosis_id
GROUP BY d.name
ORDER BY total_claims DESC;
```

### Pattern 2: Diagnosis Trend (Monthly)
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

### Pattern 3: Average Claim Cost per Diagnosis
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

### Pattern 4: Services Used per Diagnosis
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

## When to Ask Follow-Up

| User Input | Required Follow-up |
|------------|-------------------|
| "cost" | total or average? |
| "recent" | define timeframe |
| "top diagnoses" | how many? |
| "cases" | claims or encounters? |




