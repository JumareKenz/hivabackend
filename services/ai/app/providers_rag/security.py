"""
Security Filter - Credential and Secret Detection

This module detects and blocks sensitive information:
- Passwords and default credentials
- API keys and tokens
- Secrets and admin instructions
- Internal system details

This is a critical security layer for production systems.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class SecurityIssue(str, Enum):
    """Types of security issues detected."""
    
    PASSWORD_DETECTED = "password_detected"
    DEFAULT_CREDENTIAL = "default_credential"
    API_KEY_DETECTED = "api_key_detected"
    TOKEN_DETECTED = "token_detected"
    SECRET_DETECTED = "secret_detected"
    ADMIN_INSTRUCTION = "admin_instruction"
    INTERNAL_SYSTEM_DETAIL = "internal_system_detail"


@dataclass
class SecurityCheckResult:
    """Result of a security check."""
    
    is_safe: bool
    issues: list[SecurityIssue]
    redacted_text: Optional[str] = None
    alert_message: Optional[str] = None


class SecurityFilter:
    """
    Filters out sensitive information from responses.
    
    This is a hard block - responses containing secrets
    must be redacted or refused.
    """
    
    def __init__(self):
        # Common default passwords (case-insensitive)
        self._default_passwords = {
            'password', 'pass', 'pass123', 'password123', 'admin', 'administrator',
            'root', 'user', 'guest', 'default', 'changeme', 'welcome', '123456',
            'euhler', 'euhler123',  # Known default from KB
        }
        
        # Password patterns
        self._password_patterns = [
            re.compile(r'\bpassword\s*[:=]\s*["\']?([^"\'\s]{3,})["\']?', re.IGNORECASE),
            re.compile(r'\bpass\s*[:=]\s*["\']?([^"\'\s]{3,})["\']?', re.IGNORECASE),
            re.compile(r'\bpwd\s*[:=]\s*["\']?([^"\'\s]{3,})["\']?', re.IGNORECASE),
            re.compile(r'\bdefault\s+password\s*[:=]\s*["\']?([^"\'\s]{3,})["\']?', re.IGNORECASE),
        ]
        
        # API key patterns
        self._api_key_patterns = [
            re.compile(r'\bapi[_-]?key\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{20,})["\']?', re.IGNORECASE),
            re.compile(r'\bapikey\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{20,})["\']?', re.IGNORECASE),
            re.compile(r'\bsecret[_-]?key\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{20,})["\']?', re.IGNORECASE),
            re.compile(r'\baccess[_-]?token\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{20,})["\']?', re.IGNORECASE),
            re.compile(r'\btoken\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{20,})["\']?', re.IGNORECASE),
            re.compile(r'\bgsk_[a-zA-Z0-9]{32,}', re.IGNORECASE),  # Groq API key format
            re.compile(r'\bsk-[a-zA-Z0-9]{32,}', re.IGNORECASE),  # OpenAI API key format
        ]
        
        # Secret patterns
        self._secret_patterns = [
            re.compile(r'\bsecret\s*[:=]\s*["\']?([^"\'\s]{10,})["\']?', re.IGNORECASE),
            re.compile(r'\bprivate[_-]?key\s*[:=]\s*["\']?([^"\'\s]{20,})["\']?', re.IGNORECASE),
            re.compile(r'\bcredential\s*[:=]\s*["\']?([^"\'\s]{10,})["\']?', re.IGNORECASE),
        ]
        
        # Admin instruction patterns
        self._admin_patterns = [
            re.compile(r'\badmin\s+password', re.IGNORECASE),
            re.compile(r'\broot\s+password', re.IGNORECASE),
            re.compile(r'\bdefault\s+login', re.IGNORECASE),
            re.compile(r'\bbackdoor', re.IGNORECASE),
            re.compile(r'\bbypass\s+security', re.IGNORECASE),
        ]
        
        # Internal system detail patterns
        self._internal_patterns = [
            re.compile(r'\blocalhost:\d+', re.IGNORECASE),
            re.compile(r'\b127\.0\.0\.1:\d+', re.IGNORECASE),
            re.compile(r'\binternal\s+ip', re.IGNORECASE),
            re.compile(r'\bprivate\s+endpoint', re.IGNORECASE),
        ]
        
        # Safe contexts where passwords might be mentioned (but not exposed)
        self._safe_password_contexts = [
            re.compile(r'change\s+your\s+password', re.IGNORECASE),
            re.compile(r'reset\s+your\s+password', re.IGNORECASE),
            re.compile(r'password\s+reset', re.IGNORECASE),
            re.compile(r'forgot\s+password', re.IGNORECASE),
            re.compile(r'password\s+policy', re.IGNORECASE),
            re.compile(r'password\s+requirements', re.IGNORECASE),
        ]
    
    def _is_safe_context(self, text: str, match_start: int, match_end: int) -> bool:
        """Check if password mention is in a safe context."""
        # Extract context around the match
        context_start = max(0, match_start - 50)
        context_end = min(len(text), match_end + 50)
        context = text[context_start:context_end]
        
        # Check if any safe pattern matches
        for pattern in self._safe_password_contexts:
            if pattern.search(context):
                return True
        
        return False
    
    def _redact_sensitive(self, text: str, matches: list[tuple[int, int]]) -> str:
        """Redact sensitive information from text."""
        # Sort matches by start position (descending) to avoid index shifting
        matches = sorted(matches, key=lambda x: x[0], reverse=True)
        
        redacted = text
        for start, end in matches:
            # Replace with redaction marker
            redacted = redacted[:start] + "[REDACTED]" + redacted[end:]
        
        return redacted
    
    def check(self, text: str) -> SecurityCheckResult:
        """
        Check text for security issues.
        
        Args:
            text: Text to check
            
        Returns:
            SecurityCheckResult with safety status and redacted text
        """
        issues: list[SecurityIssue] = []
        redaction_matches: list[tuple[int, int]] = []
        
        text_lower = text.lower()
        
        # Check for default passwords
        for default_pwd in self._default_passwords:
            # Look for exact word matches (not substrings)
            pattern = re.compile(rf'\b{re.escape(default_pwd)}\b', re.IGNORECASE)
            for match in pattern.finditer(text):
                # Check if it's in a safe context
                if not self._is_safe_context(text, match.start(), match.end()):
                    issues.append(SecurityIssue.DEFAULT_CREDENTIAL)
                    redaction_matches.append((match.start(), match.end()))
                    logger.warning(f"Default credential detected: {default_pwd}")
        
        # Check for password patterns
        for pattern in self._password_patterns:
            for match in pattern.finditer(text):
                password_value = match.group(1) if match.groups() else ""
                # Check if it's a default password
                if password_value.lower() in self._default_passwords:
                    if not self._is_safe_context(text, match.start(), match.end()):
                        issues.append(SecurityIssue.PASSWORD_DETECTED)
                        redaction_matches.append((match.start(), match.end()))
                        logger.warning("Password pattern detected in response")
        
        # Check for API keys
        for pattern in self._api_key_patterns:
            for match in pattern.finditer(text):
                issues.append(SecurityIssue.API_KEY_DETECTED)
                redaction_matches.append((match.start(), match.end()))
                logger.warning("API key pattern detected in response")
        
        # Check for tokens
        for pattern in self._api_key_patterns:  # Tokens use similar patterns
            for match in pattern.finditer(text):
                if SecurityIssue.TOKEN_DETECTED not in issues:
                    issues.append(SecurityIssue.TOKEN_DETECTED)
                redaction_matches.append((match.start(), match.end()))
        
        # Check for secrets
        for pattern in self._secret_patterns:
            for match in pattern.finditer(text):
                issues.append(SecurityIssue.SECRET_DETECTED)
                redaction_matches.append((match.start(), match.end()))
                logger.warning("Secret pattern detected in response")
        
        # Check for admin instructions
        for pattern in self._admin_patterns:
            if pattern.search(text):
                issues.append(SecurityIssue.ADMIN_INSTRUCTION)
                logger.warning("Admin instruction pattern detected")
        
        # Check for internal system details
        for pattern in self._internal_patterns:
            if pattern.search(text):
                issues.append(SecurityIssue.INTERNAL_SYSTEM_DETAIL)
                logger.warning("Internal system detail detected")
        
        # Remove duplicate matches (overlapping)
        redaction_matches = self._merge_overlapping_ranges(redaction_matches)
        
        # Redact if needed
        redacted_text = None
        if redaction_matches:
            redacted_text = self._redact_sensitive(text, redaction_matches)
        
        is_safe = len(issues) == 0
        
        alert_message = None
        if not is_safe:
            alert_message = f"Security issues detected: {', '.join(set(i.value for i in issues))}"
            logger.error(alert_message)
        
        return SecurityCheckResult(
            is_safe=is_safe,
            issues=issues,
            redacted_text=redacted_text,
            alert_message=alert_message,
        )
    
    def _merge_overlapping_ranges(self, ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
        """Merge overlapping ranges."""
        if not ranges:
            return []
        
        # Sort by start position
        sorted_ranges = sorted(ranges, key=lambda x: x[0])
        merged = [sorted_ranges[0]]
        
        for current in sorted_ranges[1:]:
            last = merged[-1]
            # If current overlaps with last, merge them
            if current[0] <= last[1]:
                merged[-1] = (last[0], max(last[1], current[1]))
            else:
                merged.append(current)
        
        return merged
