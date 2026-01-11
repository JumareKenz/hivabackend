"""
Real Query Test: "show disease with most patients"
Tests the complete Domain 3 pipeline with a real-world query
"""

import asyncio
import sys
import os
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.query_intelligence import query_intelligence
from app.services.safety_governance import safety_governance
from app.services.explainability_engine import explainability_engine
from app.services.performance_controls import performance_controls
from app.services.evaluation_metrics import evaluation_metrics
from app.services.domain_router import domain_router
from app.services.sql_validator import sql_validator
from app.services.sql_rewriter import sql_rewriter
from app.services.confidence_scorer import confidence_scorer
from app.services.result_sanitizer import result_sanitizer


async def test_query(query: str):
    """Test a query through the complete Domain 3 pipeline"""
    print("\n" + "="*80)
    print(f"TESTING QUERY: '{query}'")
    print("="*80)
    print(f"Started at: {datetime.now().isoformat()}\n")
    
    # Step 1: Domain 3.1 - Query Intelligence
    print("🔍 Step 1: Query Intelligence & Reasoning Control")
    print("-" * 80)
    intent_category, intent_confidence = query_intelligence.classify_intent_category(query)
    print(f"  Intent Category: {intent_category} (confidence: {intent_confidence:.2f})")
    
    is_supported, intent_rejection = query_intelligence.validate_intent_supported(intent_category)
    if not is_supported:
        print(f"  ❌ Query rejected: {intent_rejection}")
        return
    print(f"  ✅ Intent validated: {intent_category} is supported")
    
    # Schema-aware reasoning
    schema_info = {
        'tables': [
            {'table_name': 'claims', 'columns': []},
            {'table_name': 'diagnoses', 'columns': []},
            {'table_name': 'service_summaries', 'columns': []},
            {'table_name': 'service_summary_diagnosis', 'columns': []},
        ]
    }
    reasoning_plan = query_intelligence.enforce_step_constrained_reasoning(query, schema_info)
    print(f"  Required Tables: {reasoning_plan.get('required_tables', [])}")
    print(f"  Needs Aggregation: {reasoning_plan.get('needs_aggregation', False)}")
    print(f"  Filters: {reasoning_plan.get('filters', [])}")
    
    # Step 2: Domain 3.2 - Safety & Governance
    print("\n🔒 Step 2: Safety, Permissions & Data Governance")
    print("-" * 80)
    user_role = "analyst"  # Simulate analyst role
    required_tables = reasoning_plan.get('required_tables', [])
    
    has_permission, permission_error = safety_governance.check_role_permissions(user_role, required_tables)
    if not has_permission:
        print(f"  ❌ Permission denied: {permission_error}")
        return
    print(f"  ✅ Role '{user_role}' has permission to access: {required_tables}")
    
    # Step 3: Phase 4 - Domain Router
    print("\n🗺️  Step 3: Domain Router")
    print("-" * 80)
    domain, rejection_reason = domain_router.route(query)
    if domain == 'rejected':
        print(f"  ❌ Domain rejected: {rejection_reason}")
        return
    print(f"  ✅ Routed to domain: {domain}")
    
    # Step 4: Simulate SQL Generation (what Vanna would generate)
    print("\n💻 Step 4: SQL Generation (Simulated)")
    print("-" * 80)
    # This is what a well-trained system should generate
    generated_sql = """
    SELECT 
        d.name AS diagnosis,
        COUNT(DISTINCT c.id) AS total_claims
    FROM claims c
    JOIN service_summaries ss ON ss.claim_id = c.id
    JOIN service_summary_diagnosis ssd ON ssd.service_summary_id = ss.id
    JOIN diagnoses d ON d.id = ssd.diagnosis_id
    GROUP BY d.name
    ORDER BY total_claims DESC
    LIMIT 1
    """
    print(f"  Generated SQL:\n{generated_sql.strip()}")
    
    # Step 5: Domain 3.2 - Query Safety Validation
    print("\n🛡️  Step 5: Query Safety Validation")
    print("-" * 80)
    is_safe, safety_error = safety_governance.validate_query_safety(generated_sql)
    if not is_safe:
        print(f"  ❌ Query unsafe: {safety_error}")
        return
    print(f"  ✅ Query is safe (no dangerous operations)")
    
    # Check sensitive data access
    is_allowed, sensitive_error = safety_governance.check_sensitive_data_access(query, generated_sql)
    if not is_allowed:
        print(f"  ❌ Sensitive data access blocked: {sensitive_error}")
        return
    print(f"  ✅ No sensitive data access detected")
    
    # Step 6: Domain 3.5 - Performance Estimation
    print("\n⚡ Step 6: Performance & Cost Estimation")
    print("-" * 80)
    cost_estimate = performance_controls.estimate_query_cost(generated_sql)
    print(f"  Estimated Rows Scanned: {cost_estimate.get('estimated_rows_scanned', 0):,}")
    print(f"  Estimated Execution Time: {cost_estimate.get('estimated_execution_time_ms', 0):.2f}ms")
    print(f"  Complexity Score: {cost_estimate.get('complexity_score', 0)}")
    if cost_estimate.get('warning_message'):
        print(f"  ⚠️  Warning: {cost_estimate['warning_message']}")
    else:
        print(f"  ✅ No performance warnings")
    
    # Step 7: Phase 4 - SQL Validation
    print("\n✅ Step 7: SQL Validation (Phase 4)")
    print("-" * 80)
    is_valid, validation_error = sql_validator.validate(generated_sql, query, domain)
    if not is_valid:
        print(f"  ❌ Validation failed: {validation_error}")
        return
    print(f"  ✅ SQL validation passed")
    
    # Step 8: Phase 4 - SQL Rewriter
    print("\n🔧 Step 8: SQL Rewriter (Phase 4)")
    print("-" * 80)
    rewritten_sql, was_rewritten, rewrite_error = sql_rewriter.rewrite(generated_sql, query)
    if rewrite_error:
        print(f"  ❌ Rewrite error: {rewrite_error}")
        return
    if was_rewritten:
        print(f"  ✅ SQL was rewritten for best practices")
        print(f"  Rewritten SQL:\n{rewritten_sql.strip()}")
    else:
        print(f"  ✅ SQL did not need rewriting")
    
    # Step 9: Phase 4 - Confidence Scorer
    print("\n📊 Step 9: Confidence Scoring (Phase 4)")
    print("-" * 80)
    from app.services.intent_classifier import intent_classifier
    intent = intent_classifier.classify_intent(query)
    confidence_score, clarification_msg = confidence_scorer.score(generated_sql, query, intent, domain)
    print(f"  Intent: {intent}")
    print(f"  Confidence Score: {confidence_score:.2f}")
    if clarification_msg:
        print(f"  ⚠️  Clarification needed: {clarification_msg}")
    else:
        print(f"  ✅ High confidence, no clarification needed")
    
    # Step 10: Domain 3.3 - Explainability
    print("\n📖 Step 10: Explainability & Trust Layer")
    print("-" * 80)
    explanation = explainability_engine.explain_sql(generated_sql, query)
    print(f"  Tables Used: {explanation.get('tables_used', [])}")
    print(f"  Joins: {len(explanation.get('join_logic', []))} join(s)")
    print(f"  Filters: {len(explanation.get('filters_applied', []))} filter(s)")
    print(f"  Aggregations: {[agg.get('type') for agg in explanation.get('aggregations_computed', [])]}")
    
    user_justification = explainability_engine.generate_user_facing_justification(explanation)
    print(f"\n  User-Facing Justification:")
    print(f"  '{user_justification}'")
    
    # Step 11: Simulate Result Sanitization
    print("\n🧹 Step 11: Result Sanitization (Phase 4)")
    print("-" * 80)
    # Simulate query results
    mock_results = [
        {"diagnosis": "Malaria", "total_claims": 1243},
        {"diagnosis": "Diabetes", "total_claims": 892},
        {"diagnosis": "Hypertension", "total_claims": 756}
    ]
    sanitized_results = result_sanitizer.sanitize(mock_results, generated_sql)
    print(f"  Sanitized Results:")
    for i, row in enumerate(sanitized_results[:3], 1):
        print(f"    {i}. {row}")
    
    # Step 12: Domain 3.6 - Metrics Recording
    print("\n📈 Step 12: Evaluation & Metrics (Domain 3.6)")
    print("-" * 80)
    evaluation_metrics.record_query_metric('sql_validity', True)
    evaluation_metrics.record_query_metric('query_executed', True, {
        'domain': domain,
        'intent': intent,
        'row_count': len(sanitized_results),
        'query': query
    })
    print(f"  ✅ Metrics recorded")
    
    kpis = evaluation_metrics.calculate_kpis(days=7)
    print(f"  Current KPIs (last 7 days):")
    print(f"    SQL Validity Rate: {kpis.get('sql_validity_rate', 0):.2%}")
    print(f"    Total Queries: {kpis.get('total_queries', 0)}")
    
    # Summary
    print("\n" + "="*80)
    print("✅ QUERY TEST COMPLETE")
    print("="*80)
    print(f"Query: '{query}'")
    print(f"Domain: {domain}")
    print(f"Intent: {intent}")
    print(f"Confidence: {confidence_score:.2f}")
    print(f"Status: ✅ PASSED ALL CHECKS")
    print(f"Completed at: {datetime.now().isoformat()}")
    print("="*80)


async def main():
    """Run the test"""
    query = "show disease with most patients"
    await test_query(query)


if __name__ == "__main__":
    asyncio.run(main())



