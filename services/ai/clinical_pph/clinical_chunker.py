"""
Clinical-Aware Chunking System for PPH Guidelines

This module implements intelligent chunking specifically designed for clinical documents:
- Section-aligned chunking (preserves clinical concepts)
- 300-600 tokens per chunk (optimal for semantic retrieval)
- Clinical context extraction
- Preserves clinical tables, protocols, and contraindications
"""

import re
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ClinicalChunk:
    """Represents a semantically meaningful clinical chunk"""
    text: str
    chunk_index: int
    section_title: Optional[str]
    clinical_context: List[str]  # e.g., ['prevention', 'diagnosis', 'management']
    pph_severity: Optional[str]  # 'mild', 'moderate', 'severe', 'any'
    contains_dosage: bool
    contains_protocol: bool
    contains_contraindication: bool
    token_count: int
    character_count: int
    
    def to_metadata(self) -> Dict[str, Any]:
        """Convert to metadata dict for vector store"""
        return {
            "chunk_index": self.chunk_index,
            "section_title": self.section_title or "Unknown",
            "clinical_context": ",".join(self.clinical_context),
            "pph_severity": self.pph_severity or "any",
            "contains_dosage": self.contains_dosage,
            "contains_protocol": self.contains_protocol,
            "contains_contraindication": self.contains_contraindication,
            "token_count": self.token_count,
            "character_count": self.character_count,
        }


class ClinicalChunker:
    """
    Clinical-aware text chunker that preserves medical concepts and context
    """
    
    # Clinical section headers (comprehensive)
    SECTION_PATTERNS = [
        # Main clinical areas
        r'^(?:##?\s*)?(?:1\.\d+\s*)?definition[s]?(?:\s+of\s+\w+)?',
        r'^(?:##?\s*)?(?:1\.\d+\s*)?introduction',
        r'^(?:##?\s*)?(?:2\.\d+\s*)?epidemiology',
        r'^(?:##?\s*)?(?:3\.\d+\s*)?etiology|aetiology',
        r'^(?:##?\s*)?(?:4\.\d+\s*)?risk\s+factors?',
        r'^(?:##?\s*)?(?:5\.\d+\s*)?pathophysiology',
        r'^(?:##?\s*)?(?:6\.\d+\s*)?clinical\s+presentation',
        r'^(?:##?\s*)?(?:7\.\d+\s*)?signs?\s+and\s+symptoms?',
        r'^(?:##?\s*)?(?:8\.\d+\s*)?diagnosis',
        r'^(?:##?\s*)?(?:9\.\d+\s*)?differential\s+diagnosis',
        r'^(?:##?\s*)?(?:10\.\d+\s*)?prevention',
        r'^(?:##?\s*)?(?:11\.\d+\s*)?management',
        r'^(?:##?\s*)?(?:12\.\d+\s*)?treatment',
        r'^(?:##?\s*)?(?:13\.\d+\s*)?intervention[s]?',
        r'^(?:##?\s*)?(?:14\.\d+\s*)?medication[s]?',
        r'^(?:##?\s*)?(?:15\.\d+\s*)?surgical\s+management',
        r'^(?:##?\s*)?(?:16\.\d+\s*)?emergency\s+management',
        r'^(?:##?\s*)?(?:17\.\d+\s*)?referral',
        r'^(?:##?\s*)?(?:18\.\d+\s*)?complications?',
        r'^(?:##?\s*)?(?:19\.\d+\s*)?prognosis',
        r'^(?:##?\s*)?(?:20\.\d+\s*)?monitoring',
        r'^(?:##?\s*)?(?:21\.\d+\s*)?follow[- ]up',
        r'^(?:##?\s*)?(?:22\.\d+\s*)?contraindications?',
        r'^(?:##?\s*)?(?:23\.\d+\s*)?precautions?',
        r'^(?:##?\s*)?(?:24\.\d+\s*)?algorithm[s]?',
        r'^(?:##?\s*)?(?:25\.\d+\s*)?protocol[s]?',
    ]
    
    # Clinical context keywords
    CLINICAL_CONTEXTS = {
        'definition': ['defined as', 'definition', 'refers to', 'is when', 'described as'],
        'epidemiology': ['incidence', 'prevalence', 'mortality', 'morbidity', 'statistics', 'data show'],
        'risk_factors': ['risk factor', 'predisposing', 'increases risk', 'at risk', 'associated with'],
        'prevention': ['prevent', 'prevention', 'prophylaxis', 'prophylactic', 'reduce risk', 'oxytocin', 'active management'],
        'diagnosis': ['diagnos', 'assess', 'evaluat', 'identif', 'clinical finding', 'present with'],
        'signs_symptoms': ['symptom', 'sign', 'present', 'manifest', 'feature', 'clinical picture'],
        'management': ['manage', 'treat', 'intervention', 'approach', 'steps', 'procedure'],
        'medication': ['drug', 'medication', 'dose', 'dosage', 'mg', 'administer', 'prescribe'],
        'emergency': ['emergency', 'urgent', 'immediate', 'critical', 'life-threatening', 'shock', 'resuscitation'],
        'referral': ['refer', 'transfer', 'escalate', 'specialist', 'tertiary', 'higher level'],
        'contraindication': ['contraindic', 'should not', 'avoid', 'do not', 'forbidden', 'prohibited'],
        'monitoring': ['monitor', 'observe', 'vital sign', 'surveillance', 'track', 'measure'],
    }
    
    # PPH severity indicators
    SEVERITY_KEYWORDS = {
        'mild': ['minor', 'mild', '500-1000', 'less than 1000', 'slight', 'minimal'],
        'moderate': ['moderate', '1000-1500', 'moderate blood loss'],
        'severe': ['severe', 'major', 'massive', '>1500', 'more than 1500', 'life-threatening', 'shock'],
    }
    
    def __init__(self, min_tokens: int = 300, max_tokens: int = 600, overlap_tokens: int = 50):
        """
        Initialize clinical chunker
        
        Args:
            min_tokens: Minimum tokens per chunk (default: 300)
            max_tokens: Maximum tokens per chunk (default: 600)
            overlap_tokens: Overlap between chunks (default: 50)
        """
        self.min_tokens = min_tokens
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
        
        # Compile section patterns once
        self.section_regex = [re.compile(pattern, re.IGNORECASE | re.MULTILINE) for pattern in self.SECTION_PATTERNS]
    
    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count (rough approximation: 1 token ≈ 4 characters)
        More accurate: ~0.75 words = 1 token for English medical text
        """
        words = len(text.split())
        return int(words / 0.75)  # Conservative estimate
    
    def identify_sections(self, text: str) -> List[Tuple[int, str, str]]:
        """
        Identify clinical sections in text
        
        Returns:
            List of (start_pos, end_pos, section_title)
        """
        sections = []
        
        # Find all section headers
        lines = text.split('\n')
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            
            # Check against section patterns
            for pattern in self.section_regex:
                if pattern.match(line_stripped):
                    # Calculate character position
                    start_pos = sum(len(lines[j]) + 1 for j in range(i))  # +1 for newline
                    sections.append((start_pos, line_stripped))
                    break
        
        # Add end positions
        sections_with_end = []
        for i, (start, title) in enumerate(sections):
            if i + 1 < len(sections):
                end = sections[i + 1][0]
            else:
                end = len(text)
            sections_with_end.append((start, end, title))
        
        return sections_with_end
    
    def extract_clinical_context(self, text: str) -> List[str]:
        """Extract clinical context keywords from text"""
        text_lower = text.lower()
        contexts = []
        
        for context, keywords in self.CLINICAL_CONTEXTS.items():
            if any(keyword in text_lower for keyword in keywords):
                contexts.append(context)
        
        return contexts
    
    def determine_pph_severity(self, text: str) -> Optional[str]:
        """Determine PPH severity level from text"""
        text_lower = text.lower()
        
        # Check for explicit severity mentions
        for severity, keywords in self.SEVERITY_KEYWORDS.items():
            if any(keyword in text_lower for keyword in keywords):
                return severity
        
        # Check for blood loss ranges
        if '500' in text and '1000' in text:
            return 'mild'
        elif '1000' in text and '1500' in text:
            return 'moderate'
        elif '1500' in text or '2000' in text:
            return 'severe'
        
        return None  # 'any' - applies to all severities
    
    def contains_clinical_elements(self, text: str) -> Tuple[bool, bool, bool]:
        """
        Check if text contains critical clinical elements
        
        Returns:
            (contains_dosage, contains_protocol, contains_contraindication)
        """
        text_lower = text.lower()
        
        # Dosage indicators
        dosage_patterns = [r'\d+\s*(?:mg|g|ml|units?|iu)', r'dose', r'dosage', r'administer']
        contains_dosage = any(re.search(pattern, text_lower) for pattern in dosage_patterns)
        
        # Protocol indicators
        protocol_patterns = [r'step\s+\d+', r'algorithm', r'protocol', r'procedure', r'first.*then', r'if.*then']
        contains_protocol = any(re.search(pattern, text_lower) for pattern in protocol_patterns)
        
        # Contraindication indicators
        contraindication_patterns = [r'contraindic', r'should not', r'do not', r'avoid', r'caution']
        contains_contraindication = any(re.search(pattern, text_lower) for pattern in contraindication_patterns)
        
        return contains_dosage, contains_protocol, contains_contraindication
    
    def chunk_section(self, text: str, section_title: Optional[str], start_index: int) -> List[ClinicalChunk]:
        """
        Chunk a section while preserving clinical concepts
        
        Args:
            text: Section text
            section_title: Section header
            start_index: Starting chunk index
            
        Returns:
            List of ClinicalChunk objects
        """
        chunks = []
        
        # If section is small enough, keep as single chunk
        token_count = self.estimate_tokens(text)
        if token_count <= self.max_tokens:
            clinical_context = self.extract_clinical_context(text)
            pph_severity = self.determine_pph_severity(text)
            dosage, protocol, contraindication = self.contains_clinical_elements(text)
            
            chunks.append(ClinicalChunk(
                text=text.strip(),
                chunk_index=start_index,
                section_title=section_title,
                clinical_context=clinical_context,
                pph_severity=pph_severity,
                contains_dosage=dosage,
                contains_protocol=protocol,
                contains_contraindication=contraindication,
                token_count=token_count,
                character_count=len(text),
            ))
            return chunks
        
        # Split into paragraphs, then group into optimal chunks
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        
        current_chunk_text = ""
        current_tokens = 0
        chunk_idx = start_index
        
        for para in paragraphs:
            para_tokens = self.estimate_tokens(para)
            
            # If adding this paragraph exceeds max, save current chunk
            if current_tokens > 0 and current_tokens + para_tokens > self.max_tokens:
                # Save current chunk
                clinical_context = self.extract_clinical_context(current_chunk_text)
                pph_severity = self.determine_pph_severity(current_chunk_text)
                dosage, protocol, contraindication = self.contains_clinical_elements(current_chunk_text)
                
                chunks.append(ClinicalChunk(
                    text=current_chunk_text.strip(),
                    chunk_index=chunk_idx,
                    section_title=section_title,
                    clinical_context=clinical_context,
                    pph_severity=pph_severity,
                    contains_dosage=dosage,
                    contains_protocol=protocol,
                    contains_contraindication=contraindication,
                    token_count=current_tokens,
                    character_count=len(current_chunk_text),
                ))
                
                # Start new chunk with overlap
                if self.overlap_tokens > 0:
                    # Take last sentences for overlap
                    sentences = current_chunk_text.split('. ')
                    overlap_text = '. '.join(sentences[-2:]) if len(sentences) > 1 else ""
                    current_chunk_text = overlap_text + "\n\n" + para if overlap_text else para
                    current_tokens = self.estimate_tokens(current_chunk_text)
                else:
                    current_chunk_text = para
                    current_tokens = para_tokens
                
                chunk_idx += 1
            else:
                # Add paragraph to current chunk
                if current_chunk_text:
                    current_chunk_text += "\n\n" + para
                else:
                    current_chunk_text = para
                current_tokens += para_tokens
        
        # Save final chunk
        if current_chunk_text.strip():
            clinical_context = self.extract_clinical_context(current_chunk_text)
            pph_severity = self.determine_pph_severity(current_chunk_text)
            dosage, protocol, contraindication = self.contains_clinical_elements(current_chunk_text)
            
            chunks.append(ClinicalChunk(
                text=current_chunk_text.strip(),
                chunk_index=chunk_idx,
                section_title=section_title,
                clinical_context=clinical_context,
                pph_severity=pph_severity,
                contains_dosage=dosage,
                contains_protocol=protocol,
                contains_contraindication=contraindication,
                token_count=current_tokens,
                character_count=len(current_chunk_text),
            ))
        
        return chunks
    
    def chunk_document(self, text: str, document_name: str) -> List[ClinicalChunk]:
        """
        Chunk entire clinical document with section awareness
        
        Args:
            text: Full document text
            document_name: Document filename for logging
            
        Returns:
            List of ClinicalChunk objects
        """
        logger.info(f"Chunking document: {document_name}")
        logger.info(f"Document length: {len(text)} chars, ~{self.estimate_tokens(text)} tokens")
        
        # Identify sections
        sections = self.identify_sections(text)
        
        if not sections:
            # No sections found, treat as single section
            logger.info("No clear sections found, chunking as single document")
            sections = [(0, len(text), "General")]
        else:
            logger.info(f"Found {len(sections)} sections")
        
        all_chunks = []
        chunk_index = 0
        
        for start, end, section_title in sections:
            section_text = text[start:end].strip()
            
            if not section_text:
                continue
            
            logger.debug(f"Processing section: {section_title} ({len(section_text)} chars)")
            
            section_chunks = self.chunk_section(section_text, section_title, chunk_index)
            all_chunks.extend(section_chunks)
            chunk_index += len(section_chunks)
            
            logger.debug(f"  → Generated {len(section_chunks)} chunks")
        
        logger.info(f"✓ Created {len(all_chunks)} total chunks")
        
        # Log statistics
        token_counts = [chunk.token_count for chunk in all_chunks]
        if token_counts:
            logger.info(f"  Token range: {min(token_counts)}-{max(token_counts)} tokens per chunk")
            logger.info(f"  Average: {sum(token_counts) // len(token_counts)} tokens per chunk")
        
        return all_chunks


def test_chunker():
    """Test clinical chunker with sample text"""
    sample_text = """
    Definition of Postpartum Hemorrhage
    
    Postpartum haemorrhage (PPH) is defined as blood loss of 500 ml or more from the female genital tract after childbirth. 
    It is classified as primary (within 24 hours) or secondary (after 24 hours).
    
    Risk Factors
    
    Major risk factors include:
    - Previous PPH
    - Multiple pregnancy
    - Grand multiparity
    - Prolonged labour
    
    Prevention
    
    Active management of third stage of labour is recommended:
    1. Administer oxytocin 10 IU intramuscularly within one minute of birth
    2. Controlled cord traction
    3. Uterine massage after delivery of placenta
    
    Management of Severe PPH
    
    In severe PPH (>1500 ml blood loss):
    1. Call for help immediately
    2. Assess airway, breathing, circulation
    3. Establish IV access with two large-bore cannulae
    4. Initiate fluid resuscitation
    5. Administer uterotonics: oxytocin 40 IU in 1L normal saline
    
    Contraindications to oxytocin include known hypersensitivity.
    """
    
    chunker = ClinicalChunker(min_tokens=100, max_tokens=300)
    chunks = chunker.chunk_document(sample_text, "test_document.txt")
    
    print(f"\nGenerated {len(chunks)} chunks:\n")
    for i, chunk in enumerate(chunks, 1):
        print(f"Chunk {i}:")
        print(f"  Section: {chunk.section_title}")
        print(f"  Tokens: {chunk.token_count}")
        print(f"  Clinical context: {', '.join(chunk.clinical_context)}")
        print(f"  Severity: {chunk.pph_severity or 'any'}")
        print(f"  Contains dosage: {chunk.contains_dosage}")
        print(f"  Contains protocol: {chunk.contains_protocol}")
        print(f"  Contains contraindication: {chunk.contains_contraindication}")
        print(f"  Preview: {chunk.text[:100]}...")
        print()


if __name__ == "__main__":
    test_chunker()

