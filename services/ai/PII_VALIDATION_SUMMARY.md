# PII/PHI Validation & Guardrails Implementation

## Overview
Comprehensive PII/PHI validation system that checks inputs, outputs, and SQL queries before data reaches the UI. Implements strict guardrails to prevent individual identification.

## Features Implemented

### 1. PII Validator Service (`pii_validator.py`)

**Input Validation:**
- Detects PII patterns in user queries (names, phones, emails, IDs, addresses, DOB)
- Blocks "who" questions about individuals
- Redacts PII in queries before processing
- Detects individual identification attempts

**Output Validation:**
- Scans query results for stray PII/PHI patterns
- Redacts any detected PII before results reach UI
- Returns sanitized results with privacy warnings

**SQL Validation:**
- Detects attempts to reverse-engineer hashed IDs
- Blocks queries that try to decode/decrypt hashed values
- Validates read-only compliance

### 2. Enhanced Privacy Service

Updated to use PII validator for comprehensive detection:
- Individual identification query detection
- PII pattern matching in natural language
- Integration with existing small cell suppression

### 3. System Guardrails

**Updated SQL Generator Prompt:**
```
"You are an analytics assistant. If a user provides a name, phone number, 
or specific ID in their prompt, redact it in your internal processing and 
inform the user that you only process de-identified data. Never attempt to 
reverse-engineer hashed IDs."
```

**Key Rules:**
- MUST refuse to answer questions about specific individuals
- MUST refuse "who" questions about patients
- MUST pivot to aggregated trends when individual identification is requested
- MUST only process de-identified data

### 4. Data Masking Patterns

| Raw Data (PHI) | Masked View (Non-PHI) |
|----------------|----------------------|
| Patient Identity: John Doe | a5f1...e92b (Hash) |
| Location: 123 Herbert Macaulay Way | Osun State (Region only) |
| Time Scale: Oct 12, 2023, 14:30 | Q4 2023 |
| Medical Detail: "Stage 2 Chronic Kidney Disease" | "Chronic - Renal" |
| Names | [REDACTED] |
| Phone Numbers | ***-***-XXXX |
| Email | XX***@*** |
| DOB | Age-bucketed (0-17, 18-24, etc.) |

### 5. Admin Endpoint Integration

**Input Validation (Step 0):**
- Validates user query for PII patterns
- Blocks individual identification queries
- Redacts PII before processing
- Returns privacy warnings

**SQL Validation (Step 2):**
- Validates generated SQL for PII leakage attempts
- Blocks reverse-engineering attempts
- Ensures read-only compliance

**Output Validation (Step 5):**
- Final validation of query results
- Redacts any stray PII/PHI patterns
- Adds privacy warnings to response

**Response Fields:**
- `privacy_warning`: Warning message if PII detected
- `pii_detected`: List of detected PII types
- `privacy_blocked`: Boolean if query was blocked

## PII Detection Patterns

### Detected Patterns:
1. **Names**: First Last, Titles (Mr/Mrs/Dr), Middle Initials
2. **Phone Numbers**: US format, International, Nigerian (0XXXXXXXXXX, +234XXXXXXXXXX)
3. **Email Addresses**: Standard email format
4. **SSN**: XXX-XX-XXXX format
5. **ID Numbers**: Alphanumeric IDs (e.g., CLM8537906241)
6. **Addresses**: Street addresses, PO Boxes
7. **Date of Birth**: Various date formats
8. **Medical Records**: MRN, Patient ID patterns
9. **Individual Queries**: "who is", "find patient", "identify person"

### Blocked Query Types:
- "Who is the patient with ID X?"
- "Find the person named John Doe"
- "Show me patient John Doe's records"
- "Identify the individual with phone number..."

### Allowed Query Types:
- "Show me top 10 providers by claim volume"
- "What is the average claim cost by state?"
- "How many claims were processed this month?"
- "Show aggregated trends by region"

## Read-Only Enforcement

All database operations are strictly read-only:
1. **Database Service**: Validates SQL for SELECT-only
2. **SQL Generator**: Only generates SELECT queries
3. **PII Validator**: Blocks any write operations
4. **Analytics Views**: Pre-masked, read-only views

## Usage Examples

### Blocked Query:
```json
{
  "query": "Who is the patient named John Doe?"
}
```

**Response:**
```json
{
  "success": false,
  "error": "For privacy compliance, I only provide insights at the cohort level. I cannot identify specific individuals or answer 'who' questions about patients.",
  "privacy_blocked": true,
  "privacy_warning": "⚠️ Privacy Notice: For privacy compliance, I only provide insights at the cohort level. I cannot identify specific individuals."
}
```

### Allowed Query with PII Detection:
```json
{
  "query": "Show me claims for patient John Doe"
}
```

**Response:**
```json
{
  "success": true,
  "data": [...],
  "privacy_warning": "⚠️ Privacy Notice: Names have been redacted for privacy compliance.",
  "pii_detected": ["name"]
}
```

### Output Validation:
If query results contain stray PII (e.g., from unmasked columns), they are automatically redacted:
- `"John Doe"` → `"[REDACTED_NAME]"`
- `"+2349012345678"` → `"[REDACTED_PHONE]"`
- `"john@example.com"` → `"[REDACTED_EMAIL]"`

## Files Created/Modified

### New Files:
1. `ai/app/services/pii_validator.py` - Comprehensive PII/PHI validation

### Modified Files:
1. `ai/app/services/privacy_service.py` - Integrated PII validator
2. `ai/app/services/enhanced_sql_generator.py` - Added guardrail prompts
3. `ai/app/api/v1/admin.py` - Added input/output validation

## Testing

Test the validation with:
1. **Individual Identification**: "Who is patient X?" → Should be blocked
2. **PII in Query**: "Show claims for John Doe" → Should redact and warn
3. **PII in Results**: Query that returns names → Should be redacted
4. **Reverse Engineering**: SQL with hash decoding → Should be blocked
5. **Normal Queries**: Aggregated queries → Should work normally

## Compliance

This implementation ensures:
- ✅ No PII/PHI reaches the UI
- ✅ Individual identification queries are blocked
- ✅ All database operations are read-only
- ✅ Hashed IDs cannot be reverse-engineered
- ✅ Privacy warnings are provided to users
- ✅ Data is pre-masked in analytics views

