"""
Response Integrity Layer - Production-Grade Text Validation

This module enforces strict quality standards on all responses:
- Completeness validation (no truncation)
- Word boundary validation (no merged words)
- Sentence completeness (no broken sentences)
- Markdown validation (proper formatting)
- Citation enforcement (mandatory citations)
- Unicode normalization (proper spacing)

This is the final gate before any response is released to users.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class IntegrityIssue(str, Enum):
    """Types of integrity issues detected."""
    
    TRUNCATED_SENTENCE = "truncated_sentence"
    TRUNCATED_PARAGRAPH = "truncated_paragraph"
    MERGED_WORDS = "merged_words"
    BROKEN_SPACING = "broken_spacing"
    MALFORMED_MARKDOWN = "malformed_markdown"
    MISSING_CITATIONS = "missing_citations"
    INCOMPLETE_ANSWER = "incomplete_answer"
    UNICODE_ISSUES = "unicode_issues"


@dataclass
class IntegrityCheckResult:
    """Result of an integrity check."""
    
    is_valid: bool
    issues: list[IntegrityIssue]
    details: dict[str, str]
    normalized_text: Optional[str] = None


class ResponseIntegrityValidator:
    """
    Validates response integrity before release.
    
    This is a hard gate - responses that fail validation
    must be regenerated or refused.
    """
    
    def __init__(self):
        # Minimum response length (characters)
        self.min_response_length = 20
        
        # Maximum response length (characters) - prevent runaway responses
        self.max_response_length = 5000
        
        # Minimum sentence count for complete answers
        self.min_sentences = 1
        
        # Patterns for detecting issues
        self._merged_word_pattern = re.compile(
            r'\b[a-z]{15,}\b',  # Words longer than 15 chars likely merged
            re.IGNORECASE
        )
        
        self._broken_spacing_pattern = re.compile(
            r'[a-z][A-Z]',  # Lowercase followed by uppercase (missing space)
        )
        
        self._truncated_sentence_pattern = re.compile(
            r'[^.!?]\s*$',  # Ends without sentence ending
        )
        
        self._malformed_markdown_patterns = [
            re.compile(r'^\*\s*$', re.MULTILINE),  # Empty bullet point
            re.compile(r'^\d+\.\s*$', re.MULTILINE),  # Empty numbered item
            re.compile(r'\[.*?\]\(\)'),  # Empty markdown link
            re.compile(r'```[^`]*$'),  # Unclosed code block
        ]
        
        # Common merged word patterns (false positives to ignore)
        self._known_long_words = {
            'authorization', 'authentication', 'administrator', 'configuration',
            'implementation', 'documentation', 'troubleshooting', 'international',
            'telecommunications', 'infrastructure', 'comprehensive', 'acknowledgment'
        }
    
    def normalize_unicode(self, text: str) -> str:
        """
        Normalize Unicode to fix spacing and character issues.
        
        Handles:
        - Non-breaking spaces
        - Zero-width spaces
        - Multiple spaces
        - Mixed line endings
        """
        # Normalize Unicode (NFKC - Compatibility Decomposition + Composition)
        text = unicodedata.normalize('NFKC', text)
        
        # Replace non-breaking spaces with regular spaces
        text = text.replace('\u00A0', ' ')  # Non-breaking space
        text = text.replace('\u2000', ' ')  # En quad
        text = text.replace('\u2001', ' ')  # Em quad
        text = text.replace('\u2002', ' ')  # En space
        text = text.replace('\u2003', ' ')  # Em space
        text = text.replace('\u2004', ' ')  # Three-per-em space
        text = text.replace('\u2005', ' ')  # Four-per-em space
        text = text.replace('\u2006', ' ')  # Six-per-em space
        text = text.replace('\u2007', ' ')  # Figure space
        text = text.replace('\u2008', ' ')  # Punctuation space
        text = text.replace('\u2009', ' ')  # Thin space
        text = text.replace('\u200A', ' ')  # Hair space
        text = text.replace('\u202F', ' ')  # Narrow no-break space
        text = text.replace('\u205F', ' ')  # Medium mathematical space
        text = text.replace('\u3000', ' ')  # Ideographic space
        
        # Remove zero-width characters
        text = text.replace('\u200B', '')  # Zero-width space
        text = text.replace('\u200C', '')  # Zero-width non-joiner
        text = text.replace('\u200D', '')  # Zero-width joiner
        text = text.replace('\uFEFF', '')  # Zero-width no-break space
        
        # Normalize line endings
        text = text.replace('\r\n', '\n')
        text = text.replace('\r', '\n')
        
        # Fix multiple spaces
        text = re.sub(r' +', ' ', text)
        
        # Fix multiple newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Remove trailing whitespace from lines
        lines = [line.rstrip() for line in text.split('\n')]
        text = '\n'.join(lines)
        
        return text.strip()
    
    def detect_merged_words(self, text: str) -> list[str]:
        """Detect words that appear to be merged together."""
        merged = []
        
        # Find all long words
        matches = self._merged_word_pattern.findall(text)
        
        for word in matches:
            word_lower = word.lower()
            # Skip known long words
            if word_lower not in self._known_long_words:
                # Check if it looks like multiple words merged
                # Simple heuristic: if it has multiple capital letters in the middle
                if re.search(r'[a-z][A-Z]', word):
                    merged.append(word)
                # Or if it's unusually long for a single word
                elif len(word) > 20:
                    merged.append(word)
        
        return merged
    
    def detect_broken_spacing(self, text: str) -> list[str]:
        """Detect places where spaces are missing between words."""
        broken = []
        
        matches = self._broken_spacing_pattern.findall(text)
        for match in matches[:10]:  # Limit to first 10
            broken.append(match)
        
        return broken
    
    def check_sentence_completeness(self, text: str) -> tuple[bool, str]:
        """
        Check if all sentences are complete.
        
        Returns (is_complete, reason)
        """
        if not text.strip():
            return False, "Empty response"
        
        # Split into sentences
        sentences = re.split(r'[.!?]+\s+', text)
        
        # Check if last sentence is complete
        last_sentence = sentences[-1] if sentences else ""
        remaining_text = text[text.rfind(last_sentence):] if last_sentence else text
        
        # If text doesn't end with sentence-ending punctuation
        if not re.search(r'[.!?]$', text.rstrip()):
            # Check if it's a list (which might end without punctuation)
            if not re.search(r'[:\-•]', remaining_text[-50:]):
                return False, "Response ends without sentence-ending punctuation"
        
        # Check minimum sentence count
        complete_sentences = [s for s in sentences if s.strip()]
        if len(complete_sentences) < self.min_sentences:
            return False, f"Too few complete sentences: {len(complete_sentences)}"
        
        return True, ""
    
    def check_markdown(self, text: str) -> tuple[bool, list[str]]:
        """Check for malformed Markdown."""
        issues = []
        
        for pattern in self._malformed_markdown_patterns:
            matches = pattern.findall(text)
            if matches:
                issues.append(f"Malformed markdown: {pattern.pattern}")
        
        return len(issues) == 0, issues
    
    def validate(
        self,
        text: str,
        require_citations: bool = True,
        citations: Optional[list] = None,
    ) -> IntegrityCheckResult:
        """
        Validate response integrity.
        
        Args:
            text: Response text to validate
            require_citations: Whether citations are mandatory
            citations: List of citations (if available)
            
        Returns:
            IntegrityCheckResult with validation status and issues
        """
        issues: list[IntegrityIssue] = []
        details: dict[str, str] = {}
        
        # Normalize Unicode first
        normalized = self.normalize_unicode(text)
        
        # Check minimum length
        if len(normalized) < self.min_response_length:
            issues.append(IntegrityIssue.INCOMPLETE_ANSWER)
            details["length"] = f"Response too short: {len(normalized)} chars"
        
        # Check maximum length
        if len(normalized) > self.max_response_length:
            issues.append(IntegrityIssue.TRUNCATED_PARAGRAPH)
            details["length"] = f"Response too long: {len(normalized)} chars"
        
        # Check sentence completeness
        is_complete, reason = self.check_sentence_completeness(normalized)
        if not is_complete:
            issues.append(IntegrityIssue.TRUNCATED_SENTENCE)
            details["sentence_completeness"] = reason
        
        # Check for merged words
        merged = self.detect_merged_words(normalized)
        if merged:
            issues.append(IntegrityIssue.MERGED_WORDS)
            details["merged_words"] = f"Found {len(merged)} potentially merged words: {merged[:5]}"
        
        # Check for broken spacing
        broken = self.detect_broken_spacing(normalized)
        if broken:
            issues.append(IntegrityIssue.BROKEN_SPACING)
            details["broken_spacing"] = f"Found {len(broken)} spacing issues"
        
        # Check Markdown
        markdown_ok, markdown_issues = self.check_markdown(normalized)
        if not markdown_ok:
            issues.append(IntegrityIssue.MALFORMED_MARKDOWN)
            details["markdown"] = "; ".join(markdown_issues)
        
        # Check citations (if required)
        if require_citations:
            if not citations or len(citations) == 0:
                issues.append(IntegrityIssue.MISSING_CITATIONS)
                details["citations"] = "Citations are required but none were provided"
        
        # Check for Unicode issues (if normalization changed the text)
        if normalized != text:
            # Only flag if significant changes
            if len(normalized) != len(text) or abs(len(normalized) - len(text)) > len(text) * 0.1:
                issues.append(IntegrityIssue.UNICODE_ISSUES)
                details["unicode"] = "Unicode normalization applied significant changes"
        
        is_valid = len(issues) == 0
        
        return IntegrityCheckResult(
            is_valid=is_valid,
            issues=issues,
            details=details,
            normalized_text=normalized if normalized != text else None,
        )
