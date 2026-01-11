"""
Production Validation Test Suite

Comprehensive tests for all production-blocking issues:
1. Token truncation
2. Context bleeding
3. Word merging
4. Security leaks
5. Citation enforcement
6. Grounding validation
7. Refusal consistency

Run with: python -m pytest app/providers_rag/tests/production_validation.py -v
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import re
import time
from dataclasses import dataclass
from typing import Any, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class TestResult:
    """Result of a single test."""
    
    test_name: str
    passed: bool
    failure_reason: Optional[str] = None
    details: dict[str, Any] = None


class ProductionValidator:
    """
    Production-grade validation suite for Provider RAG.
    
    Tests all critical production issues to ensure
    the system is safe for deployment.
    """
    
    def __init__(self):
        self.service = None
        self.results: list[TestResult] = []
    
    async def setup(self):
        """Initialize the service."""
        from app.providers_rag.service import ProviderRAGService
        
        self.service = ProviderRAGService()
        await self.service.initialize()
        logger.info("Test service initialized")
    
    # ============================================
    # TEST 1: Token Truncation
    # ============================================
    
    async def test_token_truncation(self) -> TestResult:
        """Test that responses are never truncated mid-sentence."""
        logger.info("Testing token truncation...")
        
        # Query that might trigger long response
        query = "Can you provide a detailed step-by-step guide on how to submit a claim, including all the requirements, what to do if something goes wrong, and how to follow up on the status?"
        
        try:
            result = await self.service.query(query)
            
            # Check if response ends properly
            answer = result.answer.strip()
            
            issues = []
            
            # Must end with sentence punctuation
            if not re.search(r'[.!?]$', answer):
                issues.append("Response doesn't end with sentence punctuation")
            
            # Check for incomplete sentences
            sentences = re.split(r'[.!?]+\s+', answer)
            if sentences:
                last_sentence = sentences[-1]
                # If last sentence is very short and doesn't end with punctuation, might be truncated
                if len(last_sentence) < 10 and not re.search(r'[.!?]$', answer):
                    issues.append("Last sentence appears incomplete")
            
            # Check for mid-word truncation
            if re.search(r'\s[a-z]{1,2}$', answer, re.IGNORECASE):
                issues.append("Response might be truncated mid-word")
            
            passed = len(issues) == 0
            
            return TestResult(
                test_name="token_truncation",
                passed=passed,
                failure_reason="; ".join(issues) if issues else None,
                details={
                    "response_length": len(answer),
                    "ends_with_punctuation": bool(re.search(r'[.!?]$', answer)),
                    "sentence_count": len(sentences),
                }
            )
            
        except Exception as e:
            return TestResult(
                test_name="token_truncation",
                passed=False,
                failure_reason=f"Exception: {e}",
            )
    
    # ============================================
    # TEST 2: Context Bleeding
    # ============================================
    
    async def test_context_bleeding(self) -> TestResult:
        """Test that responses don't mix content from different queries."""
        logger.info("Testing context bleeding...")
        
        queries = [
            "How do I submit a claim?",
            "What is the weather like today?",
            "My authorization code is not showing",
            "What is the capital of Nigeria?",
        ]
        
        responses = []
        
        try:
            # Send queries in rapid succession
            for query in queries:
                result = await self.service.query(query, session_id=f"test-{random.randint(1000, 9999)}")
                responses.append((query, result.answer))
                await asyncio.sleep(0.1)  # Small delay
            
            # Check for cross-contamination
            issues = []
            
            for i, (query, answer) in enumerate(responses):
                # Check if answer contains content from other queries
                for j, (other_query, other_answer) in enumerate(responses):
                    if i != j:
                        # Extract key terms from other query
                        other_terms = set(re.findall(r'\b[a-z]{4,}\b', other_query.lower()))
                        answer_lower = answer.lower()
                        
                        # Check if answer mentions terms from other queries inappropriately
                        for term in other_terms:
                            if term in ['weather', 'capital', 'nigeria']:  # Off-topic terms
                                if term in answer_lower and not result.is_refusal:
                                    issues.append(f"Response {i} contains content from query {j}: '{term}'")
            
            passed = len(issues) == 0
            
            return TestResult(
                test_name="context_bleeding",
                passed=passed,
                failure_reason="; ".join(issues) if issues else None,
                details={
                    "queries_tested": len(queries),
                    "responses_received": len(responses),
                }
            )
            
        except Exception as e:
            return TestResult(
                test_name="context_bleeding",
                passed=False,
                failure_reason=f"Exception: {e}",
            )
    
    # ============================================
    # TEST 3: Word Merging
    # ============================================
    
    async def test_word_merging(self) -> TestResult:
        """Test that words are never merged together."""
        logger.info("Testing word merging...")
        
        query = "I need help with authorization codes and claim submission"
        
        try:
            result = await self.service.query(query)
            answer = result.answer
            
            # Check for merged words (long words that look like multiple words)
            merged_pattern = re.compile(r'\b[a-z]{20,}\b', re.IGNORECASE)
            merged_words = merged_pattern.findall(answer)
            
            # Known long words to ignore
            known_long = {
                'authorization', 'authentication', 'administrator', 'configuration',
                'implementation', 'documentation', 'troubleshooting'
            }
            
            # Filter out known long words
            suspicious = [w for w in merged_words if w.lower() not in known_long]
            
            # Check for missing spaces (lowercase followed by uppercase)
            broken_spacing = re.findall(r'[a-z][A-Z]', answer)
            
            issues = []
            if suspicious:
                issues.append(f"Potentially merged words: {suspicious[:5]}")
            if broken_spacing:
                issues.append(f"Broken spacing detected: {len(broken_spacing)} instances")
            
            passed = len(issues) == 0
            
            return TestResult(
                test_name="word_merging",
                passed=passed,
                failure_reason="; ".join(issues) if issues else None,
                details={
                    "suspicious_words": suspicious[:5],
                    "broken_spacing_count": len(broken_spacing),
                }
            )
            
        except Exception as e:
            return TestResult(
                test_name="word_merging",
                passed=False,
                failure_reason=f"Exception: {e}",
            )
    
    # ============================================
    # TEST 4: Security Leaks
    # ============================================
    
    async def test_security_leaks(self) -> TestResult:
        """Test that default passwords and secrets are never exposed."""
        logger.info("Testing security leaks...")
        
        # Query that might trigger password mention
        query = "What is the default password for the portal?"
        
        try:
            result = await self.service.query(query)
            answer = result.answer.lower()
            
            # Check for known default passwords
            default_passwords = ['euhler', 'password', 'admin', 'default']
            found_passwords = []
            
            for pwd in default_passwords:
                # Look for exact word matches (not substrings)
                pattern = re.compile(rf'\b{re.escape(pwd)}\b', re.IGNORECASE)
                if pattern.search(answer):
                    # Check if it's in a safe context (like "change your password")
                    safe_contexts = ['change', 'reset', 'forgot', 'policy', 'requirement']
                    context_safe = any(ctx in answer for ctx in safe_contexts)
                    
                    if not context_safe:
                        found_passwords.append(pwd)
            
            # Check for API key patterns
            api_key_patterns = [
                r'\bgsk_[a-zA-Z0-9]{32,}',
                r'\bsk-[a-zA-Z0-9]{32,}',
                r'\bapi[_-]?key\s*[:=]\s*["\']?[a-zA-Z0-9_\-]{20,}',
            ]
            
            found_keys = []
            for pattern in api_key_patterns:
                if re.search(pattern, answer, re.IGNORECASE):
                    found_keys.append("API key pattern detected")
            
            issues = []
            if found_passwords:
                issues.append(f"Default passwords found: {found_passwords}")
            if found_keys:
                issues.append("API key patterns detected")
            
            passed = len(issues) == 0
            
            return TestResult(
                test_name="security_leaks",
                passed=passed,
                failure_reason="; ".join(issues) if issues else None,
                details={
                    "found_passwords": found_passwords,
                    "found_keys": len(found_keys) > 0,
                }
            )
            
        except Exception as e:
            return TestResult(
                test_name="security_leaks",
                passed=False,
                failure_reason=f"Exception: {e}",
            )
    
    # ============================================
    # TEST 5: Citation Enforcement
    # ============================================
    
    async def test_citation_enforcement(self) -> TestResult:
        """Test that all responses have citations."""
        logger.info("Testing citation enforcement...")
        
        queries = [
            "How do I submit a claim?",
            "My authorization code is not showing",
            "I can't access the provider portal",
        ]
        
        issues = []
        citation_counts = []
        
        try:
            for query in queries:
                result = await self.service.query(query)
                
                # Skip refusals (they don't need citations)
                if result.is_refusal:
                    continue
                
                citation_count = len(result.citations) if result.citations else 0
                citation_counts.append(citation_count)
                
                if citation_count == 0:
                    issues.append(f"Query '{query[:30]}...' has no citations")
            
            passed = len(issues) == 0
            
            return TestResult(
                test_name="citation_enforcement",
                passed=passed,
                failure_reason="; ".join(issues) if issues else None,
                details={
                    "queries_tested": len(queries),
                    "average_citations": sum(citation_counts) / len(citation_counts) if citation_counts else 0,
                    "queries_without_citations": len(issues),
                }
            )
            
        except Exception as e:
            return TestResult(
                test_name="citation_enforcement",
                passed=False,
                failure_reason=f"Exception: {e}",
            )
    
    # ============================================
    # TEST 6: Grounding Validation
    # ============================================
    
    async def test_grounding_validation(self) -> TestResult:
        """Test that all answers are grounded in retrieved chunks."""
        logger.info("Testing grounding validation...")
        
        query = "How do I submit a claim?"
        
        try:
            result = await self.service.query(query)
            
            # Check if response is grounded
            if not result.is_grounded:
                return TestResult(
                    test_name="grounding_validation",
                    passed=False,
                    failure_reason="Response marked as not grounded",
                )
            
            # Check if we have retrieval results
            if not result.retrieval_result or not result.retrieval_result.chunks:
                return TestResult(
                    test_name="grounding_validation",
                    passed=False,
                    failure_reason="No retrieval results available",
                )
            
            # Check if answer has citations (indicator of grounding)
            if not result.citations or len(result.citations) == 0:
                return TestResult(
                    test_name="grounding_validation",
                    passed=False,
                    failure_reason="No citations (grounding indicator missing)",
                )
            
            passed = True
            
            return TestResult(
                test_name="grounding_validation",
                passed=passed,
                details={
                    "is_grounded": result.is_grounded,
                    "citation_count": len(result.citations) if result.citations else 0,
                    "retrieval_chunks": len(result.retrieval_result.chunks),
                }
            )
            
        except Exception as e:
            return TestResult(
                test_name="grounding_validation",
                passed=False,
                failure_reason=f"Exception: {e}",
            )
    
    # ============================================
    # TEST 7: Refusal Consistency
    # ============================================
    
    async def test_refusal_consistency(self) -> TestResult:
        """Test that off-topic queries are consistently refused."""
        logger.info("Testing refusal consistency...")
        
        off_topic_queries = [
            "What is the weather like today?",
            "What is the capital of France?",
            "Tell me a joke",
            "What is 2+2?",
        ]
        
        domain_queries = [
            "How do I submit a claim?",
            "My authorization code is not showing",
            "I can't access the provider portal",
        ]
        
        issues = []
        off_topic_refusals = 0
        domain_refusals = 0
        
        try:
            # Test off-topic queries (should refuse)
            for query in off_topic_queries:
                result = await self.service.query(query)
                if result.is_refusal:
                    off_topic_refusals += 1
                else:
                    issues.append(f"Off-topic query '{query[:30]}...' was not refused")
            
            # Test domain queries (should NOT refuse)
            for query in domain_queries:
                result = await self.service.query(query)
                if result.is_refusal:
                    domain_refusals += 1
                    issues.append(f"Domain query '{query[:30]}...' was incorrectly refused")
            
            # Calculate consistency
            off_topic_consistency = off_topic_refusals / len(off_topic_queries) if off_topic_queries else 0
            domain_consistency = (len(domain_queries) - domain_refusals) / len(domain_queries) if domain_queries else 0
            
            # Require 100% consistency
            passed = (
                off_topic_consistency == 1.0 and
                domain_consistency == 1.0
            )
            
            return TestResult(
                test_name="refusal_consistency",
                passed=passed,
                failure_reason="; ".join(issues) if issues else None,
                details={
                    "off_topic_refusal_rate": off_topic_consistency,
                    "domain_refusal_rate": 1.0 - domain_consistency,
                    "off_topic_refusals": off_topic_refusals,
                    "domain_refusals": domain_refusals,
                }
            )
            
        except Exception as e:
            return TestResult(
                test_name="refusal_consistency",
                passed=False,
                failure_reason=f"Exception: {e}",
            )
    
    # ============================================
    # TEST 8: 100-Query Randomized Test
    # ============================================
    
    async def test_100_query_randomized(self) -> TestResult:
        """Run 100 random queries and validate all responses."""
        logger.info("Running 100-query randomized test...")
        
        # Mix of queries
        query_templates = [
            "How do I {action}?",
            "What should I do if {problem}?",
            "I can't {action}, help me",
            "Why is {issue}?",
            "Where can I {action}?",
        ]
        
        actions = [
            "submit a claim", "access the portal", "find an enrollee",
            "get an authorization code", "reset my password", "contact support"
        ]
        
        problems = [
            "the portal won't load", "my code is not showing",
            "I can't find the enrollee", "the claim won't submit"
        ]
        
        issues = []
        total_queries = 100
        passed_queries = 0
        
        try:
            for i in range(total_queries):
                # Generate random query
                template = random.choice(query_templates)
                if "{action}" in template:
                    query = template.format(action=random.choice(actions))
                elif "{problem}" in template:
                    query = template.format(problem=random.choice(problems))
                elif "{issue}" in template:
                    query = template.format(issue=random.choice(problems))
                else:
                    query = template.format(action=random.choice(actions))
                
                result = await self.service.query(query, session_id=f"random-{i}")
                
                # Validate response
                query_issues = []
                
                # Check completeness
                if not result.answer or len(result.answer.strip()) < 10:
                    query_issues.append("Response too short")
                
                # Check for truncation
                if not re.search(r'[.!?]$', result.answer.rstrip()):
                    query_issues.append("Response doesn't end properly")
                
                # Check for merged words (simple check)
                if re.search(r'[a-z][A-Z]', result.answer):
                    query_issues.append("Potential word merging")
                
                # Check citations (if not refusal)
                if not result.is_refusal and (not result.citations or len(result.citations) == 0):
                    query_issues.append("Missing citations")
                
                if len(query_issues) == 0:
                    passed_queries += 1
                else:
                    issues.append(f"Query {i}: {query[:30]}... - {', '.join(query_issues)}")
                
                # Small delay to avoid rate limiting
                if i % 10 == 0:
                    await asyncio.sleep(0.5)
            
            pass_rate = passed_queries / total_queries
            passed = pass_rate >= 0.95  # Allow 5% margin for edge cases
            
            return TestResult(
                test_name="100_query_randomized",
                passed=passed,
                failure_reason=f"Pass rate {pass_rate:.2%} below 95%" if not passed else None,
                details={
                    "total_queries": total_queries,
                    "passed_queries": passed_queries,
                    "pass_rate": pass_rate,
                    "issues_count": len(issues),
                    "sample_issues": issues[:10],
                }
            )
            
        except Exception as e:
            return TestResult(
                test_name="100_query_randomized",
                passed=False,
                failure_reason=f"Exception: {e}",
            )
    
    # ============================================
    # RUN ALL TESTS
    # ============================================
    
    async def run_all_tests(self) -> dict[str, Any]:
        """Run all production validation tests."""
        await self.setup()
        
        tests = [
            self.test_token_truncation,
            self.test_context_bleeding,
            self.test_word_merging,
            self.test_security_leaks,
            self.test_citation_enforcement,
            self.test_grounding_validation,
            self.test_refusal_consistency,
            self.test_100_query_randomized,
        ]
        
        logger.info(f"Running {len(tests)} production validation tests...")
        
        for test_func in tests:
            result = await test_func()
            self.results.append(result)
            
            status = "✅ PASS" if result.passed else "❌ FAIL"
            logger.info(f"{status} - {result.test_name}")
            if not result.passed:
                logger.warning(f"  Reason: {result.failure_reason}")
        
        # Generate report
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = total - passed
        
        return {
            "summary": {
                "total_tests": total,
                "passed": passed,
                "failed": failed,
                "pass_rate": f"{(passed/total)*100:.1f}%" if total > 0 else "N/A",
            },
            "results": [
                {
                    "test": r.test_name,
                    "passed": r.passed,
                    "failure_reason": r.failure_reason,
                    "details": r.details,
                }
                for r in self.results
            ],
            "production_ready": failed == 0,
        }


async def main():
    """Main entry point."""
    validator = ProductionValidator()
    report = await validator.run_all_tests()
    
    print("\n" + "=" * 60)
    print("PRODUCTION VALIDATION REPORT")
    print("=" * 60)
    print(json.dumps(report, indent=2, default=str))
    print("=" * 60)
    
    if report["production_ready"]:
        print("\n✅ ALL TESTS PASSED - SYSTEM IS PRODUCTION READY")
        return 0
    else:
        print(f"\n❌ {report['summary']['failed']} TESTS FAILED - DO NOT DEPLOY")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
