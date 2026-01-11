"""
Text cleaning module for Zamfara RAG system.

Removes noise, headers, footers, page numbers, and other artifacts
from extracted document text while preserving meaningful content.
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CleaningStats:
    """Statistics about the cleaning process."""
    original_length: int
    cleaned_length: int
    lines_removed: int
    patterns_applied: int
    
    @property
    def reduction_percent(self) -> float:
        if self.original_length == 0:
            return 0.0
        return ((self.original_length - self.cleaned_length) / self.original_length) * 100


class TextCleaner:
    """
    Cleans extracted document text by removing noise and artifacts.
    
    Features:
    - Header/footer removal
    - Page number removal
    - Whitespace normalization
    - Special character cleaning
    - Duplicate line removal
    """
    
    # Patterns for common headers/footers
    HEADER_FOOTER_PATTERNS = [
        # Page numbers
        r"^[\s]*(?:page|pg\.?|p\.?)\s*\d+[\s]*$",
        r"^[\s]*\d+[\s]*$",  # Standalone numbers (likely page numbers)
        r"^[\s]*-\s*\d+\s*-[\s]*$",  # Page numbers like "- 12 -"
        
        # Common headers
        r"^[\s]*(?:confidential|draft|internal use only)[\s]*$",
        r"^[\s]*(?:official use|classified)[\s]*$",
        
        # Document metadata lines
        r"^[\s]*(?:printed|generated|created)\s+(?:on|at)\s+.*$",
        r"^[\s]*file:\s+.*$",
        
        # Watermarks
        r"^[\s]*(?:watermark|sample|preview)[\s]*$",
        
        # Empty formatted lines
        r"^[\s_\-=]+$",
    ]
    
    # Patterns for noise removal
    NOISE_PATTERNS = [
        # Multiple consecutive blank lines → single blank line
        (r"\n{3,}", "\n\n"),
        
        # Multiple spaces → single space
        (r"[ \t]{2,}", " "),
        
        # Space before punctuation
        (r"\s+([.,;:!?])", r"\1"),
        
        # Remove invisible characters
        (r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", ""),
        
        # Normalize bullet points
        (r"^[\s]*[•●○▪▸►◦‣⁃]\s*", "• ", re.MULTILINE),
        
        # Normalize dashes in lists
        (r"^[\s]*[-–—]\s+", "- ", re.MULTILINE),
        
        # Remove repeated punctuation
        (r"([.,;:!?])\1+", r"\1"),
        
        # Fix common OCR artifacts
        (r"\bl\b(?=[a-z])", "I"),  # Common OCR: l → I at word start
        (r"(?<=[a-z])\bl\b", "l"),  # Keep l in words
    ]
    
    def __init__(
        self,
        remove_headers: bool = True,
        remove_footers: bool = True,
        normalize_whitespace: bool = True,
        remove_page_numbers: bool = True,
        min_line_length: int = 5,
    ):
        """
        Initialize the text cleaner.
        
        Args:
            remove_headers: Remove common header patterns
            remove_footers: Remove common footer patterns
            normalize_whitespace: Normalize whitespace and line breaks
            remove_page_numbers: Remove standalone page numbers
            min_line_length: Minimum line length to keep
        """
        self.remove_headers = remove_headers
        self.remove_footers = remove_footers
        self.normalize_whitespace = normalize_whitespace
        self.remove_page_numbers = remove_page_numbers
        self.min_line_length = min_line_length
        
        # Compile patterns for efficiency
        self._header_footer_patterns = [
            re.compile(p, re.IGNORECASE | re.MULTILINE)
            for p in self.HEADER_FOOTER_PATTERNS
        ]
        
        self._noise_patterns = []
        for pattern in self.NOISE_PATTERNS:
            if len(pattern) == 2:
                self._noise_patterns.append((
                    re.compile(pattern[0]),
                    pattern[1]
                ))
            else:
                self._noise_patterns.append((
                    re.compile(pattern[0], pattern[2]),
                    pattern[1]
                ))
    
    def clean(self, text: str) -> tuple[str, CleaningStats]:
        """
        Clean the input text.
        
        Args:
            text: Raw text to clean
            
        Returns:
            Tuple of (cleaned_text, cleaning_stats)
        """
        if not text:
            return "", CleaningStats(0, 0, 0, 0)
        
        original_length = len(text)
        patterns_applied = 0
        lines_removed = 0
        
        # Step 1: Line-by-line cleaning
        lines = text.split("\n")
        cleaned_lines = []
        
        for line in lines:
            # Check if line matches header/footer patterns
            should_remove = False
            
            if self.remove_headers or self.remove_footers or self.remove_page_numbers:
                for pattern in self._header_footer_patterns:
                    if pattern.match(line):
                        should_remove = True
                        lines_removed += 1
                        break
            
            # Check minimum line length (but keep empty lines for paragraph structure)
            if not should_remove:
                stripped = line.strip()
                if stripped and len(stripped) < self.min_line_length:
                    # Keep if it's a valid short item (e.g., "Yes", "No", numbered items)
                    if not re.match(r"^(?:\d+[.)]?|[a-z][.)]|\w{1,4})$", stripped, re.IGNORECASE):
                        should_remove = True
                        lines_removed += 1
            
            if not should_remove:
                cleaned_lines.append(line)
        
        text = "\n".join(cleaned_lines)
        
        # Step 2: Apply noise patterns
        if self.normalize_whitespace:
            for pattern, replacement in self._noise_patterns:
                new_text = pattern.sub(replacement, text)
                if new_text != text:
                    patterns_applied += 1
                text = new_text
        
        # Step 3: Final cleanup
        text = self._final_cleanup(text)
        
        stats = CleaningStats(
            original_length=original_length,
            cleaned_length=len(text),
            lines_removed=lines_removed,
            patterns_applied=patterns_applied,
        )
        
        logger.debug(
            f"Cleaned text: {stats.original_length} → {stats.cleaned_length} chars "
            f"({stats.reduction_percent:.1f}% reduction)"
        )
        
        return text, stats
    
    def _final_cleanup(self, text: str) -> str:
        """Apply final cleanup steps."""
        # Strip leading/trailing whitespace
        text = text.strip()
        
        # Ensure consistent line endings
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        
        # Remove trailing whitespace from each line
        lines = [line.rstrip() for line in text.split("\n")]
        text = "\n".join(lines)
        
        # Collapse multiple newlines
        text = re.sub(r"\n{3,}", "\n\n", text)
        
        return text
    
    def clean_batch(self, texts: list[str]) -> list[tuple[str, CleaningStats]]:
        """Clean multiple texts."""
        return [self.clean(text) for text in texts]




