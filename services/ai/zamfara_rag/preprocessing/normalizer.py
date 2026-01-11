"""
Text normalization module for Zamfara RAG system.

Standardizes text formatting, handles special characters, and ensures
consistency across documents from different sources.
"""

from __future__ import annotations

import re
import unicodedata
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class TextNormalizer:
    """
    Normalizes text for consistent processing and embedding.
    
    Features:
    - Unicode normalization
    - Case handling
    - Number formatting
    - Abbreviation expansion
    - Formal language standardization
    """
    
    # Common abbreviations in government/administrative documents
    ABBREVIATIONS = {
        # Titles
        "hon.": "Honorable",
        "hon": "Honorable",
        "dr.": "Doctor",
        "dr": "Doctor",
        "prof.": "Professor",
        "mr.": "Mister",
        "mrs.": "Mistress",
        "ms.": "Miss",
        
        # Government terms
        "govt.": "Government",
        "govt": "Government",
        "min.": "Ministry",
        "dept.": "Department",
        "dept": "Department",
        "comm.": "Commissioner",
        "dir.": "Director",
        "sec.": "Secretary",
        "exec.": "Executive",
        "admin.": "Administration",
        "auth.": "Authority",
        
        # Legal/administrative
        "no.": "Number",
        "ref.": "Reference",
        "re:": "Regarding",
        "viz.": "namely",
        "i.e.": "that is",
        "e.g.": "for example",
        "etc.": "and so forth",
        "et al.": "and others",
        
        # Measurements
        "approx.": "approximately",
        "max.": "maximum",
        "min.": "minimum",
        "avg.": "average",
    }
    
    # Nigerian state abbreviations
    STATE_ABBREVIATIONS = {
        "zam": "Zamfara",
        "zmf": "Zamfara",
        "fct": "Federal Capital Territory",
        "abj": "Abuja",
        "kn": "Kano",
        "kd": "Kaduna",
        "skt": "Sokoto",
        "kg": "Kogi",
    }
    
    def __init__(
        self,
        expand_abbreviations: bool = True,
        normalize_unicode: bool = True,
        preserve_case: bool = True,
        normalize_numbers: bool = True,
    ):
        """
        Initialize the text normalizer.
        
        Args:
            expand_abbreviations: Expand common abbreviations
            normalize_unicode: Apply Unicode normalization
            preserve_case: Keep original case (vs. lowercasing)
            normalize_numbers: Standardize number formats
        """
        self.expand_abbreviations = expand_abbreviations
        self.normalize_unicode = normalize_unicode
        self.preserve_case = preserve_case
        self.normalize_numbers = normalize_numbers
        
        # Build abbreviation patterns
        self._abbrev_pattern = None
        if expand_abbreviations:
            # Combine all abbreviations
            all_abbrevs = {**self.ABBREVIATIONS, **self.STATE_ABBREVIATIONS}
            # Sort by length (longest first) for correct matching
            sorted_abbrevs = sorted(all_abbrevs.keys(), key=len, reverse=True)
            # Escape and create pattern
            escaped = [re.escape(a) for a in sorted_abbrevs]
            self._abbrev_pattern = re.compile(
                r"\b(" + "|".join(escaped) + r")\b",
                re.IGNORECASE
            )
            self._abbrevs = all_abbrevs
    
    def normalize(self, text: str) -> str:
        """
        Normalize the input text.
        
        Args:
            text: Text to normalize
            
        Returns:
            Normalized text
        """
        if not text:
            return ""
        
        # Step 1: Unicode normalization (NFC form)
        if self.normalize_unicode:
            text = self._normalize_unicode(text)
        
        # Step 2: Expand abbreviations
        if self.expand_abbreviations and self._abbrev_pattern:
            text = self._expand_abbreviations(text)
        
        # Step 3: Normalize numbers
        if self.normalize_numbers:
            text = self._normalize_numbers(text)
        
        # Step 4: Normalize quotation marks and dashes
        text = self._normalize_punctuation(text)
        
        # Step 5: Normalize whitespace within sentences
        text = self._normalize_sentence_spacing(text)
        
        return text
    
    def _normalize_unicode(self, text: str) -> str:
        """Apply Unicode NFC normalization."""
        # NFC: Canonical Decomposition, followed by Canonical Composition
        text = unicodedata.normalize("NFC", text)
        
        # Replace common problematic characters
        replacements = {
            "\u2018": "'",   # Left single quote
            "\u2019": "'",   # Right single quote
            "\u201c": '"',   # Left double quote
            "\u201d": '"',   # Right double quote
            "\u2013": "-",   # En dash
            "\u2014": "-",   # Em dash
            "\u2026": "...", # Ellipsis
            "\u00a0": " ",   # Non-breaking space
            "\u200b": "",    # Zero-width space
            "\ufeff": "",    # BOM
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        return text
    
    def _expand_abbreviations(self, text: str) -> str:
        """Expand abbreviations to full forms."""
        def replace_abbrev(match: re.Match) -> str:
            abbrev = match.group(1).lower()
            # Get the expansion
            expansion = self._abbrevs.get(abbrev, match.group(1))
            
            # Preserve original capitalization pattern
            original = match.group(1)
            if original.isupper():
                return expansion.upper()
            elif original[0].isupper():
                return expansion.capitalize()
            else:
                return expansion.lower()
        
        return self._abbrev_pattern.sub(replace_abbrev, text)
    
    def _normalize_numbers(self, text: str) -> str:
        """Standardize number formats."""
        # Add comma separators to large numbers (thousands)
        # E.g., 1000000 → 1,000,000
        def add_commas(match: re.Match) -> str:
            num = match.group(0)
            # Don't modify numbers that already have formatting
            if "," in num or "." in num:
                return num
            # Format with comma separators
            try:
                return f"{int(num):,}"
            except ValueError:
                return num
        
        # Match numbers with 4+ digits not followed by decimal
        text = re.sub(r"\b\d{4,}\b(?!\.\d)", add_commas, text)
        
        # Normalize percentage formats
        text = re.sub(r"(\d+)\s*%", r"\1%", text)
        text = re.sub(r"(\d+)\s+percent\b", r"\1%", text, flags=re.IGNORECASE)
        
        # Normalize currency (Nigerian Naira)
        text = re.sub(r"(?:NGN|₦)\s*(\d)", r"₦\1", text)
        text = re.sub(r"(\d)\s*naira\b", r"\1 Naira", text, flags=re.IGNORECASE)
        
        return text
    
    def _normalize_punctuation(self, text: str) -> str:
        """Normalize quotation marks, dashes, and other punctuation."""
        # Standardize quote marks
        text = re.sub(r"[`´''‚]", "'", text)
        text = re.sub(r'[""„]', '"', text)
        
        # Standardize dashes
        text = re.sub(r"[–—−]", "-", text)
        
        # Fix double punctuation
        text = re.sub(r"([.!?])\s*\1+", r"\1", text)
        
        # Ensure space after punctuation (except in numbers or abbreviations)
        text = re.sub(r"([.!?,;:])([A-Za-z])", r"\1 \2", text)
        
        return text
    
    def _normalize_sentence_spacing(self, text: str) -> str:
        """Ensure consistent spacing between sentences."""
        # Double space after period → single space
        text = re.sub(r"([.!?])\s{2,}", r"\1 ", text)
        
        return text
    
    def normalize_for_embedding(self, text: str) -> str:
        """
        Apply normalization optimized for embedding generation.
        
        This applies lighter normalization focused on semantic preservation.
        """
        if not text:
            return ""
        
        # Basic Unicode normalization
        text = unicodedata.normalize("NFC", text)
        
        # Remove zero-width characters
        text = re.sub(r"[\u200b\ufeff]", "", text)
        
        # Normalize whitespace
        text = re.sub(r"\s+", " ", text)
        
        return text.strip()
    
    def normalize_query(self, query: str) -> str:
        """
        Normalize a user query for retrieval.
        
        Applies focused normalization for query matching.
        """
        if not query:
            return ""
        
        # Basic cleaning
        query = query.strip()
        
        # Unicode normalization
        query = unicodedata.normalize("NFC", query)
        
        # Remove excessive punctuation
        query = re.sub(r"[?!.]+$", "", query)
        
        # Normalize whitespace
        query = re.sub(r"\s+", " ", query)
        
        return query.strip()




