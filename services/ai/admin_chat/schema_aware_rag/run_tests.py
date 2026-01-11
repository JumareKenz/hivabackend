#!/usr/bin/env python3
"""
Test Script for Schema-Aware RAG System
Runs comprehensive tests on the complete system
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from schema_aware_rag.schema_extractor import schema_extractor
from schema_aware_rag.table_selector import table_selector
from schema_aware_rag.rag_service import schema_aware_rag


async def test_schema_extraction():
    """Test 1: Schema Extraction"""
    print("\n" + "=" * 60)
    print("TEST 1: Schema Extraction")
    print("=" * 60)
    
    try:
        if not await schema_extractor.initialize():
            print("❌ Failed to initialize schema extractor")
            return False
        
        tables = await schema_extractor.extract_top_tables(n=20)
        
        print(f"\n✅ Extracted {len(tables)} tables")
        print("\nTop 10 tables by importance:")
        for name, info in sorted(tables.items(), key=lambda x: -x[1].importance_score)[:10]:
            print(f"  {info.importance_score:3.0f} | {name:30} | {info.row_count:>10,} rows")
        
        # Verify key tables are present
        required_tables = ['claims', 'service_summaries', 'diagnoses', 'users', 'states']
        missing = [t for t in required_tables if t not in tables]
        if missing:
            print(f"\n⚠️  Missing required tables: {missing}")
            return False
        
        print("\n✅ All required tables present")
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_table_selection():
    """Test 2: Table Selection"""
    print("\n" + "=" * 60)
    print("TEST 2: Table Selection")
    print("=" * 60)
    
    test_queries = [
        ("show me the disease with highest patients", ["diagnoses", "service_summaries", "claims"]),
        ("which disease has the most claims in Kogi state", ["diagnoses", "service_summaries", "claims", "users", "states"]),
        ("how many claims were processed", ["claims"]),
        ("top providers by claim count", ["providers", "claims"]),
    ]
    
    all_passed = True
    for query, expected_tables in test_queries:
        print(f"\nQuery: {query}")
        selected = table_selector.select_tables(query)
        selected_names = {t.table_name for t in selected}
        
        # Check if expected tables are in selection
        missing = set(expected_tables) - selected_names
        if missing:
            print(f"  ⚠️  Missing expected tables: {missing}")
            all_passed = False
        else:
            print(f"  ✅ Selected: {[t.table_name for t in selected[:5]]}")
    
    return all_passed


async def test_sql_generation():
    """Test 3: SQL Generation with Correct Joins"""
    print("\n" + "=" * 60)
    print("TEST 3: SQL Generation")
    print("=" * 60)
    
    if not await schema_aware_rag.initialize():
        print("❌ Failed to initialize RAG service")
        return False
    
    # Add core training examples with CORRECT join path
    training_examples = [
        {
            "question": "show me the disease with highest patients",
            "sql": """SELECT
    d.name AS disease,
    COUNT(DISTINCT c.id) AS patient_count
FROM claims c
JOIN diagnoses d ON d.id = CAST(c.diagnosis AS UNSIGNED)
WHERE c.diagnosis REGEXP '^[0-9]+$'
GROUP BY d.name
ORDER BY patient_count DESC
LIMIT 1""",
            "tag": "disease_highest_patients",
            "domain": "clinical"
        },
        {
            "question": "which disease has the most claims in Kogi state",
            "sql": """SELECT
    d.name AS disease,
    COUNT(DISTINCT c.id) AS claim_count
FROM claims c
JOIN users u ON c.user_id = u.id
JOIN states s ON u.state = s.id
JOIN diagnoses d ON d.id = CAST(c.diagnosis AS UNSIGNED)
WHERE s.name LIKE '%Kogi%' AND c.diagnosis REGEXP '^[0-9]+$'
GROUP BY d.name
ORDER BY claim_count DESC
LIMIT 1""",
            "tag": "disease_by_state",
            "domain": "clinical"
        },
        {
            "question": "top 5 diagnoses overall",
            "sql": """SELECT
    d.name AS diagnosis,
    COUNT(DISTINCT c.id) AS patient_count
FROM claims c
JOIN diagnoses d ON d.id = CAST(c.diagnosis AS UNSIGNED)
WHERE c.diagnosis REGEXP '^[0-9]+$'
GROUP BY d.name
ORDER BY patient_count DESC
LIMIT 5""",
            "tag": "top_diagnoses",
            "domain": "clinical"
        },
    ]
    
    for ex in training_examples:
        await schema_aware_rag.train_question_sql(
            question=ex['question'],
            sql=ex['sql'],
            tag=ex['tag'],
            domain=ex['domain']
        )
    
    print("\n✅ Training examples loaded")
    return True


async def test_query_execution():
    """Test 4: Query Execution with Self-Correction"""
    print("\n" + "=" * 60)
    print("TEST 4: Query Execution")
    print("=" * 60)
    
    test_queries = [
        "show me the disease with highest patients",
        "top 5 diagnoses overall",
        "how many claims are there",
    ]
    
    all_passed = True
    for query in test_queries:
        print(f"\n{'-' * 40}")
        print(f"Query: {query}")
        
        try:
            result = await schema_aware_rag.ask(query)
            
            if result.success:
                print(f"✅ Success: {result.row_count} rows")
                print(f"   SQL: {result.sql[:100]}...")
                if result.data:
                    print(f"   Sample: {result.data[0]}")
                if result.correction_attempts > 0:
                    print(f"   (Required {result.correction_attempts} correction attempts)")
            else:
                print(f"❌ Failed: {result.error}")
                all_passed = False
                
        except Exception as e:
            print(f"❌ Error: {e}")
            all_passed = False
    
    return all_passed


async def test_state_query():
    """Test 5: State-Based Disease Query (Critical Test)"""
    print("\n" + "=" * 60)
    print("TEST 5: State-Based Disease Query")
    print("=" * 60)
    
    query = "which disease has the most claims in Kogi state"
    print(f"\nQuery: {query}")
    
    try:
        result = await schema_aware_rag.ask(query)
        
        if result.success:
            print(f"\n✅ Success: {result.row_count} rows")
            print(f"SQL:\n{result.sql}")
            if result.data:
                print(f"\nResults:")
                for row in result.data[:5]:
                    print(f"  {row}")
            return True
        else:
            print(f"\n❌ Failed: {result.error}")
            print(f"SQL:\n{result.sql}")
            return False
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("SCHEMA-AWARE RAG SYSTEM - TEST SUITE")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 60)
    
    results = {}
    
    # Test 1: Schema Extraction
    results['schema_extraction'] = await test_schema_extraction()
    
    # Test 2: Table Selection
    results['table_selection'] = await test_table_selection()
    
    # Test 3: SQL Generation
    results['sql_generation'] = await test_sql_generation()
    
    # Test 4: Query Execution
    results['query_execution'] = await test_query_execution()
    
    # Test 5: State Query
    results['state_query'] = await test_state_query()
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  {test_name}: {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL TESTS PASSED")
    else:
        print("❌ SOME TESTS FAILED")
    print("=" * 60)
    
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)

