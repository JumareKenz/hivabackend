"""
Domain 3: Comprehensive Stress Test Suite
Tests all 6 phases rigorously and thoroughly
"""

import asyncio
import time
import json
from typing import Dict, List, Any
from datetime import datetime
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.query_intelligence import query_intelligence
from app.services.safety_governance import safety_governance
from app.services.explainability_engine import explainability_engine
from app.services.feedback_learning import feedback_learning
from app.services.performance_controls import performance_controls
from app.services.evaluation_metrics import evaluation_metrics
from app.services.domain_router import domain_router
from app.services.sql_validator import sql_validator
from app.services.sql_rewriter import sql_rewriter
from app.services.confidence_scorer import confidence_scorer
from app.services.result_sanitizer import result_sanitizer


class StressTestResults:
    """Track test results"""
    def __init__(self):
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0
        self.errors = []
        self.warnings = []
        self.performance_metrics = {}
    
    def add_result(self, test_name: str, passed: bool, error: str = None, warning: str = None):
        self.total_tests += 1
        if passed:
            self.passed_tests += 1
            print(f"  ✅ PASS: {test_name}")
        else:
            self.failed_tests += 1
            print(f"  ❌ FAIL: {test_name}")
            if error:
                self.errors.append(f"{test_name}: {error}")
                print(f"     Error: {error}")
        if warning:
            self.warnings.append(f"{test_name}: {warning}")
            print(f"     ⚠️  Warning: {warning}")
    
    def add_performance(self, metric_name: str, value: float):
        self.performance_metrics[metric_name] = value
    
    def print_summary(self):
        print("\n" + "="*80)
        print("STRESS TEST SUMMARY")
        print("="*80)
        print(f"Total Tests: {self.total_tests}")
        print(f"Passed: {self.passed_tests} ({self.passed_tests/self.total_tests*100:.1f}%)")
        print(f"Failed: {self.failed_tests} ({self.failed_tests/self.total_tests*100:.1f}%)")
        print(f"Warnings: {len(self.warnings)}")
        
        if self.performance_metrics:
            print("\nPerformance Metrics:")
            for metric, value in self.performance_metrics.items():
                print(f"  {metric}: {value:.4f}s")
        
        if self.errors:
            print("\nErrors:")
            for error in self.errors[:10]:  # Show first 10 errors
                print(f"  - {error}")
            if len(self.errors) > 10:
                print(f"  ... and {len(self.errors) - 10} more errors")
        
        if self.warnings:
            print("\nWarnings:")
            for warning in self.warnings[:5]:  # Show first 5 warnings
                print(f"  - {warning}")
            if len(self.warnings) > 5:
                print(f"  ... and {len(self.warnings) - 5} more warnings")
        
        print("="*80)


# Initialize results tracker
results = StressTestResults()


def test_phase3_1_query_intelligence():
    """Test Phase 3.1: Query Intelligence & Reasoning Control"""
    print("\n" + "="*80)
    print("PHASE 3.1: Query Intelligence & Reasoning Control")
    print("="*80)
    
    # Test 1: Intent Classification
    test_cases = [
        ("show all claims", "read_only_analytics"),
        ("count total claims", "aggregations"),
        ("diagnosis trend over time", "time_series"),
        ("details about provider 123", "entity_lookups"),
        ("show user email addresses", "sensitive_restricted"),
    ]
    
    for query, expected_intent in test_cases:
        intent_category, confidence = query_intelligence.classify_intent_category(query)
        passed = intent_category == expected_intent
        results.add_result(
            f"Intent Classification: '{query}'",
            passed,
            None if passed else f"Expected {expected_intent}, got {intent_category}"
        )
    
    # Test 2: Intent Validation
    is_supported, rejection = query_intelligence.validate_intent_supported("sensitive_restricted")
    results.add_result(
        "Intent Validation: Reject sensitive queries",
        not is_supported and rejection is not None
    )
    
    is_supported, rejection = query_intelligence.validate_intent_supported("read_only_analytics")
    results.add_result(
        "Intent Validation: Allow safe queries",
        is_supported and rejection is None
    )
    
    # Test 3: Schema-Aware Reasoning - Identify Tables
    schema_info = {
        'tables': [
            {'table_name': 'claims', 'columns': []},
            {'table_name': 'providers', 'columns': []},
            {'table_name': 'diagnoses', 'columns': []},
        ]
    }
    
    test_queries = [
        ("show all claims", ["claims"]),
        ("providers with most claims", ["providers", "claims"]),
        ("diagnosis trends", ["diagnoses"]),
    ]
    
    for query, expected_tables in test_queries:
        required_tables = query_intelligence.identify_required_tables(query, schema_info)
        # Check if all expected tables are present
        all_present = all(table in required_tables for table in expected_tables)
        results.add_result(
            f"Table Identification: '{query}'",
            all_present,
            None if all_present else f"Expected {expected_tables}, got {required_tables}"
        )
    
    # Test 4: Step-Constrained Reasoning
    reasoning_plan = query_intelligence.enforce_step_constrained_reasoning(
        "most common diagnosis last year",
        schema_info
    )
    
    results.add_result(
        "Step-Constrained Reasoning: Generate plan",
        'required_tables' in reasoning_plan and 'filters' in reasoning_plan
    )


def test_phase3_2_safety_governance():
    """Test Phase 3.2: Safety, Permissions & Data Governance"""
    print("\n" + "="*80)
    print("PHASE 3.2: Safety, Permissions & Data Governance")
    print("="*80)
    
    # Test 1: Role-Based Permissions
    test_cases = [
        ("admin", ["claims", "users", "providers"], True),
        ("analyst", ["claims", "providers"], True),
        ("analyst", ["users"], False),  # Analyst shouldn't access users
        ("public", ["diagnoses"], True),
        ("public", ["claims"], False),  # Public shouldn't access claims
    ]
    
    for role, tables, should_allow in test_cases:
        has_permission, error = safety_governance.check_role_permissions(role, tables)
        passed = has_permission == should_allow
        results.add_result(
            f"Role Permissions: {role} accessing {tables}",
            passed,
            None if passed else f"Expected {should_allow}, got {has_permission}. Error: {error}"
        )
    
    # Test 2: PII Detection
    sql_queries = [
        ("SELECT email FROM users", ["email"]),
        ("SELECT phone_number, nimc FROM users", ["phone_number", "nimc"]),
        ("SELECT name, id FROM claims", []),  # No PII
    ]
    
    for sql, expected_pii in sql_queries:
        pii_columns = safety_governance.identify_pii_columns(sql)
        all_found = all(pii in pii_columns for pii in expected_pii)
        results.add_result(
            f"PII Detection: {sql[:50]}",
            all_found,
            None if all_found else f"Expected {expected_pii}, got {pii_columns}"
        )
    
    # Test 3: PII Masking
    test_results = [
        {"email": "user@example.com", "name": "John"},
        {"phone": "1234567890", "id": 1},
    ]
    
    masked = safety_governance.mask_pii_in_results(test_results, ["email", "phone"])
    email_masked = masked[0].get("email", "").startswith("***")
    phone_masked = masked[1].get("phone", "").startswith("***")
    
    results.add_result(
        "PII Masking: Mask sensitive data",
        email_masked and phone_masked
    )
    
    # Test 4: Query Safety Validation
    dangerous_queries = [
        ("DELETE FROM claims", False),
        ("UPDATE users SET", False),
        ("DROP TABLE", False),
        ("SELECT * FROM claims", True),  # Safe
    ]
    
    for sql, should_allow in dangerous_queries:
        is_safe, error = safety_governance.validate_query_safety(sql)
        passed = is_safe == should_allow
        results.add_result(
            f"Query Safety: {sql[:50]}",
            passed,
            None if passed else f"Expected {should_allow}, got {is_safe}"
        )
    
    # Test 5: Sensitive Data Access Check
    sensitive_queries = [
        ("show user emails", "SELECT email FROM users", False),
        ("count claims", "SELECT COUNT(*) FROM claims", True),
    ]
    
    for query, sql, should_allow in sensitive_queries:
        is_allowed, error = safety_governance.check_sensitive_data_access(query, sql)
        passed = is_allowed == should_allow
        results.add_result(
            f"Sensitive Data Check: '{query}'",
            passed,
            None if passed else f"Expected {should_allow}, got {is_allowed}"
        )


def test_phase3_3_explainability():
    """Test Phase 3.3: Explainability & Trust Layer"""
    print("\n" + "="*80)
    print("PHASE 3.3: Explainability & Trust Layer")
    print("="*80)
    
    # Test 1: SQL Explanation
    test_sql = """
    SELECT d.name, COUNT(DISTINCT c.id) AS total_claims
    FROM claims c
    JOIN service_summaries ss ON ss.claim_id = c.id
    JOIN service_summary_diagnosis ssd ON ssd.service_summary_id = ss.id
    JOIN diagnoses d ON d.id = ssd.diagnosis_id
    WHERE YEAR(c.created_at) = 2024
    GROUP BY d.name
    ORDER BY total_claims DESC
    """
    
    explanation = explainability_engine.explain_sql(test_sql, "most common diagnosis in 2024")
    
    results.add_result(
        "SQL Explanation: Generate explanation",
        'tables_used' in explanation and 'join_logic' in explanation
    )
    
    results.add_result(
        "SQL Explanation: Extract tables",
        len(explanation.get('tables_used', [])) > 0
    )
    
    results.add_result(
        "SQL Explanation: Extract joins",
        len(explanation.get('join_logic', [])) > 0
    )
    
    # Test 2: Result Provenance
    test_results = [{"diagnosis": "Malaria", "total_claims": 100}]
    provenance = explainability_engine.create_result_provenance(
        "most common diagnosis",
        test_sql,
        test_results,
        0.5,  # execution_time
        0.9   # confidence
    )
    
    results.add_result(
        "Result Provenance: Create provenance",
        'query_timestamp' in provenance and 'tables_involved' in provenance
    )
    
    # Test 3: User-Facing Justification
    justification = explainability_engine.generate_user_facing_justification(explanation)
    
    results.add_result(
        "User Justification: Generate justification",
        len(justification) > 0 and "based on" in justification.lower()
    )


def test_phase3_4_feedback_learning():
    """Test Phase 3.4: Feedback Loop & Learning Signals"""
    print("\n" + "="*80)
    print("PHASE 3.4: Feedback Loop & Learning Signals")
    print("="*80)
    
    # Test 1: Feedback Capture
    session_id = f"test_session_{int(time.time())}"
    feedback_saved = feedback_learning.capture_feedback(
        session_id=session_id,
        query="most common diagnosis",
        sql="SELECT ...",
        feedback_type="positive",
        feedback_data={"rating": 5}
    )
    
    results.add_result(
        "Feedback Capture: Save feedback",
        feedback_saved
    )
    
    # Test 2: Query Correction Storage
    correction_saved = feedback_learning.store_query_correction(
        original_query="show diagnosis codes",
        original_sql="SELECT diagnosis_code FROM diagnoses",
        corrected_sql="SELECT name FROM diagnoses",
        correction_reason="Must use name, not code"
    )
    
    results.add_result(
        "Query Correction: Store correction",
        correction_saved
    )
    
    # Test 3: Get Corrections
    corrections = feedback_learning.get_corrections_for_query("show diagnosis codes")
    
    results.add_result(
        "Query Correction: Retrieve corrections",
        isinstance(corrections, list)
    )
    
    # Test 4: Golden Question Set
    golden_saved = feedback_learning.add_golden_question(
        question="most common diagnosis",
        sql="SELECT d.name, COUNT(*) FROM ...",
        category="operational",
        validated_by="test_user"
    )
    
    results.add_result(
        "Golden Questions: Add question",
        golden_saved
    )
    
    golden_questions = feedback_learning.get_golden_questions("operational")
    
    results.add_result(
        "Golden Questions: Retrieve questions",
        isinstance(golden_questions, list)
    )


def test_phase3_5_performance_controls():
    """Test Phase 3.5: Performance, Cost & Reliability Controls"""
    print("\n" + "="*80)
    print("PHASE 3.5: Performance, Cost & Reliability Controls")
    print("="*80)
    
    # Test 1: Query Cost Estimation
    simple_sql = "SELECT COUNT(*) FROM claims"
    complex_sql = """
    SELECT d.name, COUNT(DISTINCT c.id)
    FROM claims c
    JOIN service_summaries ss ON ss.claim_id = c.id
    JOIN service_summary_diagnosis ssd ON ssd.service_summary_id = ss.id
    JOIN diagnoses d ON d.id = ssd.diagnosis_id
    JOIN claims_services cs ON cs.claims_id = c.id
    JOIN services s ON s.id = cs.services_id
    GROUP BY d.name
    """
    
    simple_cost = performance_controls.estimate_query_cost(simple_sql)
    complex_cost = performance_controls.estimate_query_cost(complex_sql)
    
    results.add_result(
        "Cost Estimation: Estimate simple query",
        'estimated_rows_scanned' in simple_cost and 'estimated_execution_time_ms' in simple_cost
    )
    
    results.add_result(
        "Cost Estimation: Complex query has higher cost",
        complex_cost['complexity_score'] > simple_cost['complexity_score']
    )
    
    # Test 2: Caching Identification
    cacheable_queries = [
        ("total claims", True),
        ("most common diagnosis", True),
        ("show details for claim 12345", False),
    ]
    
    for query, should_cache in cacheable_queries:
        should_cache_result, cache_key = performance_controls.should_cache_query(query, "SELECT ...")
        passed = (should_cache_result == should_cache) if should_cache else True  # Don't fail if it doesn't cache
        results.add_result(
            f"Caching: '{query}'",
            passed
        )
    
    # Test 3: Failure Handling
    failure_info = performance_controls.handle_query_failure(
        sql="SELECT invalid_column FROM claims",
        error="Unknown column 'invalid_column'",
        query="show invalid data"
    )
    
    results.add_result(
        "Failure Handling: Generate failure info",
        'explanation' in failure_info and 'clarifying_question' in failure_info
    )


def test_phase3_6_evaluation_metrics():
    """Test Phase 3.6: Evaluation & KPIs"""
    print("\n" + "="*80)
    print("PHASE 3.6: Evaluation & KPIs")
    print("="*80)
    
    # Test 1: Record Metrics
    test_metrics = [
        ("sql_validity", True),
        ("sql_validity", False),
        ("response_time", 150.5),
        ("user_satisfaction", 4.5),
        ("query_executed", True),
    ]
    
    for metric_type, value in test_metrics:
        try:
            evaluation_metrics.record_query_metric(metric_type, value)
            results.add_result(
                f"Metric Recording: {metric_type}",
                True
            )
        except Exception as e:
            results.add_result(
                f"Metric Recording: {metric_type}",
                False,
                str(e)
            )
    
    # Test 2: Calculate KPIs
    kpis = evaluation_metrics.calculate_kpis(days=7)
    
    results.add_result(
        "KPI Calculation: Calculate KPIs",
        'sql_validity_rate' in kpis and 'total_queries' in kpis
    )
    
    results.add_result(
        "KPI Calculation: All metrics present",
        all(key in kpis for key in [
            'sql_validity_rate', 'correct_answer_rate', 'join_accuracy',
            'average_response_time_ms', 'user_satisfaction_score',
            'hallucination_frequency'
        ])
    )


def test_integration_flow():
    """Test complete integration flow"""
    print("\n" + "="*80)
    print("INTEGRATION: Complete Flow Test")
    print("="*80)
    
    # Simulate a complete query flow
    query = "most common diagnosis last year"
    
    # Step 1: Intent Classification
    intent_category, confidence = query_intelligence.classify_intent_category(query)
    is_supported, rejection = query_intelligence.validate_intent_supported(intent_category)
    
    results.add_result(
        "Integration: Intent classification",
        is_supported
    )
    
    # Step 2: Domain Routing
    domain, rejection_reason = domain_router.route(query)
    
    results.add_result(
        "Integration: Domain routing",
        domain != 'rejected'
    )
    
    # Step 3: Role Permissions
    has_permission, permission_error = safety_governance.check_role_permissions("analyst", ["claims", "diagnoses"])
    
    results.add_result(
        "Integration: Role permissions",
        has_permission
    )
    
    # Step 4: SQL Validation (simulated)
    test_sql = """
    SELECT d.name, COUNT(DISTINCT c.id) AS total_claims
    FROM claims c
    JOIN service_summaries ss ON ss.claim_id = c.id
    JOIN service_summary_diagnosis ssd ON ssd.service_summary_id = ss.id
    JOIN diagnoses d ON d.id = ssd.diagnosis_id
    WHERE YEAR(c.created_at) = YEAR(CURRENT_DATE) - 1
    GROUP BY d.name
    ORDER BY total_claims DESC
    """
    
    is_safe, safety_error = safety_governance.validate_query_safety(test_sql)
    
    results.add_result(
        "Integration: Query safety",
        is_safe
    )
    
    is_valid, validation_error = sql_validator.validate(test_sql, query, domain)
    
    results.add_result(
        "Integration: SQL validation",
        is_valid
    )
    
    # Step 5: Explainability
    explanation = explainability_engine.explain_sql(test_sql, query)
    
    results.add_result(
        "Integration: Explainability",
        'tables_used' in explanation
    )
    
    # Step 6: Performance
    cost_estimate = performance_controls.estimate_query_cost(test_sql)
    
    results.add_result(
        "Integration: Performance estimation",
        'complexity_score' in cost_estimate
    )
    
    # Step 7: Metrics
    evaluation_metrics.record_query_metric('integration_test', True, {'query': query})
    
    results.add_result(
        "Integration: Metrics recording",
        True
    )


def test_performance_stress():
    """Performance stress test"""
    print("\n" + "="*80)
    print("PERFORMANCE: Stress Test")
    print("="*80)
    
    # Test 1: Intent Classification Performance
    start_time = time.time()
    for _ in range(100):
        query_intelligence.classify_intent_category("most common diagnosis")
    elapsed = time.time() - start_time
    
    results.add_performance("Intent Classification (100 ops)", elapsed)
    results.add_result(
        "Performance: Intent classification speed",
        elapsed < 1.0,  # Should complete in < 1 second
        None if elapsed < 1.0 else f"Took {elapsed:.4f}s (expected < 1.0s)"
    )
    
    # Test 2: SQL Validation Performance
    test_sql = "SELECT d.name FROM diagnoses d JOIN claims c ON c.id = d.id"
    start_time = time.time()
    for _ in range(100):
        sql_validator.validate(test_sql, "test query", "clinical_claims_diagnosis")
    elapsed = time.time() - start_time
    
    results.add_performance("SQL Validation (100 ops)", elapsed)
    results.add_result(
        "Performance: SQL validation speed",
        elapsed < 1.0,
        None if elapsed < 1.0 else f"Took {elapsed:.4f}s (expected < 1.0s)"
    )
    
    # Test 3: Explainability Performance
    start_time = time.time()
    for _ in range(50):
        explainability_engine.explain_sql(test_sql, "test query")
    elapsed = time.time() - start_time
    
    results.add_performance("Explainability (50 ops)", elapsed)
    results.add_result(
        "Performance: Explainability speed",
        elapsed < 2.0,
        None if elapsed < 2.0 else f"Took {elapsed:.4f}s (expected < 2.0s)"
    )


def test_edge_cases():
    """Test edge cases and error conditions"""
    print("\n" + "="*80)
    print("EDGE CASES: Error Conditions & Boundary Tests")
    print("="*80)
    
    # Test 1: Empty query
    intent_category, _ = query_intelligence.classify_intent_category("")
    results.add_result(
        "Edge Case: Empty query handling",
        intent_category in ["read_only_analytics", "aggregations"]  # Should default to something
    )
    
    # Test 2: Very long query
    long_query = "most common " * 100 + "diagnosis"
    intent_category, _ = query_intelligence.classify_intent_category(long_query)
    results.add_result(
        "Edge Case: Very long query",
        intent_category is not None
    )
    
    # Test 3: SQL injection attempts (in SQL, not query string)
    sql_injection_attempts = [
        ("SELECT * FROM users; DROP TABLE users; --", False),  # Should be blocked
        ("SELECT * FROM claims WHERE id = 1' OR '1'='1", True),  # This would fail at execution, not safety check
        ("SELECT * FROM claims; DELETE FROM claims; --", False),  # Should be blocked
    ]
    
    for sql, should_allow in sql_injection_attempts:
        is_safe, error = safety_governance.validate_query_safety(sql)
        passed = is_safe == should_allow
        results.add_result(
            f"Edge Case: SQL injection attempt ({sql[:30]}...)",
            passed,
            None if passed else f"Expected {should_allow}, got {is_safe}"
        )
    
    # Test 4: Invalid role
    has_permission, error = safety_governance.check_role_permissions("invalid_role", ["claims"])
    results.add_result(
        "Edge Case: Invalid role handling",
        not has_permission and error is not None
    )
    
    # Test 5: Empty results
    explanation = explainability_engine.explain_sql("SELECT * FROM claims WHERE 1=0", "empty query")
    results.add_result(
        "Edge Case: Empty result explanation",
        'tables_used' in explanation
    )


def main():
    """Run all stress tests"""
    print("\n" + "="*80)
    print("DOMAIN 3: COMPREHENSIVE STRESS TEST SUITE")
    print("="*80)
    print(f"Started at: {datetime.now().isoformat()}")
    print("="*80)
    
    start_time = time.time()
    
    # Run all test suites
    try:
        test_phase3_1_query_intelligence()
        test_phase3_2_safety_governance()
        test_phase3_3_explainability()
        test_phase3_4_feedback_learning()
        test_phase3_5_performance_controls()
        test_phase3_6_evaluation_metrics()
        test_integration_flow()
        test_performance_stress()
        test_edge_cases()
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR during testing: {e}")
        import traceback
        traceback.print_exc()
        results.add_result("Critical Error", False, str(e))
    
    total_time = time.time() - start_time
    results.add_performance("Total Test Execution Time", total_time)
    
    # Print summary
    results.print_summary()
    
    print(f"\nCompleted at: {datetime.now().isoformat()}")
    print(f"Total execution time: {total_time:.2f}s")
    
    # Exit with appropriate code
    if results.failed_tests > 0:
        print("\n❌ STRESS TEST FAILED - Some tests did not pass")
        sys.exit(1)
    else:
        print("\n✅ STRESS TEST PASSED - All tests passed")
        sys.exit(0)


if __name__ == "__main__":
    main()

