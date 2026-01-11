"""
Comprehensive Test Suite for Provider RAG System.

This test suite validates:
1. Zero hallucination guarantee
2. Correct refusal behavior
3. Grounding verification
4. Confidence scoring accuracy

Run with: python -m pytest app/providers_rag/tests/test_suite.py -v
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class TestCase:
    """A single test case."""
    
    name: str
    query: str
    category: str  # positive, negative, hallucination, grounding, edge_case
    expected_behavior: str  # "answer", "refuse", "clarify"
    expected_keywords: list[str] = None  # Keywords expected in response
    forbidden_keywords: list[str] = None  # Keywords that should NOT appear
    min_confidence: Optional[str] = None  # Minimum confidence level
    description: str = ""
    
    def __post_init__(self):
        self.expected_keywords = self.expected_keywords or []
        self.forbidden_keywords = self.forbidden_keywords or []


# ============================================
# TEST CASES
# ============================================

POSITIVE_TEST_CASES = [
    TestCase(
        name="portal_access_basic",
        query="I can't access the provider portal, what should I do?",
        category="positive",
        expected_behavior="answer",
        expected_keywords=["browser", "chrome", "firefox", "cache"],
        min_confidence="medium",
        description="Basic portal access question - should find direct match",
    ),
    TestCase(
        name="authorization_code_missing",
        query="My authorization code is not showing",
        category="positive",
        expected_behavior="answer",
        expected_keywords=["refresh", "ict", "screenshot"],
        min_confidence="medium",
        description="Auth code issue - common problem with clear answer",
    ),
    TestCase(
        name="login_password_issue",
        query="The portal keeps rejecting my password",
        category="positive",
        expected_behavior="answer",
        expected_keywords=["password", "email", "case-sensitive"],
        min_confidence="medium",
        description="Password/login issue - should find credential error answer",
    ),
    TestCase(
        name="enrollee_not_found",
        query="I can't find the enrollee in the system",
        category="positive",
        expected_behavior="answer",
        expected_keywords=["search", "id", "phone", "name"],
        min_confidence="low",
        description="Enrollee lookup - should provide search guidance",
    ),
    TestCase(
        name="claim_submit_button",
        query="Nothing happens when I click the submit button for my claim",
        category="positive",
        expected_behavior="answer",
        expected_keywords=["cache", "browser", "network"],
        min_confidence="medium",
        description="Claim submission issue - should provide troubleshooting",
    ),
    TestCase(
        name="authorization_code_used",
        query="The system says my authorization code has already been used",
        category="positive",
        expected_behavior="answer",
        expected_keywords=["draft", "manage claims", "ict"],
        min_confidence="medium",
        description="Code already used - specific procedure exists",
    ),
    TestCase(
        name="dependant_not_showing",
        query="I can only see the principal, the dependant is not showing",
        category="positive",
        expected_behavior="answer",
        expected_keywords=["dependant", "principal", "agency", "headquarters"],
        min_confidence="medium",
        description="Dependant visibility issue - has specific answer",
    ),
]

NEGATIVE_TEST_CASES = [
    TestCase(
        name="offtopic_weather",
        query="What's the weather like today?",
        category="negative",
        expected_behavior="refuse",
        forbidden_keywords=["sunny", "cloudy", "temperature", "rain"],
        description="Completely off-topic question - must refuse",
    ),
    TestCase(
        name="offtopic_general_health",
        query="What are the symptoms of malaria?",
        category="negative",
        expected_behavior="refuse",
        forbidden_keywords=["fever", "chills", "headache", "mosquito"],
        description="Medical question outside knowledge base - must refuse",
    ),
    TestCase(
        name="nonexistent_feature",
        query="How do I use the blockchain verification feature?",
        category="negative",
        expected_behavior="refuse",
        forbidden_keywords=["blockchain", "crypto", "verification"],
        description="Feature that doesn't exist - must refuse",
    ),
    TestCase(
        name="external_system",
        query="How do I configure the AWS integration?",
        category="negative",
        expected_behavior="refuse",
        forbidden_keywords=["aws", "amazon", "cloud", "s3"],
        description="External system not in KB - must refuse",
    ),
    TestCase(
        name="salary_information",
        query="What is the salary structure for healthcare workers?",
        category="negative",
        expected_behavior="refuse",
        forbidden_keywords=["salary", "pay", "compensation", "wage"],
        description="Information not in provider KB - must refuse",
    ),
    TestCase(
        name="internal_procedures",
        query="What is the internal approval workflow for new providers?",
        category="negative",
        expected_behavior="refuse",
        description="Internal procedure not documented - should refuse or provide limited info",
    ),
]

HALLUCINATION_TEST_CASES = [
    TestCase(
        name="leading_false_premise",
        query="I heard that providers can submit claims via WhatsApp, how does that work?",
        category="hallucination",
        expected_behavior="refuse",
        forbidden_keywords=["whatsapp", "message", "chat"],
        description="Leading question with false premise - must NOT confirm",
    ),
    TestCase(
        name="specific_number_fishing",
        query="What is the maximum claim amount that can be submitted in one transaction?",
        category="hallucination",
        expected_behavior="refuse",
        forbidden_keywords=["$", "₦", "naira", "amount", "maximum"],
        description="Fishing for specific number not in KB - must refuse",
    ),
    TestCase(
        name="fake_feature",
        query="Can you explain how the AI-powered automatic claim approval works?",
        category="hallucination",
        expected_behavior="refuse",
        forbidden_keywords=["ai", "automatic", "approval", "machine learning"],
        description="Fake feature question - must NOT invent details",
    ),
    TestCase(
        name="outdated_process",
        query="I remember there was a paper-based claim process, is that still available?",
        category="hallucination",
        expected_behavior="refuse",
        description="Asking about potentially outdated process - should not fabricate",
    ),
    TestCase(
        name="specific_timeline_fishing",
        query="How many days does it take for a claim to be processed?",
        category="hallucination",
        expected_behavior="refuse",
        forbidden_keywords=["days", "hours", "weeks", "business days"],
        description="Specific timeline not in KB - must not invent",
    ),
    TestCase(
        name="policy_detail_fishing",
        query="What percentage of the claim amount goes to administrative fees?",
        category="hallucination",
        expected_behavior="refuse",
        forbidden_keywords=["%", "percent", "fee", "administrative"],
        description="Specific policy detail not in KB - must refuse",
    ),
]

GROUNDING_TEST_CASES = [
    TestCase(
        name="grounding_portal_access",
        query="How do I troubleshoot portal access issues?",
        category="grounding",
        expected_behavior="answer",
        expected_keywords=["browser", "cache", "incognito"],
        description="Answer must be traceable to KB content",
    ),
    TestCase(
        name="grounding_auth_code",
        query="What should I do if my authorization code is blank?",
        category="grounding",
        expected_behavior="answer",
        expected_keywords=["refresh", "screenshot", "ict"],
        description="Answer must match KB content exactly",
    ),
    TestCase(
        name="grounding_enrollee_search",
        query="How can I search for an enrollee?",
        category="grounding",
        expected_behavior="answer",
        expected_keywords=["search", "id", "phone", "name"],
        description="Search methods must match KB",
    ),
]

EDGE_CASE_TEST_CASES = [
    TestCase(
        name="greeting_hi",
        query="Hi",
        category="edge_case",
        expected_behavior="answer",
        expected_keywords=["help", "assist"],
        description="Simple greeting - should respond helpfully",
    ),
    TestCase(
        name="greeting_hello",
        query="Hello there!",
        category="edge_case",
        expected_behavior="answer",
        expected_keywords=["help", "assist"],
        description="Greeting with exclamation - should respond",
    ),
    TestCase(
        name="thank_you",
        query="Thank you so much!",
        category="edge_case",
        expected_behavior="answer",
        expected_keywords=["welcome", "glad"],
        description="Expression of gratitude - should acknowledge",
    ),
    TestCase(
        name="empty_query",
        query="",
        category="edge_case",
        expected_behavior="clarify",
        description="Empty query - should ask for clarification",
    ),
    TestCase(
        name="very_short_ambiguous",
        query="it",
        category="edge_case",
        expected_behavior="clarify",
        description="Ambiguous single word - should ask for clarification",
    ),
    TestCase(
        name="special_characters",
        query="??? !!!! .....",
        category="edge_case",
        expected_behavior="clarify",
        description="Only special characters - should handle gracefully",
    ),
    TestCase(
        name="very_long_query",
        query="I am having issues with the portal and I cannot login and the system keeps showing errors and I have tried multiple browsers including Chrome and Firefox and Edge and even Safari but nothing works and I have cleared my cache and cookies multiple times and even tried using incognito mode but still having the same issues can you please help me understand what might be wrong and what steps I should take to resolve this issue?",
        category="edge_case",
        expected_behavior="answer",
        expected_keywords=["browser", "cache", "ict"],
        description="Very long query - should still work",
    ),
]


ALL_TEST_CASES = (
    POSITIVE_TEST_CASES +
    NEGATIVE_TEST_CASES +
    HALLUCINATION_TEST_CASES +
    GROUNDING_TEST_CASES +
    EDGE_CASE_TEST_CASES
)


@dataclass
class TestResult:
    """Result of a single test."""
    
    test_case: TestCase
    passed: bool
    actual_behavior: str
    confidence: str
    confidence_score: float
    response: str
    citations_count: int
    processing_time_ms: float
    failure_reason: Optional[str] = None


class ProviderRAGTestRunner:
    """
    Test runner for the Provider RAG system.
    
    Executes test cases and validates behavior against expectations.
    """
    
    def __init__(self):
        self.service = None
        self.results: list[TestResult] = []
    
    async def setup(self):
        """Initialize the service for testing."""
        from app.providers_rag.service import ProviderRAGService
        
        self.service = ProviderRAGService()
        await self.service.initialize()
        logger.info("Test service initialized")
    
    def _determine_actual_behavior(self, result) -> str:
        """Determine the actual behavior from a query result."""
        if result.is_refusal:
            return "refuse"
        if result.needs_clarification:
            return "clarify"
        return "answer"
    
    def _check_keywords(
        self,
        response: str,
        expected: list[str],
        forbidden: list[str]
    ) -> tuple[bool, str]:
        """Check keyword presence/absence in response."""
        response_lower = response.lower()
        
        # Check expected keywords (at least one should be present)
        if expected:
            found_expected = any(kw.lower() in response_lower for kw in expected)
            if not found_expected:
                return False, f"Missing expected keywords: {expected}"
        
        # Check forbidden keywords (none should be present)
        if forbidden:
            found_forbidden = [kw for kw in forbidden if kw.lower() in response_lower]
            if found_forbidden:
                return False, f"Found forbidden keywords: {found_forbidden}"
        
        return True, ""
    
    def _check_confidence(
        self,
        actual_confidence: str,
        min_confidence: Optional[str]
    ) -> bool:
        """Check if confidence meets minimum requirement."""
        if not min_confidence:
            return True
        
        confidence_order = ["none", "low", "medium", "high"]
        try:
            actual_idx = confidence_order.index(actual_confidence.lower())
            min_idx = confidence_order.index(min_confidence.lower())
            return actual_idx >= min_idx
        except ValueError:
            return True
    
    async def run_test(self, test_case: TestCase) -> TestResult:
        """Run a single test case."""
        logger.info(f"Running test: {test_case.name}")
        
        try:
            result = await self.service.query(test_case.query)
            
            actual_behavior = self._determine_actual_behavior(result)
            
            # Check behavior match
            behavior_match = actual_behavior == test_case.expected_behavior
            
            # Check keywords
            keyword_check, keyword_reason = self._check_keywords(
                result.answer,
                test_case.expected_keywords,
                test_case.forbidden_keywords,
            )
            
            # Check confidence
            confidence_check = self._check_confidence(
                result.confidence.value,
                test_case.min_confidence,
            )
            
            # Determine overall pass/fail
            passed = behavior_match and keyword_check and confidence_check
            
            failure_reason = None
            if not passed:
                reasons = []
                if not behavior_match:
                    reasons.append(
                        f"Behavior mismatch: expected '{test_case.expected_behavior}', "
                        f"got '{actual_behavior}'"
                    )
                if not keyword_check:
                    reasons.append(keyword_reason)
                if not confidence_check:
                    reasons.append(
                        f"Confidence too low: {result.confidence.value} < {test_case.min_confidence}"
                    )
                failure_reason = "; ".join(reasons)
            
            return TestResult(
                test_case=test_case,
                passed=passed,
                actual_behavior=actual_behavior,
                confidence=result.confidence.value,
                confidence_score=result.confidence_score,
                response=result.answer[:500],  # Truncate for display
                citations_count=len(result.citations),
                processing_time_ms=result.processing_time_ms,
                failure_reason=failure_reason,
            )
            
        except Exception as e:
            logger.error(f"Test {test_case.name} failed with exception: {e}")
            return TestResult(
                test_case=test_case,
                passed=False,
                actual_behavior="error",
                confidence="none",
                confidence_score=0.0,
                response=str(e),
                citations_count=0,
                processing_time_ms=0,
                failure_reason=f"Exception: {e}",
            )
    
    async def run_all_tests(self) -> dict[str, Any]:
        """Run all test cases and return summary."""
        await self.setup()
        
        self.results = []
        
        for test_case in ALL_TEST_CASES:
            result = await self.run_test(test_case)
            self.results.append(result)
            
            status = "✓ PASS" if result.passed else "✗ FAIL"
            logger.info(
                f"  {status} [{test_case.category}] {test_case.name} "
                f"(conf: {result.confidence}, time: {result.processing_time_ms:.0f}ms)"
            )
            
            if not result.passed:
                logger.warning(f"    Reason: {result.failure_reason}")
        
        return self.generate_report()
    
    def generate_report(self) -> dict[str, Any]:
        """Generate a test report."""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = total - passed
        
        # Group by category
        by_category = {}
        for result in self.results:
            cat = result.test_case.category
            if cat not in by_category:
                by_category[cat] = {"total": 0, "passed": 0, "failed": 0}
            by_category[cat]["total"] += 1
            if result.passed:
                by_category[cat]["passed"] += 1
            else:
                by_category[cat]["failed"] += 1
        
        # Collect failures
        failures = [
            {
                "name": r.test_case.name,
                "category": r.test_case.category,
                "query": r.test_case.query,
                "expected": r.test_case.expected_behavior,
                "actual": r.actual_behavior,
                "reason": r.failure_reason,
                "response_preview": r.response[:200],
            }
            for r in self.results if not r.passed
        ]
        
        # Calculate average processing time
        avg_time = sum(r.processing_time_ms for r in self.results) / total if total > 0 else 0
        
        report = {
            "summary": {
                "total_tests": total,
                "passed": passed,
                "failed": failed,
                "pass_rate": f"{(passed/total)*100:.1f}%" if total > 0 else "N/A",
                "average_processing_time_ms": round(avg_time, 2),
            },
            "by_category": by_category,
            "failures": failures,
            "zero_hallucination_check": {
                "hallucination_tests_passed": by_category.get("hallucination", {}).get("passed", 0),
                "hallucination_tests_total": by_category.get("hallucination", {}).get("total", 0),
                "compliant": by_category.get("hallucination", {}).get("failed", 0) == 0,
            },
        }
        
        return report


async def run_tests():
    """Main entry point for running tests."""
    runner = ProviderRAGTestRunner()
    report = await runner.run_all_tests()
    
    print("\n" + "=" * 60)
    print("PROVIDER RAG TEST REPORT")
    print("=" * 60)
    print(json.dumps(report, indent=2))
    print("=" * 60)
    
    # Exit with error code if tests failed
    if report["summary"]["failed"] > 0:
        print(f"\n❌ {report['summary']['failed']} TESTS FAILED")
        return 1
    else:
        print(f"\n✅ ALL {report['summary']['passed']} TESTS PASSED")
        return 0


if __name__ == "__main__":
    exit_code = asyncio.run(run_tests())
    exit(exit_code)
