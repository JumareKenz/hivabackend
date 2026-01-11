#!/bin/bash

# Provider RAG Endpoint Test Script
# Tests the HTTP endpoints using curl

BASE_URL="http://localhost:8000"
ENDPOINT="${BASE_URL}/api/v1/providers"

echo "============================================================"
echo "PROVIDER RAG ENDPOINT TEST"
echo "============================================================"

# Test 1: Health Check
echo ""
echo "[1] Health Check"
echo "GET ${ENDPOINT}/health"
echo "------------------------------------------------------------"
curl -s -X GET "${ENDPOINT}/health" | jq '.' || echo "Error: Server may not be running or jq not installed"
echo ""

# Test 2: Positive Query - Portal Access
echo "[2] Positive Query - Portal Access"
echo "POST ${ENDPOINT}/ask"
echo "------------------------------------------------------------"
curl -s -X POST "${ENDPOINT}/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "I can'\''t access the provider portal, what should I do?",
    "session_id": "test-123"
  }' | jq '{
    answer: .answer[:200],
    confidence: .confidence,
    confidence_score: .confidence_score,
    is_grounded: .is_grounded,
    is_refusal: .is_refusal,
    processing_time_ms: .processing_time_ms
  }' || echo "Error"
echo ""

# Test 3: Positive Query - Authorization Code
echo "[3] Positive Query - Authorization Code"
echo "POST ${ENDPOINT}/ask"
echo "------------------------------------------------------------"
curl -s -X POST "${ENDPOINT}/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "My authorization code is not showing",
    "session_id": "test-456"
  }' | jq '{
    answer: .answer[:200],
    confidence: .confidence,
    is_refusal: .is_refusal
  }' || echo "Error"
echo ""

# Test 4: Negative Query - Off-topic (Should Refuse)
echo "[4] Negative Query - Off-topic (Should Refuse)"
echo "POST ${ENDPOINT}/ask"
echo "------------------------------------------------------------"
curl -s -X POST "${ENDPOINT}/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the weather like today?",
    "session_id": "test-789"
  }' | jq '{
    answer: .answer[:200],
    confidence: .confidence,
    is_refusal: .is_refusal
  }' || echo "Error"
echo ""

# Test 5: Hallucination Test - Fake Feature (Should Refuse)
echo "[5] Hallucination Test - Fake Feature (Should Refuse)"
echo "POST ${ENDPOINT}/ask"
echo "------------------------------------------------------------"
curl -s -X POST "${ENDPOINT}/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How does the AI-powered automatic claim approval work?",
    "session_id": "test-999"
  }' | jq '{
    answer: .answer[:200],
    confidence: .confidence,
    is_refusal: .is_refusal
  }' || echo "Error"
echo ""

echo "============================================================"
echo "✅ Endpoint tests completed!"
echo "============================================================"
echo ""
echo "Endpoint URLs:"
echo "  POST ${ENDPOINT}/ask      - Query knowledge base"
echo "  GET  ${ENDPOINT}/health   - Health check"
echo "  POST ${ENDPOINT}/ingest   - Re-ingest knowledge base"
echo ""
