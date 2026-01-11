"""
Text Integrity Module - Production-Grade Text Normalization
Fast, accurate, and preserves known words.
"""
import re
import unicodedata
import time


class TextIntegrityProcessor:
    """Fast, accurate text normalization for LLM outputs."""
    
    # Known words/acronyms that should NEVER be split
    KNOWN_WORDS = [
        'ZAMCHEMA', 'Zamfara', 'State', 'Contributory', 'Healthcare', 'Health', 'Care',
        'Management', 'Agency', 'Scheme', 'contribution', 'contributions', 'premium',
        'premiums', 'program', 'programs', 'service', 'services', 'facility', 'facilities',
    ]
    
    def __init__(self):
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Pre-compile regex patterns."""
        # Fix split words (incorrectly split by model) - MUST BE FIRST
        self.split_word_fixes = [
            (re.compile(r'\bZAMCHEM\s+A\b', re.I), 'ZAMCHEMA'),
            (re.compile(r'\bZAM\s+CHEMA\b', re.I), 'ZAMCHEMA'),
            (re.compile(r'\bZamfar\s+a\b', re.I), 'Zamfara'),
            (re.compile(r'\bZa\s+mfara\b', re.I), 'Zamfara'),
            (re.compile(r'\bst\s+a\s+t\s+e\b', re.I), 'state'),
            (re.compile(r'\ba\s+gency\b', re.I), 'agency'),
            (re.compile(r'\bc\s+a\s+re\b', re.I), 'care'),
            (re.compile(r'\bheal\s+th\b', re.I), 'health'),
            (re.compile(r'\bresi\s+dent\b', re.I), 'resident'),
            (re.compile(r'\ba\s+ccess\b', re.I), 'access'),
            (re.compile(r'\ba\s+ffordable\b', re.I), 'affordable'),
            (re.compile(r'\ba\s+vailable\b', re.I), 'available'),
            (re.compile(r'\bever\s+y\b', re.I), 'every'),
            (re.compile(r'\bman\s+age\b', re.I), 'manage'),
            (re.compile(r'\bman\s+age\s+ment\b', re.I), 'management'),
            (re.compile(r'\bCont\s+ributory\b', re.I), 'Contributory'),
            (re.compile(r'\bHeal\s+thcare\b', re.I), 'Healthcare'),
            (re.compile(r'\bMana\s+gement\b', re.I), 'Management'),
        ]
        
        # Patterns for adding spaces (but NOT splitting known words)
        self.punct_no_space = re.compile(r'([.!?,:;])([A-Za-z])')
        self.emoji_no_space = re.compile(r'([\U0001F600-\U0001F9FF])([A-Za-z])')
        # Only split if NOT a known word
        self.merged_case = re.compile(r'([a-z])([A-Z])')
        self.acronym_word = re.compile(r'([A-Z]{2,})([a-z]{2,})')  # ACRONYMword -> ACRONYM word
        self.contraction_no_space = re.compile(r"([A-Za-z]'[a-z]{1,2})([a-z]{3,})")
        
        # Common word endings
        word_endings = 'ly|ed|ing|er|est|tion|sion|ment|ness|ful|less|able|ible|ous|ive|al|ic'
        self.word_ending_pattern = re.compile(f'([a-z]+(?:{word_endings}))([a-z]{{4,}})\b', re.I)
        
        # Common words
        common_words = 'the|and|or|for|with|from|to|in|on|at|by|is|are|was|were|has|have|had|can|will|would|should|could|may|might|this|that|these|those|a|an|of|as|if|so|do|does|did|get|got|go|goes|went|come|came|see|saw|know|knew|think|thought|say|said|tell|told|ask|asked|give|gave|take|took|make|made|use|used|want|wanted|need|needed|try|tried|work|worked|help|helped|call|called|contact|contacted|reach|reached|find|found|look|looked|check|checked|visit|visited|glad|happy|sorry|sure|here|there|where|when|what|who|how|why|every|any|some|all|each|both|many|much|more|most|very|quite|really|just|only|also|even|still|already|yet|again|once|twice|always|never|often|sometimes|usually|rarely|seldom|hello|hi|hey|thanks|thank|please'
        self.common_word_pattern = re.compile(f'\b({common_words})([a-z]{{3,}})\b', re.I)
    
    def _is_known_word(self, word: str) -> bool:
        """Check if word is a known word (case-insensitive)."""
        word_upper = word.upper()
        word_lower = word.lower()
        word_title = word.capitalize()
        return any(kw.upper() == word_upper or kw.lower() == word_lower or kw == word_title 
                   for kw in self.KNOWN_WORDS)
    
    def normalize(self, text: str) -> str:
        """Normalize text - fast and accurate."""
        if not text or not text.strip():
            return text
        
        start = time.perf_counter()
        
        # Step 1: Unicode normalization
        text = unicodedata.normalize('NFKC', text)
        
        # Step 2: Fix split words FIRST
        for pattern, replacement in self.split_word_fixes:
            text = pattern.sub(replacement, text)
        
        # Step 3: Add space after punctuation
        text = self.punct_no_space.sub(r'\1 \2', text)
        
        # Step 4: Add space after emoji
        text = self.emoji_no_space.sub(r'\1 \2', text)
        
        # Step 5: Fix acronym + word (ZAMCHEMAis -> ZAMCHEMA is)
        def split_acronym_word(match):
            acronym = match.group(1)
            word = match.group(2)
            if self._is_known_word(acronym):
                return acronym + ' ' + word
            return match.group(0)
        text = self.acronym_word.sub(split_acronym_word, text)
        
        # Step 6: Fix merged case (wordWord -> word Word) but preserve known words
        def split_merged_case(match):
            word1 = match.group(1)
            word2 = match.group(2)
            combined = word1 + word2
            # Don't split if it's a known word
            if self._is_known_word(combined):
                return match.group(0)
            return word1 + ' ' + word2
        text = self.merged_case.sub(split_merged_case, text)
        
        # Step 7: Fix contractions
        text = self.contraction_no_space.sub(r'\1 \2', text)
        
        # Step 8: Fix word endings + new word (conservative)
        text = self.word_ending_pattern.sub(r'\1 \2', text)
        
        # Step 9: Fix common words + new word (conservative)
        text = self.common_word_pattern.sub(r'\1 \2', text)
        
        # Step 10: Cleanup
        text = re.sub(r' {2,}', ' ', text)
        text = re.sub(r'\s+([.!?,:;])', r'\1', text)
        text = text.strip()
        
        elapsed = (time.perf_counter() - start) * 1000
        if elapsed > 5:
            import logging
            logging.warning(f"Text normalization took {elapsed:.2f}ms")
        
        return text


_processor = None

def normalize_text(text: str) -> str:
    """Public API."""
    global _processor
    if _processor is None:
        _processor = TextIntegrityProcessor()
    return _processor.normalize(text)
