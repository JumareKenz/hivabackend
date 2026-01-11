# API & Event Schemas Specification

**Version:** 1.0.0  
**Date:** January 7, 2026  
**Classification:** CONFIDENTIAL - Technical Specification

---

## 1. Overview

This document defines all API contracts and event schemas for inter-service communication in the Dynamic Claims Automation Layer. All schemas are versioned, validated, and designed for backward compatibility.

---

## 2. Event Schemas (Kafka/Message Queue)

### 2.1 Claim Submitted Event

**Topic:** `claims.submitted`  
**Version:** `1.0.0`  
**Direction:** Backend → AI Engine  
**Serialization:** JSON with HMAC signature

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://hiva.claims/schemas/claim-submitted-v1.json",
  "title": "ClaimSubmittedEvent",
  "description": "Event emitted when a new claim is submitted for AI analysis",
  "type": "object",
  "required": ["envelope_version", "payload", "signature", "timestamp"],
  "properties": {
    "envelope_version": {
      "type": "string",
      "const": "1.0.0",
      "description": "Schema version for envelope structure"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time",
      "description": "ISO 8601 timestamp of event creation"
    },
    "signature": {
      "type": "string",
      "pattern": "^[a-f0-9]{64}$",
      "description": "HMAC-SHA256 signature of payload"
    },
    "payload": {
      "type": "object",
      "required": [
        "claim_id",
        "policy_id", 
        "provider_id",
        "member_id_hash",
        "procedure_codes",
        "diagnosis_codes",
        "billed_amount",
        "service_date",
        "submission_timestamp",
        "claim_type"
      ],
      "properties": {
        "claim_id": {
          "type": "string",
          "pattern": "^CLM-[0-9]{4}-[0-9]{6,12}$",
          "description": "Unique claim identifier",
          "examples": ["CLM-2026-000123456"]
        },
        "policy_id": {
          "type": "string",
          "pattern": "^POL-[A-Z0-9]{8,16}$",
          "description": "Associated policy identifier"
        },
        "provider_id": {
          "type": "string",
          "pattern": "^PRV-[A-Z0-9]{6,12}$",
          "description": "Healthcare provider identifier"
        },
        "member_id_hash": {
          "type": "string",
          "pattern": "^[a-f0-9]{64}$",
          "description": "SHA-256 hash of member ID (PII protection)"
        },
        "procedure_codes": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["code", "code_type", "quantity"],
            "properties": {
              "code": {
                "type": "string",
                "description": "Procedure code (CPT, HCPCS, etc.)"
              },
              "code_type": {
                "type": "string",
                "enum": ["CPT", "HCPCS", "ICD10_PCS", "CDT", "NDC"],
                "description": "Code classification system"
              },
              "quantity": {
                "type": "integer",
                "minimum": 1,
                "maximum": 999
              },
              "modifiers": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 4
              },
              "line_amount": {
                "type": "number",
                "minimum": 0,
                "description": "Billed amount for this line"
              }
            }
          },
          "minItems": 1,
          "maxItems": 999
        },
        "diagnosis_codes": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["code", "code_type", "sequence"],
            "properties": {
              "code": {
                "type": "string",
                "pattern": "^[A-Z][0-9]{2}(\\.[0-9A-Z]{1,4})?$",
                "description": "ICD-10-CM diagnosis code"
              },
              "code_type": {
                "type": "string",
                "enum": ["ICD10_CM", "ICD9_CM"],
                "default": "ICD10_CM"
              },
              "sequence": {
                "type": "integer",
                "minimum": 1,
                "description": "Diagnosis sequence (1 = primary)"
              }
            }
          },
          "minItems": 1,
          "maxItems": 25
        },
        "billed_amount": {
          "type": "number",
          "minimum": 0,
          "maximum": 99999999.99,
          "description": "Total billed amount in local currency"
        },
        "service_date": {
          "type": "string",
          "format": "date",
          "description": "Date service was rendered (ISO 8601)"
        },
        "service_date_end": {
          "type": "string",
          "format": "date",
          "description": "End date for date range services"
        },
        "submission_timestamp": {
          "type": "string",
          "format": "date-time",
          "description": "When claim was submitted to backend"
        },
        "claim_type": {
          "type": "string",
          "enum": ["PROFESSIONAL", "INSTITUTIONAL", "DENTAL", "PHARMACY", "VISION"],
          "description": "Type of healthcare claim"
        },
        "facility_type": {
          "type": "string",
          "enum": [
            "INPATIENT_HOSPITAL",
            "OUTPATIENT_HOSPITAL", 
            "SKILLED_NURSING",
            "PHYSICIAN_OFFICE",
            "URGENT_CARE",
            "EMERGENCY_ROOM",
            "AMBULATORY_SURGERY",
            "HOME_HEALTH",
            "PHARMACY",
            "LAB",
            "DME",
            "OTHER"
          ]
        },
        "place_of_service": {
          "type": "string",
          "pattern": "^[0-9]{2}$",
          "description": "CMS Place of Service code"
        },
        "admission_date": {
          "type": "string",
          "format": "date"
        },
        "discharge_date": {
          "type": "string",
          "format": "date"
        },
        "drg_code": {
          "type": "string",
          "pattern": "^[0-9]{3}$",
          "description": "Diagnosis Related Group (inpatient)"
        },
        "referring_provider_id": {
          "type": "string"
        },
        "prior_auth_number": {
          "type": "string",
          "description": "Prior authorization reference"
        },
        "network_status": {
          "type": "string",
          "enum": ["IN_NETWORK", "OUT_OF_NETWORK", "UNKNOWN"]
        },
        "metadata": {
          "type": "object",
          "additionalProperties": true,
          "description": "Optional additional metadata"
        }
      },
      "additionalProperties": false
    }
  }
}
```

### 2.2 Claim Analyzed Event

**Topic:** `claims.analyzed`  
**Version:** `1.0.0`  
**Direction:** AI Engine → Backend  
**Serialization:** JSON with digital signature

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://hiva.claims/schemas/claim-analyzed-v1.json",
  "title": "ClaimAnalyzedEvent",
  "description": "AI analysis result for a submitted claim",
  "type": "object",
  "required": [
    "envelope_version",
    "claim_id",
    "analysis_id",
    "timestamp",
    "recommendation",
    "confidence_score",
    "rule_results",
    "ml_results",
    "audit_trail",
    "signature"
  ],
  "properties": {
    "envelope_version": {
      "type": "string",
      "const": "1.0.0"
    },
    "claim_id": {
      "type": "string",
      "pattern": "^CLM-[0-9]{4}-[0-9]{6,12}$"
    },
    "analysis_id": {
      "type": "string",
      "format": "uuid",
      "description": "Unique identifier for this analysis"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time"
    },
    "recommendation": {
      "type": "string",
      "enum": ["APPROVE", "MANUAL_REVIEW", "DECLINE"],
      "description": "AI recommendation (advisory only)"
    },
    "confidence_score": {
      "type": "number",
      "minimum": 0,
      "maximum": 1,
      "description": "Overall confidence in recommendation"
    },
    "risk_score": {
      "type": "number",
      "minimum": 0,
      "maximum": 1,
      "description": "Combined fraud/anomaly risk score"
    },
    "rule_results": {
      "$ref": "#/definitions/RuleResults"
    },
    "ml_results": {
      "$ref": "#/definitions/MLResults"
    },
    "reasons": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["code", "severity", "message"],
        "properties": {
          "code": {
            "type": "string",
            "pattern": "^[A-Z]{3}-[0-9]{4}$"
          },
          "severity": {
            "type": "string",
            "enum": ["INFO", "WARNING", "ERROR", "CRITICAL"]
          },
          "message": {
            "type": "string"
          },
          "source": {
            "type": "string",
            "enum": ["RULE_ENGINE", "ML_ENGINE", "DECISION_ENGINE"]
          }
        }
      }
    },
    "assigned_queue": {
      "type": "string",
      "enum": [
        "AUTO_PROCESS",
        "STANDARD_REVIEW",
        "SENIOR_REVIEW",
        "FRAUD_INVESTIGATION",
        "MEDICAL_DIRECTOR"
      ],
      "description": "Queue assignment for manual review"
    },
    "processing_time_ms": {
      "type": "integer",
      "minimum": 0,
      "description": "Total processing time in milliseconds"
    },
    "audit_trail": {
      "$ref": "#/definitions/AuditTrail"
    },
    "signature": {
      "type": "string",
      "description": "Ed25519 signature of analysis results"
    }
  },
  "definitions": {
    "RuleResults": {
      "type": "object",
      "required": ["engine_version", "rules_evaluated", "outcome", "triggered_rules"],
      "properties": {
        "engine_version": {
          "type": "string",
          "pattern": "^[0-9]+\\.[0-9]+\\.[0-9]+$"
        },
        "ruleset_version": {
          "type": "string"
        },
        "rules_evaluated": {
          "type": "integer",
          "minimum": 0
        },
        "outcome": {
          "type": "string",
          "enum": ["PASS", "FAIL", "FLAG"]
        },
        "triggered_rules": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["rule_id", "rule_name", "outcome", "message"],
            "properties": {
              "rule_id": {
                "type": "string"
              },
              "rule_name": {
                "type": "string"
              },
              "rule_version": {
                "type": "string"
              },
              "category": {
                "type": "string",
                "enum": [
                  "POLICY_COVERAGE",
                  "PROVIDER_ELIGIBILITY",
                  "TARIFF_COMPLIANCE",
                  "DUPLICATE_DETECTION",
                  "TEMPORAL_VALIDATION",
                  "MEDICAL_NECESSITY",
                  "CODING_VALIDATION",
                  "BENEFIT_LIMITS"
                ]
              },
              "outcome": {
                "type": "string",
                "enum": ["PASS", "FAIL", "FLAG", "SKIP"]
              },
              "message": {
                "type": "string"
              },
              "details": {
                "type": "object"
              }
            }
          }
        },
        "execution_time_ms": {
          "type": "integer"
        }
      }
    },
    "MLResults": {
      "type": "object",
      "required": ["model_id", "model_version", "risk_score", "confidence"],
      "properties": {
        "model_id": {
          "type": "string"
        },
        "model_version": {
          "type": "string"
        },
        "model_hash": {
          "type": "string",
          "pattern": "^sha256:[a-f0-9]{64}$"
        },
        "risk_score": {
          "type": "number",
          "minimum": 0,
          "maximum": 1
        },
        "confidence": {
          "type": "number",
          "minimum": 0,
          "maximum": 1
        },
        "risk_factors": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["factor", "contribution", "description"],
            "properties": {
              "factor": {
                "type": "string"
              },
              "contribution": {
                "type": "number"
              },
              "value": {
                "type": ["number", "string", "boolean"]
              },
              "threshold": {
                "type": "number"
              },
              "description": {
                "type": "string"
              }
            }
          }
        },
        "anomaly_indicators": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "indicator_type": {
                "type": "string",
                "enum": [
                  "COST_ANOMALY",
                  "FREQUENCY_ANOMALY",
                  "PATTERN_ANOMALY",
                  "PROVIDER_ANOMALY",
                  "TEMPORAL_ANOMALY",
                  "CODING_ANOMALY"
                ]
              },
              "severity": {
                "type": "string",
                "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
              },
              "score": {
                "type": "number"
              },
              "explanation": {
                "type": "string"
              }
            }
          }
        },
        "execution_time_ms": {
          "type": "integer"
        }
      }
    },
    "AuditTrail": {
      "type": "object",
      "required": ["trace_id", "stages", "integrity_hash"],
      "properties": {
        "trace_id": {
          "type": "string",
          "format": "uuid"
        },
        "correlation_id": {
          "type": "string"
        },
        "stages": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["stage", "timestamp", "status"],
            "properties": {
              "stage": {
                "type": "string",
                "enum": [
                  "RECEIVED",
                  "VALIDATED",
                  "RULES_STARTED",
                  "RULES_COMPLETED",
                  "ML_STARTED",
                  "ML_COMPLETED",
                  "SYNTHESIS_STARTED",
                  "SYNTHESIS_COMPLETED",
                  "PUBLISHED"
                ]
              },
              "timestamp": {
                "type": "string",
                "format": "date-time"
              },
              "status": {
                "type": "string",
                "enum": ["SUCCESS", "FAILURE", "SKIPPED"]
              },
              "duration_ms": {
                "type": "integer"
              },
              "details": {
                "type": "object"
              }
            }
          }
        },
        "integrity_hash": {
          "type": "string",
          "pattern": "^sha256:[a-f0-9]{64}$"
        },
        "previous_hash": {
          "type": "string"
        }
      }
    }
  }
}
```

### 2.3 Manual Review Decision Event

**Topic:** `claims.reviewed`  
**Version:** `1.0.0`  
**Direction:** Admin Portal → AI Engine → Backend

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://hiva.claims/schemas/claim-reviewed-v1.json",
  "title": "ClaimReviewedEvent",
  "description": "Manual review decision from admin portal",
  "type": "object",
  "required": [
    "envelope_version",
    "claim_id",
    "analysis_id",
    "review_id",
    "timestamp",
    "decision",
    "reviewer",
    "signature"
  ],
  "properties": {
    "envelope_version": {
      "type": "string",
      "const": "1.0.0"
    },
    "claim_id": {
      "type": "string"
    },
    "analysis_id": {
      "type": "string",
      "format": "uuid"
    },
    "review_id": {
      "type": "string",
      "format": "uuid"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time"
    },
    "decision": {
      "type": "string",
      "enum": ["APPROVE", "DECLINE", "ESCALATE", "REQUEST_INFO"],
      "description": "Reviewer's final decision"
    },
    "decision_amount": {
      "type": "number",
      "minimum": 0,
      "description": "Approved amount (may differ from billed)"
    },
    "adjustment_reason": {
      "type": "string",
      "enum": [
        "FULL_APPROVAL",
        "PARTIAL_APPROVAL",
        "BUNDLING_ADJUSTMENT",
        "FEE_SCHEDULE_ADJUSTMENT",
        "MEDICAL_NECESSITY_DENIAL",
        "COVERAGE_DENIAL",
        "DUPLICATE_DENIAL",
        "FRAUD_DENIAL",
        "OTHER"
      ]
    },
    "notes": {
      "type": "string",
      "maxLength": 4000
    },
    "override_flags": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["flag_type", "original_value", "override_value", "justification"],
        "properties": {
          "flag_type": {
            "type": "string"
          },
          "original_value": {
            "type": "string"
          },
          "override_value": {
            "type": "string"
          },
          "justification": {
            "type": "string"
          }
        }
      }
    },
    "reviewer": {
      "type": "object",
      "required": ["user_id", "role", "timestamp"],
      "properties": {
        "user_id": {
          "type": "string"
        },
        "role": {
          "type": "string",
          "enum": [
            "CLAIMS_PROCESSOR",
            "SENIOR_PROCESSOR",
            "SUPERVISOR",
            "FRAUD_INVESTIGATOR",
            "MEDICAL_DIRECTOR",
            "COMPLIANCE_OFFICER"
          ]
        },
        "timestamp": {
          "type": "string",
          "format": "date-time"
        },
        "session_id": {
          "type": "string"
        }
      }
    },
    "review_duration_seconds": {
      "type": "integer"
    },
    "signature": {
      "type": "string"
    }
  }
}
```

### 2.4 Training Feedback Event

**Topic:** `claims.feedback`  
**Version:** `1.0.0`  
**Direction:** Admin Portal → Training Store

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://hiva.claims/schemas/claim-feedback-v1.json",
  "title": "ClaimFeedbackEvent",
  "description": "Training feedback for ML model improvement",
  "type": "object",
  "required": [
    "envelope_version",
    "feedback_id",
    "claim_id",
    "analysis_id",
    "timestamp",
    "feedback_type",
    "ground_truth"
  ],
  "properties": {
    "envelope_version": {
      "type": "string",
      "const": "1.0.0"
    },
    "feedback_id": {
      "type": "string",
      "format": "uuid"
    },
    "claim_id": {
      "type": "string"
    },
    "analysis_id": {
      "type": "string",
      "format": "uuid"
    },
    "review_id": {
      "type": "string",
      "format": "uuid"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time"
    },
    "feedback_type": {
      "type": "string",
      "enum": [
        "CORRECT_PREDICTION",
        "FALSE_POSITIVE",
        "FALSE_NEGATIVE",
        "PARTIAL_AGREEMENT",
        "RULE_OVERRIDE",
        "ML_OVERRIDE"
      ]
    },
    "ground_truth": {
      "type": "object",
      "required": ["final_decision", "is_fraudulent"],
      "properties": {
        "final_decision": {
          "type": "string",
          "enum": ["APPROVED", "DECLINED", "PARTIAL"]
        },
        "is_fraudulent": {
          "type": "boolean"
        },
        "fraud_type": {
          "type": "string",
          "enum": [
            "NONE",
            "UPCODING",
            "UNBUNDLING",
            "PHANTOM_BILLING",
            "DUPLICATE_BILLING",
            "IDENTITY_FRAUD",
            "KICKBACK",
            "MEDICALLY_UNNECESSARY",
            "OTHER"
          ]
        },
        "confidence": {
          "type": "number",
          "minimum": 0,
          "maximum": 1
        }
      }
    },
    "model_performance": {
      "type": "object",
      "properties": {
        "prediction_correct": {
          "type": "boolean"
        },
        "risk_score_accuracy": {
          "type": "number"
        },
        "feature_feedback": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "feature_name": {
                "type": "string"
              },
              "was_useful": {
                "type": "boolean"
              },
              "comments": {
                "type": "string"
              }
            }
          }
        }
      }
    },
    "metadata": {
      "type": "object",
      "properties": {
        "reviewer_experience_level": {
          "type": "string"
        },
        "review_difficulty": {
          "type": "string",
          "enum": ["EASY", "MODERATE", "DIFFICULT", "COMPLEX"]
        },
        "additional_context": {
          "type": "string"
        }
      }
    }
  }
}
```

---

## 3. REST API Specifications

### 3.1 AI Engine Internal API

**Base URL:** `https://ai-engine.internal.hiva.claims/api/v1`  
**Authentication:** mTLS + JWT Bearer Token

#### 3.1.1 Health Endpoints

```yaml
openapi: 3.0.3
info:
  title: Claims AI Engine API
  version: 1.0.0

paths:
  /health/live:
    get:
      summary: Liveness check
      tags: [Health]
      security: []
      responses:
        '200':
          description: Service is alive
          content:
            application/json:
              schema:
                type: object
                properties:
                  status:
                    type: string
                    enum: [ALIVE]
                  timestamp:
                    type: string
                    format: date-time
        '503':
          description: Service unavailable

  /health/ready:
    get:
      summary: Readiness check
      tags: [Health]
      security: []
      responses:
        '200':
          description: Service is ready
          content:
            application/json:
              schema:
                type: object
                properties:
                  status:
                    type: string
                    enum: [READY, DEGRADED]
                  components:
                    type: object
                    additionalProperties:
                      type: object
                      properties:
                        status:
                          type: string
                        latency_ms:
                          type: integer
                  degradation_level:
                    type: string
        '503':
          description: Service not ready

  /health/detailed:
    get:
      summary: Detailed health status
      tags: [Health]
      security:
        - bearerAuth: []
      responses:
        '200':
          description: Detailed health information
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/DetailedHealth'
```

#### 3.1.2 Analysis Endpoints

```yaml
  /analysis/{claim_id}:
    get:
      summary: Get analysis result for a claim
      tags: [Analysis]
      security:
        - bearerAuth: []
      parameters:
        - name: claim_id
          in: path
          required: true
          schema:
            type: string
      responses:
        '200':
          description: Analysis result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ClaimAnalysis'
        '404':
          description: Analysis not found

  /analysis/{claim_id}/audit-trail:
    get:
      summary: Get complete audit trail for a claim
      tags: [Analysis, Audit]
      security:
        - bearerAuth: []
      parameters:
        - name: claim_id
          in: path
          required: true
          schema:
            type: string
      responses:
        '200':
          description: Complete audit trail
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/AuditTrail'

  /analysis/batch:
    post:
      summary: Submit batch of claims for analysis (webhook fallback)
      tags: [Analysis]
      security:
        - bearerAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                claims:
                  type: array
                  items:
                    $ref: '#/components/schemas/ClaimSubmission'
                  maxItems: 100
                callback_url:
                  type: string
                  format: uri
      responses:
        '202':
          description: Batch accepted for processing
          content:
            application/json:
              schema:
                type: object
                properties:
                  batch_id:
                    type: string
                    format: uuid
                  claims_accepted:
                    type: integer
                  estimated_completion:
                    type: string
                    format: date-time
```

#### 3.1.3 Rule Engine Endpoints

```yaml
  /rules/validate:
    post:
      summary: Validate a claim against rules (sync, for testing)
      tags: [Rules]
      security:
        - bearerAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ClaimSubmission'
      responses:
        '200':
          description: Validation result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/RuleValidationResult'

  /rules/versions:
    get:
      summary: List rule set versions
      tags: [Rules]
      security:
        - bearerAuth: []
      responses:
        '200':
          description: Available rule set versions
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: '#/components/schemas/RuleSetVersion'

  /rules/{rule_id}:
    get:
      summary: Get rule definition
      tags: [Rules]
      security:
        - bearerAuth: []
      parameters:
        - name: rule_id
          in: path
          required: true
          schema:
            type: string
      responses:
        '200':
          description: Rule definition
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/RuleDefinition'
```

#### 3.1.4 ML Engine Endpoints

```yaml
  /ml/models:
    get:
      summary: List deployed models
      tags: [ML]
      security:
        - bearerAuth: []
      responses:
        '200':
          description: Deployed models
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: '#/components/schemas/ModelInfo'

  /ml/models/{model_id}/explain:
    post:
      summary: Get model explanation for a claim
      tags: [ML]
      security:
        - bearerAuth: []
      parameters:
        - name: model_id
          in: path
          required: true
          schema:
            type: string
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ClaimSubmission'
      responses:
        '200':
          description: Model explanation
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ModelExplanation'
```

### 3.2 Admin Portal API

**Base URL:** `https://admin.hiva.claims/api/v1`  
**Authentication:** OIDC + JWT Bearer Token

```yaml
openapi: 3.0.3
info:
  title: Claims Admin Portal API
  version: 1.0.0

paths:
  /review-queue:
    get:
      summary: Get claims awaiting review
      tags: [Review]
      security:
        - bearerAuth: []
      parameters:
        - name: queue
          in: query
          schema:
            type: string
            enum: [STANDARD_REVIEW, SENIOR_REVIEW, FRAUD_INVESTIGATION, MEDICAL_DIRECTOR]
        - name: priority
          in: query
          schema:
            type: string
            enum: [LOW, MEDIUM, HIGH, CRITICAL]
        - name: assigned_to
          in: query
          schema:
            type: string
        - name: page
          in: query
          schema:
            type: integer
            default: 1
        - name: page_size
          in: query
          schema:
            type: integer
            default: 20
            maximum: 100
      responses:
        '200':
          description: Review queue items
          content:
            application/json:
              schema:
                type: object
                properties:
                  items:
                    type: array
                    items:
                      $ref: '#/components/schemas/ReviewQueueItem'
                  total:
                    type: integer
                  page:
                    type: integer
                  page_size:
                    type: integer

  /review-queue/{claim_id}/claim:
    post:
      summary: Claim a review item (assign to self)
      tags: [Review]
      security:
        - bearerAuth: []
      parameters:
        - name: claim_id
          in: path
          required: true
          schema:
            type: string
      responses:
        '200':
          description: Claim assigned
        '409':
          description: Claim already assigned

  /review-queue/{claim_id}/decision:
    post:
      summary: Submit review decision
      tags: [Review]
      security:
        - bearerAuth: []
      parameters:
        - name: claim_id
          in: path
          required: true
          schema:
            type: string
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ReviewDecision'
      responses:
        '200':
          description: Decision recorded
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ReviewDecisionResponse'
        '400':
          description: Invalid decision
        '403':
          description: Insufficient permissions

  /audit/claims/{claim_id}:
    get:
      summary: Get complete audit history for a claim
      tags: [Audit]
      security:
        - bearerAuth: []
      parameters:
        - name: claim_id
          in: path
          required: true
          schema:
            type: string
      responses:
        '200':
          description: Audit history
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ClaimAuditHistory'

  /audit/export:
    post:
      summary: Export audit data for compliance reporting
      tags: [Audit]
      security:
        - bearerAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                start_date:
                  type: string
                  format: date
                end_date:
                  type: string
                  format: date
                format:
                  type: string
                  enum: [JSON, CSV, PDF]
                include_pii:
                  type: boolean
                  default: false
      responses:
        '202':
          description: Export job started
          content:
            application/json:
              schema:
                type: object
                properties:
                  job_id:
                    type: string
                    format: uuid
                  estimated_completion:
                    type: string
                    format: date-time

components:
  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT

  schemas:
    ReviewQueueItem:
      type: object
      properties:
        claim_id:
          type: string
        analysis_id:
          type: string
        queue:
          type: string
        priority:
          type: string
        recommendation:
          type: string
        confidence_score:
          type: number
        risk_score:
          type: number
        billed_amount:
          type: number
        key_flags:
          type: array
          items:
            type: string
        assigned_to:
          type: string
        queued_at:
          type: string
          format: date-time
        sla_deadline:
          type: string
          format: date-time

    ReviewDecision:
      type: object
      required: [decision, justification]
      properties:
        decision:
          type: string
          enum: [APPROVE, DECLINE, ESCALATE, REQUEST_INFO]
        approved_amount:
          type: number
        adjustment_reason:
          type: string
        justification:
          type: string
          minLength: 10
          maxLength: 4000
        override_flags:
          type: array
          items:
            type: object
            properties:
              flag_type:
                type: string
              override_value:
                type: string
              override_justification:
                type: string

    ReviewDecisionResponse:
      type: object
      properties:
        review_id:
          type: string
          format: uuid
        claim_id:
          type: string
        decision:
          type: string
        recorded_at:
          type: string
          format: date-time
        audit_reference:
          type: string
```

---

## 4. Schema Versioning Strategy

### 4.1 Versioning Policy

| Change Type | Version Bump | Backward Compatible |
|-------------|--------------|---------------------|
| Add optional field | MINOR | Yes |
| Add enum value | MINOR | Yes |
| Rename field | MAJOR | No |
| Remove field | MAJOR | No |
| Change field type | MAJOR | No |
| Add required field | MAJOR | No |

### 4.2 Version Migration

```python
class SchemaVersionMigrator:
    """Handles schema version migrations for backward compatibility."""
    
    MIGRATIONS = {
        ("1.0.0", "1.1.0"): migrate_1_0_to_1_1,
        ("1.1.0", "1.2.0"): migrate_1_1_to_1_2,
    }
    
    def migrate(self, data: dict, from_version: str, to_version: str) -> dict:
        """Migrate data between schema versions."""
        current = from_version
        
        while current != to_version:
            migration_key = (current, self._next_version(current, to_version))
            if migration_key not in self.MIGRATIONS:
                raise ValueError(f"No migration path from {current} to {to_version}")
            
            migration_fn = self.MIGRATIONS[migration_key]
            data = migration_fn(data)
            current = migration_key[1]
        
        return data
```

---

## 5. Error Response Schema

### 5.1 Standard Error Format

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://hiva.claims/schemas/error-response-v1.json",
  "title": "ErrorResponse",
  "type": "object",
  "required": ["error"],
  "properties": {
    "error": {
      "type": "object",
      "required": ["code", "message", "timestamp"],
      "properties": {
        "code": {
          "type": "string",
          "pattern": "^[A-Z]+_[A-Z0-9_]+$",
          "examples": ["VALIDATION_ERROR", "AUTH_INVALID_TOKEN", "RATE_LIMIT_EXCEEDED"]
        },
        "message": {
          "type": "string"
        },
        "details": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "field": {
                "type": "string"
              },
              "code": {
                "type": "string"
              },
              "message": {
                "type": "string"
              }
            }
          }
        },
        "timestamp": {
          "type": "string",
          "format": "date-time"
        },
        "trace_id": {
          "type": "string",
          "format": "uuid"
        },
        "documentation_url": {
          "type": "string",
          "format": "uri"
        }
      }
    }
  }
}
```

### 5.2 Error Code Reference

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 400 | Request validation failed |
| `SCHEMA_VERSION_MISMATCH` | 400 | Unsupported schema version |
| `AUTH_MISSING_TOKEN` | 401 | No authentication provided |
| `AUTH_INVALID_TOKEN` | 401 | Token validation failed |
| `AUTH_EXPIRED_TOKEN` | 401 | Token has expired |
| `FORBIDDEN` | 403 | Insufficient permissions |
| `NOT_FOUND` | 404 | Resource not found |
| `CONFLICT` | 409 | Resource state conflict |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests |
| `INTERNAL_ERROR` | 500 | Internal server error |
| `SERVICE_UNAVAILABLE` | 503 | Service temporarily unavailable |
| `SIGNATURE_INVALID` | 400 | Message signature verification failed |
| `CLAIM_ALREADY_PROCESSED` | 409 | Claim has already been processed |

---

**END OF API & EVENT SCHEMAS SPECIFICATION**


