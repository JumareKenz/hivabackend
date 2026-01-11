"""
Clinical Safety Guardrails for PPH RAG System

This module implements comprehensive safety checks to prevent:
- Hallucinations and speculation
- Unsafe dosage recommendations
- Patient-specific advice
- Out-of-scope clinical guidance
- Conflicting guidance without disclosure
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class SafetyViolationType(Enum):
    """Types of safety violations"""
    HALLUCINATION = "hallucination"
    UNSAFE_DOSAGE = "unsafe_dosage"
    PATIENT_SPECIFIC = "patient_specific"
    OUT_OF_SCOPE = "out_of_scope"
    SPECULATION = "speculation"
    CONFLICTING_GUIDANCE = "conflicting_guidance"
    MISSING_EVIDENCE = "missing_evidence"


@dataclass
class SafetyCheck:
    """Result of a safety check"""
    passed: bool
    violation_type: Optional[SafetyViolationType]
    message: str
    severity: str  # 'critical', 'high', 'medium', 'low'
    recommended_action: str


class ClinicalSafetyGuardrails:
    """
    Comprehensive safety guardrails for clinical responses
    """
    
    # Patterns that indicate dosage/intervention recommendations
    DOSAGE_PATTERNS = [
        r'\b\d+\s*(?:mg|g|ml|units?|iu)\b',
        r'\b(?:give|administer|prescribe|dose)\s+\d+',
        r'\badminister\s+(?:\w+\s+){0,3}\d+',
    ]
    
    # Phase 1: Emergency query classification keywords
    EMERGENCY_PROTOCOL_KEYWORDS = [
        'protocol', 'procedure', 'procedures', 'steps', 'algorithm', 
        'guideline', 'guidelines', 'management', 'approach'
    ]
    
    EMERGENCY_INFORMATIONAL_KEYWORDS = [
        'what is', 'what are', 'define', 'explain', 'describe', 
        'definition', 'signs', 'symptoms', 'features'
    ]
    
    EMERGENCY_TRIGGER_KEYWORDS = [
        'emergency', 'urgent', 'urgently', 'immediate', 'immediately', 
        'critical', 'critically', 'now', 'right now', 'asap'
    ]
    
    # Patterns that indicate patient-specific advice
    # CRITICAL: These are checked FIRST before any other classification
    PATIENT_SPECIFIC_PATTERNS = [
        # Original patterns
        r'\byou\s+should\s+(?:take|receive|get)',
        r'\bin\s+your\s+case',
        r'\bfor\s+you(?:r)?\s+(?:specifically|particularly)',
        r'\byour\s+(?:dose|treatment|medication)',
        r'\bI\s+(?:recommend|suggest|advise)\s+you',
        
        # Phase 1 additions: First-person prescriptive
        r'\bI\s+should\s+(?:give|administer|prescribe|recommend)',
        r'\bshould\s+I\s+(?:give|administer|prescribe)',
        r'\b(?:exact|specific)\s+dose',  # Any exact/specific dose query is suspicious
        r'\bdose.*I\s+should',  # dose + I should combination
        r'\bdose.*(?:for\s+my|for\s+our|for\s+this)\s+patient',
        r'\b(?:what|which|how\s+much).*(?:dosage|dose).*(?:for\s+my|for\s+our)\s+patient',
        r'\b(?:dosage|dose)\s+(?:for|of).*my\s+patient',  # dosage for my patient
        
        # Specific patient details with numbers
        r'\ba\s+patient\s+(?:weighs?|is|has)\s+\d+',
        r'\bpatient\s+weighing\s+\d+',
        r'\bpatient.*\d+\s*(?:kg|lb|weeks?|years?)',
        
        # Possessive with pronoun (indicates active patient case)
        r'\bmy\s+patient\b.*\b(?:her|his|their)\b',
        r'\bour\s+patient\b.*\b(?:her|his|their)\b',
        r'\bthis\s+patient\b.*\b(?:her|his|their)\b',
        
        # Calculation requests
        r'\bcalculate\s+(?:dose|dosage|amount)\s+for',
        r'\bdose\s+for\s+(?:this|my|our|a)\s+patient',
        r'\b(?:what|how\s+much)\s+(?:dose|dosage).*patient',
        
        # Active case management
        r'\bpatient\s+(?:is|has)\s+(?:currently|now|right\s+now)',
        r'\btreat\s+(?:this|my|our)\s+patient',
        r'\b(?:my|our|this)\s+patient.*(?:what\s+should|what\s+do)',  # Specific patient only
        
        # Case review requests
        r'\breview\s+(?:this|my|our|a)\s+patient',
        r'\bpatient.*(?:BP|blood\s+pressure|bleeding).*\d+',
        r'\bcase.*BP.*bleeding',
        
        # Queries about new/future guidelines (non-existent)
        r'\bnew\s+202[5-9]\s+guideline',  # Future years 2025-2029
        r'\b202[5-9]\s+(?:guideline|recommendation|protocol)',
        r'\bupcoming\s+guideline',
        r'\blatest\s+202[5-9]',
    ]
    
    # Speculation indicators
    SPECULATION_PATTERNS = [
        r'\b(?:probably|possibly|might|maybe|perhaps|could be|may be)\b',
        r'\b(?:typically|usually|generally|often)\s+(?:patients?|women)\b',
        r'\bI\s+think\b',
        r'\bI\s+believe\b',
        r'\bin\s+my\s+(?:opinion|experience)\b',
    ]
    
    # Out-of-scope indicators
    OUT_OF_SCOPE_PATTERNS = [
        r'\b(?:cancer|diabetes|hypertension|HIV|tuberculosis)\b',  # Non-PPH conditions
        r'\b(?:pregnancy\s+test|ultrasound|MRI|CT\s+scan)\b',  # Diagnostic procedures beyond PPH
        r'\b(?:chemotherapy|radiotherapy)\b',  # Treatments beyond PPH scope
    ]
    
    # Phase 1: Negative indicators that exclude PPH scope even with "postpartum" keyword
    OUT_OF_SCOPE_NEGATIVE_INDICATORS = [
        r'\b(?:antibiotic|antibiotics)\b(?!.*(?:pph|hemorrhage|haemorrhage))',
        r'\binfection\b(?!.*(?:pph|hemorrhage|haemorrhage))',  # Infection without PPH context
        r'\b(?:fever|sepsis)\b(?!.*(?:pph|hemorrhage|haemorrhage))',
        r'\bpostpartum\s+(?:depression|psychosis|blues)',  # Mental health, not PPH
        r'\bbreastfeeding\b(?!.*(?:pph|hemorrhage|haemorrhage))',  # Unless PPH-related
    ]
    
    # Safe refusal templates
    SAFE_REFUSAL_TEMPLATES = {
        SafetyViolationType.MISSING_EVIDENCE: (
            "This information is not explicitly stated in the available PPH clinical "
            "guidelines in this knowledge base. For specific medical guidance, please "
            "consult with a healthcare professional."
        ),
        SafetyViolationType.UNSAFE_DOSAGE: (
            "I cannot provide specific dosage recommendations. Medication dosages must "
            "be determined by a qualified healthcare provider based on individual patient "
            "assessment. Please refer to the clinical guidelines or consult a healthcare professional."
        ),
        SafetyViolationType.PATIENT_SPECIFIC: (
            "I cannot provide patient-specific medical advice. Clinical decisions must be "
            "made by qualified healthcare providers based on individual patient assessment. "
            "Please consult with a healthcare professional for personalized guidance."
        ),
        SafetyViolationType.OUT_OF_SCOPE: (
            "This question appears to be outside the scope of postpartum hemorrhage management. "
            "This knowledge base contains information specifically about PPH prevention, diagnosis, "
            "and management. For other medical conditions, please consult appropriate resources."
        ),
    }
    
    def __init__(self):
        """Initialize safety guardrails"""
        self.violation_log: List[Dict[str, Any]] = []
    
    def classify_emergency_query(self, query: str) -> str:
        """
        Classify emergency query type (Phase 1 addition)
        
        CRITICAL: Distinguish between:
        - General emergency protocol queries (SAFE if documented)
        - Active patient emergencies (UNSAFE - always refuse)
        
        Returns:
            'protocol' - Safe to answer if documented (general procedure request)
            'informational' - Safe to answer if documented (general information)
            'patient_emergency' - ALWAYS REFUSE (active patient case)
            'none' - Not an emergency query
        """
        query_lower = query.lower()
        
        # Check if this is an emergency-related query
        is_emergency = any(kw in query_lower for kw in self.EMERGENCY_TRIGGER_KEYWORDS)
        
        if not is_emergency:
            return 'none'
        
        # PRIORITY 1: Check for EXPLICIT protocol request FIRST
        # If user explicitly asks for "the protocol" or "the procedure", that's safe
        # even if they mention "my patient"
        explicit_protocol_requests = [
            r'give\s+me\s+(?:the\s+)?(?:protocol|procedure|steps|algorithm)',
            r'what\s+is\s+the\s+(?:protocol|procedure|steps|algorithm)',
            r'tell\s+me\s+the\s+(?:protocol|procedure|steps|algorithm)',
            r'show\s+me\s+the\s+(?:protocol|procedure|steps|algorithm)',
        ]
        
        for pattern in explicit_protocol_requests:
            if re.search(pattern, query_lower):
                return 'protocol'  # Explicit protocol request - safe
        
        # PRIORITY 2: Check for SPECIFIC patient case (UNSAFE)
        specific_patient_indicators = [
            r'\bmy\s+patient',
            r'\bour\s+patient',
            r'\bthis\s+patient',
            r'\bpatient.*\d+.*(?:kg|weeks?|ml|BP)',  # Patient with specific details
        ]
        
        for pattern in specific_patient_indicators:
            if re.search(pattern, query_lower):
                return 'patient_emergency'  # Specific case - refuse
        
        # PRIORITY 3: Check for general protocol request (safe if documented)
        # Keywords like "protocol", "procedure", "steps", "algorithm"
        if any(kw in query_lower for kw in self.EMERGENCY_PROTOCOL_KEYWORDS):
            return 'protocol'
        
        # PRIORITY 3: Check for informational request (safe if documented)
        # Keywords like "what is", "define", "explain"
        if any(kw in query_lower for kw in self.EMERGENCY_INFORMATIONAL_KEYWORDS):
            return 'informational'
        
        # Check general patient-specific patterns
        for pattern in self.PATIENT_SPECIFIC_PATTERNS:
            if re.search(pattern, query_lower):
                return 'patient_emergency'
        
        # Emergency query with "what do I do" - could be general protocol request
        # Allow if phrased generally (e.g., "Patient bleeding, what do I do?")
        # This is asking for general emergency protocol, not patient-specific advice
        if re.search(r'what\s+(?:do|should)\s+I\s+do', query_lower):
            # If has possessive (my/our patient), it's patient-specific
            if re.search(r'\b(?:my|our|this)\s+patient', query_lower):
                return 'patient_emergency'
            # Otherwise, treat as general protocol question (safe if documented)
            return 'protocol'
        
        # Default: Emergency query without clear categorization
        # If it mentions "patient" generically without possessive, could be general
        if 'patient' in query_lower and not any(re.search(p, query_lower) for p in [r'\bmy\s+patient', r'\bour\s+patient', r'\bthis\s+patient']):
            return 'protocol'  # General reference, likely protocol question
        
        # Otherwise be conservative
        return 'patient_emergency'
    
    def detect_query_type(self, query: str) -> str:
        """
        Detect query type for threshold adjustment (Phase 1 addition)
        
        Returns:
            'direct' - Standard factual query
            'comparative' - Guideline comparison query
            'emergency_protocol' - Emergency protocol query
        """
        query_lower = query.lower()
        
        # Check for comparative queries
        comparative_keywords = [
            'difference', 'differ', 'compare', 'comparison', 'vs', 'versus',
            'which guideline', 'who or', 'national or', 'should i follow'
        ]
        if any(kw in query_lower for kw in comparative_keywords):
            return 'comparative'
        
        # Check for emergency protocol queries
        emergency_type = self.classify_emergency_query(query)
        if emergency_type in ['protocol', 'informational']:
            return 'emergency_protocol'
        
        return 'direct'
    
    def check_query_safety(self, query: str) -> SafetyCheck:
        """
        Check if query is safe and within scope
        
        CRITICAL: Check emergency classification FIRST, then patient-specific patterns
        
        Args:
            query: User query
            
        Returns:
            SafetyCheck result
        """
        query_lower = query.lower()
        
        # SPECIAL CASE: Check if this is a general emergency protocol query
        # These are SAFE if documented, even if they mention "patient" generally
        emergency_type = self.classify_emergency_query(query)
        if emergency_type in ['protocol', 'informational']:
            # This is a general protocol/info request - allow it to proceed
            # Will be refused later if evidence doesn't exist
            pass  # Continue to other checks
        elif emergency_type == 'patient_emergency':
            # Active patient emergency - refuse
            return SafetyCheck(
                passed=False,
                violation_type=SafetyViolationType.PATIENT_SPECIFIC,
                message="Query requests patient-specific emergency advice",
                severity="critical",
                recommended_action="Refuse with safe template"
            )
        
        # PRIORITY 2: Check for patient-specific requests
        # Skip patterns that were handled by emergency classification
        for i, pattern in enumerate(self.PATIENT_SPECIFIC_PATTERNS):
            if re.search(pattern, query_lower):
                # Double-check this isn't a general emergency protocol query
                if emergency_type in ['protocol', 'informational']:
                    continue  # Allow general protocol queries
                
                logger.debug(f"Query matched patient-specific pattern {i}: {pattern}")
                return SafetyCheck(
                    passed=False,
                    violation_type=SafetyViolationType.PATIENT_SPECIFIC,
                    message=f"Query requests patient-specific advice (pattern: {pattern[:50]}...)",
                    severity="critical",
                    recommended_action="Refuse with safe template"
                )
        
        # PRIORITY 2: Check for out-of-scope medical conditions
        # Check negative indicators FIRST (more specific)
        for pattern in self.OUT_OF_SCOPE_NEGATIVE_INDICATORS:
            if re.search(pattern, query_lower):
                return SafetyCheck(
                    passed=False,
                    violation_type=SafetyViolationType.OUT_OF_SCOPE,
                    message="Query is outside PPH scope (negative indicator)",
                    severity="high",
                    recommended_action="Refuse with out-of-scope template"
                )
        
        # Then check general out-of-scope patterns
        for pattern in self.OUT_OF_SCOPE_PATTERNS:
            if re.search(pattern, query_lower):
                # But allow if clearly in PPH context
                if not any(keyword in query_lower for keyword in ['pph', 'postpartum', 'hemorrhage', 'haemorrhage']):
                    return SafetyCheck(
                        passed=False,
                        violation_type=SafetyViolationType.OUT_OF_SCOPE,
                        message="Query is outside PPH scope",
                        severity="high",
                        recommended_action="Refuse with out-of-scope template"
                    )
        
        # All checks passed
        return SafetyCheck(
            passed=True,
            violation_type=None,
            message="Query is safe",
            severity="low",
            recommended_action="Proceed with retrieval"
        )
    
    def check_response_safety(
        self,
        response: str,
        retrieved_chunks: List[str],
        query: str
    ) -> SafetyCheck:
        """
        Check if generated response is safe
        
        Args:
            response: Generated response text
            retrieved_chunks: List of retrieved chunk texts
            query: Original query
            
        Returns:
            SafetyCheck result
        """
        response_lower = response.lower()
        
        # Check for patient-specific advice in response
        for pattern in self.PATIENT_SPECIFIC_PATTERNS:
            if re.search(pattern, response_lower):
                logger.warning(f"Response contains patient-specific advice: {pattern}")
                return SafetyCheck(
                    passed=False,
                    violation_type=SafetyViolationType.PATIENT_SPECIFIC,
                    message="Response contains patient-specific advice",
                    severity="critical",
                    recommended_action="Reject response, return safe refusal"
                )
        
        # Check for speculation
        speculation_count = sum(
            1 for pattern in self.SPECULATION_PATTERNS
            if re.search(pattern, response_lower)
        )
        if speculation_count > 2:  # Allow minimal hedging
            logger.warning(f"Response contains excessive speculation ({speculation_count} instances)")
            return SafetyCheck(
                passed=False,
                violation_type=SafetyViolationType.SPECULATION,
                message=f"Response contains excessive speculation ({speculation_count} instances)",
                severity="high",
                recommended_action="Regenerate with stricter prompt"
            )
        
        # Check for unsupported dosage recommendations
        dosage_in_response = any(
            re.search(pattern, response_lower)
            for pattern in self.DOSAGE_PATTERNS
        )
        
        if dosage_in_response:
            # Verify dosage is explicitly in retrieved chunks
            dosage_supported = any(
                re.search(pattern, chunk.lower())
                for chunk in retrieved_chunks
                for pattern in self.DOSAGE_PATTERNS
            )
            
            if not dosage_supported:
                logger.warning("Response contains dosage not found in retrieved chunks")
                return SafetyCheck(
                    passed=False,
                    violation_type=SafetyViolationType.UNSAFE_DOSAGE,
                    message="Response contains dosage not found in source documents",
                    severity="critical",
                    recommended_action="Reject response, return safe refusal"
                )
        
        # Check for hallucination (content not in retrieved chunks)
        hallucination_score = self._check_hallucination(response, retrieved_chunks)
        if hallucination_score > 0.3:  # More than 30% unsupported content
            logger.warning(f"Possible hallucination detected (score: {hallucination_score:.2f})")
            return SafetyCheck(
                passed=False,
                violation_type=SafetyViolationType.HALLUCINATION,
                message=f"Response may contain hallucinated content (score: {hallucination_score:.2f})",
                severity="critical",
                recommended_action="Reject response, regenerate with stricter grounding"
            )
        
        # All checks passed
        return SafetyCheck(
            passed=True,
            violation_type=None,
            message="Response is safe",
            severity="low",
            recommended_action="Deliver response"
        )
    
    def _check_hallucination(
        self,
        response: str,
        retrieved_chunks: List[str]
    ) -> float:
        """
        Estimate hallucination score (0.0 = fully grounded, 1.0 = fully hallucinated)
        
        Simple heuristic: check what percentage of response sentences contain
        key terms/phrases found in retrieved chunks.
        
        Args:
            response: Generated response
            retrieved_chunks: Source chunks
            
        Returns:
            Hallucination score between 0.0 and 1.0
        """
        # Extract key terms from retrieved chunks (simple word-based)
        chunk_text = " ".join(retrieved_chunks).lower()
        chunk_words = set(re.findall(r'\b\w{4,}\b', chunk_text))  # Words 4+ chars
        
        # Check response sentences
        sentences = re.split(r'[.!?]+', response)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
        
        if not sentences:
            return 0.0
        
        grounded_sentences = 0
        for sentence in sentences:
            sentence_lower = sentence.lower()
            sentence_words = set(re.findall(r'\b\w{4,}\b', sentence_lower))
            
            # Check overlap with source chunks
            if sentence_words:
                overlap = len(sentence_words & chunk_words) / len(sentence_words)
                if overlap > 0.3:  # At least 30% overlap
                    grounded_sentences += 1
        
        # Return proportion of ungrounded sentences
        hallucination_score = 1.0 - (grounded_sentences / len(sentences))
        return hallucination_score
    
    def get_safe_refusal(
        self,
        violation_type: SafetyViolationType
    ) -> str:
        """
        Get appropriate safe refusal message
        
        Args:
            violation_type: Type of safety violation
            
        Returns:
            Safe refusal message
        """
        return self.SAFE_REFUSAL_TEMPLATES.get(
            violation_type,
            self.SAFE_REFUSAL_TEMPLATES[SafetyViolationType.MISSING_EVIDENCE]
        )
    
    def log_violation(
        self,
        query: str,
        response: str,
        violation_type: SafetyViolationType,
        severity: str
    ):
        """Log safety violation for monitoring"""
        import datetime
        
        self.violation_log.append({
            "timestamp": datetime.datetime.now().isoformat(),
            "query": query[:200],  # Truncate for privacy
            "response": response[:200],
            "violation_type": violation_type.value,
            "severity": severity,
        })
        
        logger.warning(
            f"Safety violation logged: {violation_type.value} (severity: {severity})"
        )


class EvidenceGatedGenerator:
    """
    Evidence-gated response generator that ensures all claims are grounded
    """
    
    def __init__(self):
        self.guardrails = ClinicalSafetyGuardrails()
    
    def validate_and_generate_safe_response(
        self,
        query: str,
        retrieved_chunks: List[str],
        generated_response: str
    ) -> Tuple[bool, str, Optional[SafetyCheck]]:
        """
        Validate query and response, return safe output
        
        Args:
            query: User query
            retrieved_chunks: Retrieved source chunks
            generated_response: LLM-generated response
            
        Returns:
            Tuple of (is_safe, final_response, safety_check)
            is_safe: Whether response passed all safety checks
            final_response: Safe response text (original or refusal)
            safety_check: SafetyCheck result for logging
        """
        # Check query safety
        query_check = self.guardrails.check_query_safety(query)
        if not query_check.passed:
            logger.info(f"Query failed safety check: {query_check.message}")
            self.guardrails.log_violation(
                query, "", query_check.violation_type, query_check.severity
            )
            safe_response = self.guardrails.get_safe_refusal(query_check.violation_type)
            return False, safe_response, query_check
        
        # Check response safety
        response_check = self.guardrails.check_response_safety(
            generated_response,
            retrieved_chunks,
            query
        )
        
        if not response_check.passed:
            logger.warning(f"Response failed safety check: {response_check.message}")
            self.guardrails.log_violation(
                query,
                generated_response,
                response_check.violation_type,
                response_check.severity
            )
            safe_response = self.guardrails.get_safe_refusal(response_check.violation_type)
            return False, safe_response, response_check
        
        # All checks passed
        return True, generated_response, response_check


# Global instance
clinical_safety = ClinicalSafetyGuardrails()
evidence_gated_generator = EvidenceGatedGenerator()


def test_safety_guardrails():
    """Test safety guardrails with sample queries and responses"""
    
    test_cases = [
        {
            "query": "What dosage of oxytocin should I take?",
            "expected": "patient_specific",
        },
        {
            "query": "How is diabetes managed during pregnancy?",
            "expected": "out_of_scope",
        },
        {
            "query": "What are the risk factors for PPH?",
            "expected": "safe",
        },
        {
            "query": "Explain the management of severe PPH",
            "expected": "safe",
        },
    ]
    
    guardrails = ClinicalSafetyGuardrails()
    
    print("\nTesting Safety Guardrails:")
    print("=" * 80)
    
    for i, test in enumerate(test_cases, 1):
        query = test["query"]
        expected = test["expected"]
        
        check = guardrails.check_query_safety(query)
        
        print(f"\nTest {i}: {query}")
        print(f"  Expected: {expected}")
        print(f"  Result: {'PASS' if check.passed else 'FAIL'}")
        print(f"  Violation: {check.violation_type.value if check.violation_type else 'None'}")
        print(f"  Severity: {check.severity}")
        
        if not check.passed:
            refusal = guardrails.get_safe_refusal(check.violation_type)
            print(f"  Refusal: {refusal[:100]}...")


if __name__ == "__main__":
    test_safety_guardrails()

