"""
Migration Validation Scripts
Validates data integrity, functional correctness, and performance after migration
"""
import asyncio
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
import sys
from pathlib import Path

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.database_service import database_service
from app.services.sql_generator import sql_generator
from app.services.conversation_manager import conversation_manager


class MigrationValidator:
    """Validates migration integrity and correctness"""
    
    def __init__(self):
        self.validation_results = {
            "schema": {},
            "data": {},
            "functional": {},
            "performance": {},
            "semantic": {}
        }
        self.errors = []
        self.warnings = []
    
    async def validate_all(self) -> Dict[str, Any]:
        """Run all validation checks"""
        print("🔍 Starting migration validation...")
        
        # Initialize database
        await database_service.initialize()
        
        # Run validations
        await self.validate_schema()
        await self.validate_data_integrity()
        await self.validate_functional_correctness()
        await self.validate_performance()
        await self.validate_semantic_consistency()
        
        # Generate report
        report = self._generate_report()
        return report
    
    async def validate_schema(self):
        """Validate schema migration integrity"""
        print("  ✓ Validating schema...")
        
        try:
            schema_info = await database_service.get_schema_info()
            
            if not schema_info or "tables" not in schema_info:
                self.errors.append("Schema information is empty or invalid")
                return
            
            tables = schema_info.get("tables", [])
            
            # Validate table count
            if len(tables) == 0:
                self.errors.append("No tables found in schema")
            else:
                self.validation_results["schema"]["table_count"] = len(tables)
                print(f"    Found {len(tables)} tables")
            
            # Validate key tables exist
            key_tables = ["claims", "users", "providers", "states"]
            found_tables = {t.get("table_name") for t in tables}
            
            for table in key_tables:
                if table not in found_tables:
                    self.warnings.append(f"Key table '{table}' not found in schema")
                else:
                    # Validate table structure
                    table_info = next(t for t in tables if t.get("table_name") == table)
                    columns = table_info.get("columns", [])
                    if len(columns) == 0:
                        self.errors.append(f"Table '{table}' has no columns")
                    else:
                        self.validation_results["schema"][f"{table}_columns"] = len(columns)
            
            # Validate column data types
            for table in tables:
                table_name = table.get("table_name")
                columns = table.get("columns", [])
                
                for col in columns:
                    if not col.get("data_type"):
                        self.warnings.append(
                            f"Column '{col.get('column_name')}' in table '{table_name}' has no data type"
                        )
            
            self.validation_results["schema"]["status"] = "passed" if not self.errors else "failed"
            
        except Exception as e:
            self.errors.append(f"Schema validation error: {str(e)}")
            self.validation_results["schema"]["status"] = "error"
    
    async def validate_data_integrity(self):
        """Validate data migration integrity"""
        print("  ✓ Validating data integrity...")
        
        try:
            # Sample-based validation for key tables
            test_tables = ["claims", "users", "providers"]
            
            for table in test_tables:
                try:
                    # Get row count
                    count_query = f"SELECT COUNT(*) as count FROM {table}"
                    result = await database_service.execute_query(count_query)
                    
                    if result and len(result) > 0:
                        row_count = result[0].get("count", 0)
                        self.validation_results["data"][f"{table}_row_count"] = row_count
                        print(f"    {table}: {row_count} rows")
                        
                        if row_count == 0:
                            self.warnings.append(f"Table '{table}' is empty")
                        
                        # Sample a few rows to validate structure
                        if row_count > 0:
                            sample_query = f"SELECT * FROM {table} LIMIT 5"
                            sample = await database_service.execute_query(sample_query)
                            
                            if sample and len(sample) > 0:
                                # Validate row structure
                                expected_keys = set(sample[0].keys())
                                for row in sample:
                                    if set(row.keys()) != expected_keys:
                                        self.errors.append(
                                            f"Inconsistent row structure in table '{table}'"
                                        )
                                        break
                    else:
                        self.warnings.append(f"Could not get row count for table '{table}'")
                
                except Exception as e:
                    self.warnings.append(f"Error validating table '{table}': {str(e)}")
            
            self.validation_results["data"]["status"] = "passed" if not self.errors else "failed"
            
        except Exception as e:
            self.errors.append(f"Data integrity validation error: {str(e)}")
            self.validation_results["data"]["status"] = "error"
    
    async def validate_functional_correctness(self):
        """Validate functional correctness of queries"""
        print("  ✓ Validating functional correctness...")
        
        test_queries = [
            {
                "query": "Show me total number of claims",
                "expected_sql_keywords": ["SELECT", "COUNT", "claims"],
                "min_confidence": 0.8
            },
            {
                "query": "Claims by status",
                "expected_sql_keywords": ["SELECT", "GROUP BY", "status"],
                "min_confidence": 0.8
            },
            {
                "query": "Top 10 providers by claim volume",
                "expected_sql_keywords": ["SELECT", "LIMIT", "10"],
                "min_confidence": 0.7
            }
        ]
        
        passed = 0
        failed = 0
        
        for test in test_queries:
            try:
                query = test["query"]
                result = await sql_generator.generate_sql(
                    natural_language_query=query,
                    conversation_history=None
                )
                
                sql = result.get("sql", "").upper()
                confidence = result.get("confidence", 0)
                
                # Check SQL contains expected keywords
                expected_keywords = test["expected_sql_keywords"]
                keywords_found = all(keyword.upper() in sql for keyword in expected_keywords)
                
                # Check confidence
                confidence_ok = confidence >= test["min_confidence"]
                
                if keywords_found and confidence_ok:
                    passed += 1
                    print(f"    ✓ '{query}' - SQL generated successfully")
                else:
                    failed += 1
                    issues = []
                    if not keywords_found:
                        issues.append("missing expected keywords")
                    if not confidence_ok:
                        issues.append(f"low confidence ({confidence:.2f})")
                    
                    self.warnings.append(
                        f"Query '{query}' validation issues: {', '.join(issues)}"
                    )
                    print(f"    ⚠ '{query}' - {', '.join(issues)}")
                
                # Try to execute the SQL
                try:
                    execution_result = await database_service.execute_query(result["sql"])
                    if execution_result is None:
                        self.errors.append(f"Query '{query}' execution returned None")
                    else:
                        print(f"      Executed successfully, returned {len(execution_result)} rows")
                except Exception as e:
                    self.errors.append(f"Query '{query}' execution failed: {str(e)}")
            
            except Exception as e:
                failed += 1
                self.errors.append(f"Query '{query}' generation failed: {str(e)}")
                print(f"    ✗ '{query}' - Generation failed: {str(e)}")
        
        self.validation_results["functional"] = {
            "status": "passed" if failed == 0 else "failed",
            "passed": passed,
            "failed": failed,
            "total": len(test_queries)
        }
    
    async def validate_performance(self):
        """Validate performance meets requirements"""
        print("  ✓ Validating performance...")
        
        import time
        
        test_query = "Show me total number of claims"
        
        try:
            # Measure SQL generation time
            start = time.time()
            sql_result = await sql_generator.generate_sql(
                natural_language_query=test_query,
                conversation_history=None
            )
            generation_time = time.time() - start
            
            # Measure query execution time
            start = time.time()
            execution_result = await database_service.execute_query(sql_result["sql"])
            execution_time = time.time() - start
            
            self.validation_results["performance"] = {
                "status": "passed",
                "sql_generation_time": generation_time,
                "query_execution_time": execution_time,
                "total_time": generation_time + execution_time
            }
            
            print(f"    SQL generation: {generation_time:.2f}s")
            print(f"    Query execution: {execution_time:.2f}s")
            print(f"    Total: {generation_time + execution_time:.2f}s")
            
            # Performance thresholds (adjust as needed)
            if generation_time > 10:
                self.warnings.append(f"SQL generation time ({generation_time:.2f}s) exceeds threshold")
            if execution_time > 5:
                self.warnings.append(f"Query execution time ({execution_time:.2f}s) exceeds threshold")
        
        except Exception as e:
            self.errors.append(f"Performance validation error: {str(e)}")
            self.validation_results["performance"]["status"] = "error"
    
    async def validate_semantic_consistency(self):
        """Validate semantic consistency of query variations"""
        print("  ✓ Validating semantic consistency...")
        
        query_variations = [
            [
                "total number of claims",
                "count of claims",
                "how many claims",
                "show me total number of claims"
            ]
        ]
        
        passed = 0
        failed = 0
        
        for variations in query_variations:
            results = []
            
            for query in variations:
                try:
                    result = await sql_generator.generate_sql(
                        natural_language_query=query,
                        conversation_history=None
                    )
                    results.append({
                        "query": query,
                        "sql": result["sql"],
                        "confidence": result["confidence"]
                    })
                except Exception as e:
                    self.warnings.append(f"Failed to generate SQL for '{query}': {str(e)}")
                    failed += 1
                    continue
            
            # Check if all variations produce similar SQL (same table, similar structure)
            if len(results) >= 2:
                first_sql = results[0]["sql"].upper()
                all_similar = all(
                    "CLAIMS" in r["sql"].upper() and "COUNT" in r["sql"].upper()
                    for r in results
                )
                
                if all_similar:
                    passed += len(results)
                    print(f"    ✓ Variations produce consistent SQL")
                else:
                    failed += len(results)
                    self.warnings.append(
                        f"Query variations produce inconsistent SQL structures"
                    )
                    print(f"    ⚠ Variations produce inconsistent SQL")
        
        self.validation_results["semantic"] = {
            "status": "passed" if failed == 0 else "failed",
            "passed": passed,
            "failed": failed
        }
    
    def _generate_report(self) -> Dict[str, Any]:
        """Generate validation report"""
        total_errors = len(self.errors)
        total_warnings = len(self.warnings)
        
        overall_status = "passed" if total_errors == 0 else "failed"
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": overall_status,
            "summary": {
                "total_errors": total_errors,
                "total_warnings": total_warnings,
                "validation_results": self.validation_results
            },
            "errors": self.errors,
            "warnings": self.warnings,
            "recommendations": self._generate_recommendations()
        }
        
        return report
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on validation results"""
        recommendations = []
        
        if len(self.errors) > 0:
            recommendations.append(
                f"❌ {len(self.errors)} errors found. Review and fix before proceeding with migration."
            )
        
        if len(self.warnings) > 0:
            recommendations.append(
                f"⚠️  {len(self.warnings)} warnings found. Review and address as needed."
            )
        
        if len(self.errors) == 0 and len(self.warnings) == 0:
            recommendations.append(
                "✅ All validations passed. Migration can proceed."
            )
        
        return recommendations


async def main():
    """Main validation entry point"""
    validator = MigrationValidator()
    report = await validator.validate_all()
    
    # Print report
    print("\n" + "="*60)
    print("VALIDATION REPORT")
    print("="*60)
    print(f"Overall Status: {report['overall_status'].upper()}")
    print(f"Errors: {report['summary']['total_errors']}")
    print(f"Warnings: {report['summary']['total_warnings']}")
    print("\nRecommendations:")
    for rec in report['recommendations']:
        print(f"  {rec}")
    
    if report['errors']:
        print("\nErrors:")
        for error in report['errors']:
            print(f"  ❌ {error}")
    
    if report['warnings']:
        print("\nWarnings:")
        for warning in report['warnings']:
            print(f"  ⚠️  {warning}")
    
    # Save report to file
    report_file = Path(__file__).parent / "validation_report.json"
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2, default=str)
    
    print(f"\n📄 Full report saved to: {report_file}")
    
    # Exit with error code if validation failed
    if report['overall_status'] == "failed":
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())


