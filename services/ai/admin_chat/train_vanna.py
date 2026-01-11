#!/usr/bin/env python3
"""
Train Vanna AI on database schema and example queries
"""

import asyncio
import argparse
from typing import Optional

# Import database and Vanna services
from app.services.database_service import database_service
from app.services.vanna_service import vanna_service


async def train_on_schema():
    """Train Vanna on database schema"""
    print("🔄 Initializing database connection...")
    await database_service.initialize()
    
    print("🔄 Initializing Vanna AI...")
    await vanna_service.initialize()
    
    print("✅ Schema training completed (or already up to date)")


async def train_on_examples():
    """Train Vanna on example question-SQL pairs"""
    print("🔄 Loading example queries...")
    
    # Phase 3: CORE TRAINING PAIRS (High-Precision Gold-Standard)
    # Domain 1: Clinical Claims & Diagnosis examples
    # Domain 2: Providers & Facilities Performance examples
    
    examples = [
        # ===== DOMAIN 1: Clinical Claims & Diagnosis =====
        # Phase 3: Example 1 — Most Common Diagnosis
        {
            "question": "which diagnosis has the most claims",
            "sql": """SELECT
    d.name AS diagnosis,
    COUNT(DISTINCT c.id) AS total_claims
FROM claims c
JOIN diagnoses d ON d.id = CAST(c.diagnosis AS UNSIGNED)
WHERE c.diagnosis REGEXP '^[0-9]+$'
GROUP BY d.name
ORDER BY total_claims DESC
LIMIT 1""",
            "tag": "phase3_core1_most_common"
        },
        # Phase 3: Example 2 — Diagnosis Trend (Monthly)
        {
            "question": "show monthly trends of diagnoses",
            "sql": """SELECT
    d.name AS diagnosis,
    DATE_FORMAT(c.created_at, '%Y-%m') AS month,
    COUNT(DISTINCT c.id) AS total_claims
FROM claims c
JOIN diagnoses d ON d.id = CAST(c.diagnosis AS UNSIGNED)
WHERE c.diagnosis REGEXP '^[0-9]+$'
GROUP BY d.name, month
ORDER BY month""",
            "tag": "phase3_core2_trend_monthly"
        },
        # Phase 3: Example 3 — Average Claim Cost per Diagnosis
        {
            "question": "what is the average claim cost per diagnosis",
            "sql": """SELECT
    d.name AS diagnosis,
    AVG(c.total_cost) AS avg_claim_cost
FROM claims c
JOIN diagnoses d ON d.id = CAST(c.diagnosis AS UNSIGNED)
WHERE c.diagnosis REGEXP '^[0-9]+$' AND c.total_cost IS NOT NULL
GROUP BY d.name
ORDER BY avg_claim_cost DESC""",
            "tag": "phase3_core3_avg_cost"
        },
        # Phase 3: Example 4 — Services Used Per Diagnosis
        {
            "question": "what services are most commonly used for each diagnosis",
            "sql": """SELECT
    d.name AS diagnosis,
    s.description AS service,
    COUNT(*) AS usage_count
FROM claims c
JOIN diagnoses d ON d.id = CAST(c.diagnosis AS UNSIGNED)
JOIN claims_services cs ON cs.claims_id = c.id
JOIN services s ON s.id = cs.services_id
WHERE c.diagnosis REGEXP '^[0-9]+$'
GROUP BY d.name, s.description
ORDER BY usage_count DESC""",
            "tag": "phase3_core4_services_per_diagnosis"
        },
        # Phase 3: Example 5 — Disease with Most Patients (CRITICAL - fixes "code 80471" issue)
        {
            "question": "show me the disease with highest number of patients",
            "sql": """SELECT
    d.name AS disease,
    COUNT(DISTINCT c.id) AS patient_count
FROM claims c
JOIN diagnoses d ON d.id = CAST(c.diagnosis AS UNSIGNED)
WHERE c.diagnosis REGEXP '^[0-9]+$'
GROUP BY d.name
ORDER BY patient_count DESC
LIMIT 1""",
            "tag": "phase3_core5_disease_most_patients"
        },
        # Phase 3: Example 5b — Disease with Most Patients in State (CRITICAL - state filtering)
        {
            "question": "show me which disease has the highest patients in Zamfara state",
            "sql": """SELECT
    d.name AS disease,
    COUNT(DISTINCT c.id) AS patient_count
FROM claims c
JOIN users u ON c.user_id = u.id
JOIN states s ON u.state = s.id
JOIN diagnoses d ON d.id = CAST(c.diagnosis AS UNSIGNED)
WHERE c.diagnosis REGEXP '^[0-9]+$' AND s.name LIKE '%Zamfara%'
GROUP BY d.name
ORDER BY patient_count DESC
LIMIT 1""",
            "tag": "phase3_core5b_disease_most_patients_state"
        },
        # Phase 3: Example 6 — Top Diagnoses Last Year
        {
            "question": "what were the top diagnoses last year",
            "sql": """SELECT
    d.name AS diagnosis,
    COUNT(DISTINCT c.id) AS total_claims
FROM claims c
JOIN diagnoses d ON d.id = CAST(c.diagnosis AS UNSIGNED)
WHERE c.diagnosis REGEXP '^[0-9]+$' AND YEAR(c.created_at) = YEAR(CURRENT_DATE) - 1
GROUP BY d.name
ORDER BY total_claims DESC""",
            "tag": "phase3_core5_top_last_year"
        },
        # ===== DOMAIN 2: Providers & Facilities Performance =====
        # Example 1 — Top Providers by Claims
        {
            "question": "which providers handled the most claims",
            "sql": """SELECT
    p.provider_id AS provider,
    COUNT(DISTINCT c.id) AS total_claims
FROM providers p
JOIN claims c ON c.provider_id = p.id
GROUP BY p.provider_id
ORDER BY total_claims DESC""",
            "tag": "domain2_provider_volume"
        },
        # Example 2 — Most Common Diagnosis per Provider
        {
            "question": "what are the most common diagnoses per provider",
            "sql": """SELECT
    p.provider_id AS provider,
    d.name AS diagnosis,
    COUNT(DISTINCT c.id) AS total_claims
FROM providers p
JOIN claims c ON c.provider_id = p.id
JOIN diagnoses d ON d.id = CAST(c.diagnosis AS UNSIGNED)
WHERE c.diagnosis REGEXP '^[0-9]+$'
GROUP BY p.provider_id, d.name
ORDER BY total_claims DESC""",
            "tag": "domain2_provider_diagnosis"
        },
        # Example 3 — Services Rendered by Providers
        {
            "question": "what services are most rendered by providers",
            "sql": """SELECT
    p.provider_id AS provider,
    s.description AS service,
    COUNT(*) AS usage_count
FROM providers p
JOIN claims c ON c.provider_id = p.id
JOIN claims_services cs ON cs.claims_id = c.id
JOIN services s ON s.id = cs.services_id
GROUP BY p.provider_id, s.description
ORDER BY usage_count DESC""",
            "tag": "domain2_provider_service"
        },
        # Example 4 — Provider Activity Trend
        {
            "question": "show monthly provider activity",
            "sql": """SELECT
    p.provider_id AS provider,
    DATE_FORMAT(c.created_at, '%Y-%m') AS month,
    COUNT(DISTINCT c.id) AS total_claims
FROM providers p
JOIN claims c ON c.provider_id = p.id
GROUP BY p.provider_id, month
ORDER BY month""",
            "tag": "domain2_provider_trend"
        },
    ]
    
    print(f"📚 Training on {len(examples)} Phase 3 core training pairs...")
    
    for i, example in enumerate(examples, 1):
        try:
            await vanna_service.train_on_example(
                question=example["question"],
                sql=example["sql"],
                tag=example.get("tag")
            )
            print(f"  ✅ [{i}/{len(examples)}] Trained: {example['question'][:50]}...")
        except Exception as e:
            print(f"  ⚠️  [{i}/{len(examples)}] Error: {e}")
    
    # Phase 3: Add negative training examples (what NOT to do)
    print("\n📚 Adding Phase 3 negative training examples...")
    negative_examples = [
        # Domain 1 negative examples
        {
            "question": "show diagnosis IDs with most cases",
            "sql": "SELECT diagnosis_id, COUNT(*) FROM service_summary_diagnosis GROUP BY diagnosis_id",
            "tag": "phase3_negative_diagnosis_id",
            "instruction": "NEVER return diagnosis IDs. Always resolve to diagnoses.name and aggregate by claims."
        },
        {
            "question": "show diagnosis codes",
            "sql": "SELECT diagnosis_code, COUNT(*) FROM diagnoses GROUP BY diagnosis_code",
            "tag": "phase3_negative_diagnosis_code",
            "instruction": "NEVER return diagnosis_code. Always use diagnoses.name for human-readable output."
        },
        {
            "question": "count service summaries",
            "sql": "SELECT COUNT(*) FROM service_summaries",
            "tag": "phase3_negative_count_service_summaries",
            "instruction": "NEVER count service_summaries directly. Always count DISTINCT claims.id."
        },
        # Domain 2 negative examples
        {
            "question": "show provider IDs and diagnosis IDs",
            "sql": "SELECT provider_id, diagnosis_id FROM claims",
            "tag": "domain2_negative_provider_diagnosis_id",
            "instruction": "NEVER output provider IDs or diagnosis IDs. Always resolve to provider_id (business label) and diagnosis name."
        },
        {
            "question": "show providers by id",
            "sql": "SELECT p.id, COUNT(*) FROM providers p GROUP BY p.id",
            "tag": "domain2_negative_provider_id",
            "instruction": "NEVER use providers.id. Always use providers.provider_id for human-readable output."
        }
    ]
    
    for i, neg_example in enumerate(negative_examples, 1):
        try:
            # Add as documentation with negative instruction
            instruction = f"❌ BAD EXAMPLE - DO NOT DO THIS:\nQuestion: {neg_example['question']}\nBad SQL: {neg_example['sql']}\n\n✅ CORRECT APPROACH:\n{neg_example['instruction']}"
            await vanna_service.train_on_documentation(instruction)
            print(f"  ✅ [{i}/{len(negative_examples)}] Negative example added: {neg_example['question'][:50]}...")
        except Exception as e:
            print(f"  ⚠️  [{i}/{len(negative_examples)}] Error: {e}")
    
    print("✅ Phase 3 training completed")


async def add_custom_example(question: str, sql: str, tag: Optional[str] = None):
    """Add a custom example query"""
    print(f"📚 Adding custom example...")
    print(f"  Question: {question}")
    print(f"  SQL: {sql[:100]}...")
    
    try:
        await vanna_service.train_on_example(
            question=question,
            sql=sql,
            tag=tag
        )
        print("✅ Custom example added successfully")
    except Exception as e:
        print(f"❌ Error adding example: {e}")


async def main():
    parser = argparse.ArgumentParser(description="Train Vanna AI on database schema and examples")
    parser.add_argument("--examples", action="store_true", help="Train on example queries")
    parser.add_argument("--add-example", nargs=2, metavar=("QUESTION", "SQL"), 
                       help="Add a custom example (provide question and SQL)")
    parser.add_argument("--tag", help="Tag for custom example")
    
    args = parser.parse_args()
    
    # Initialize database and Vanna
    await train_on_schema()
    
    if args.add_example:
        # Add custom example
        question, sql = args.add_example
        await add_custom_example(question, sql, args.tag)
    elif args.examples:
        # Train on examples
        await train_on_examples()
    else:
        print("ℹ️  Schema training completed. Use --examples to train on example queries.")
        print("ℹ️  Use --add-example 'QUESTION' 'SQL' to add custom examples.")
    
    # Close database connection
    await database_service.close()
    print("✅ Training complete!")


if __name__ == "__main__":
    asyncio.run(main())
