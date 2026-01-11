"""
Metadata extraction and document typing module for Zamfara RAG system.

Extracts and infers rich metadata from documents including:
- Document type classification
- Department/topic inference
- Section heading extraction
- Temporal metadata
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class DocumentMetadata:
    """Complete metadata for a document."""
    
    # Core identification
    document_title: str
    file_path: str
    file_name: str
    
    # Classification
    document_type: str  # policy, guideline, sop, faq, gazette, opg
    document_type_confidence: float  # 0.0 to 1.0
    
    # Organizational
    department: str
    department_confidence: float
    topics: List[str]
    
    # Temporal
    last_updated: Optional[str]
    effective_date: Optional[str]
    
    # Content summary
    word_count: int
    section_count: int
    section_headings: List[str]
    
    # Source
    extraction_method: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "document_title": self.document_title,
            "file_path": self.file_path,
            "file_name": self.file_name,
            "document_type": self.document_type,
            "document_type_confidence": self.document_type_confidence,
            "department": self.department,
            "department_confidence": self.department_confidence,
            "topics": self.topics,
            "last_updated": self.last_updated,
            "effective_date": self.effective_date,
            "word_count": self.word_count,
            "section_count": self.section_count,
            "section_headings": self.section_headings,
            "extraction_method": self.extraction_method,
        }


class MetadataExtractor:
    """
    Extracts and infers rich metadata from documents.
    
    Features:
    - Document type classification (policy, guideline, SOP, FAQ, etc.)
    - Department inference from content and filename
    - Section heading extraction
    - Date/version extraction
    """
    
    # Document type keywords with weights
    DOCUMENT_TYPE_INDICATORS = {
        "policy": {
            "keywords": ["policy", "regulation", "act", "law", "statute", "decree", 
                        "directive", "ordinance", "provision", "mandate", "rule"],
            "filename_patterns": [r"policy", r"act\d*", r"regulation", r"law"],
            "weight": 1.0
        },
        "guideline": {
            "keywords": ["guideline", "guidance", "guide", "manual", "handbook",
                        "instruction", "advisory", "recommendation"],
            "filename_patterns": [r"guide", r"manual", r"handbook"],
            "weight": 0.9
        },
        "sop": {
            "keywords": ["procedure", "sop", "standard operating", "process",
                        "workflow", "protocol", "methodology", "step-by-step"],
            "filename_patterns": [r"sop", r"procedure", r"process"],
            "weight": 0.9
        },
        "faq": {
            "keywords": ["faq", "frequently asked", "questions", "answers", "q&a",
                        "common questions", "help"],
            "filename_patterns": [r"faq", r"qa", r"questions"],
            "weight": 0.95
        },
        "gazette": {
            "keywords": ["gazette", "official", "government", "publication",
                        "notice", "announcement", "proclamation"],
            "filename_patterns": [r"gazette", r"official", r"notice"],
            "weight": 0.85
        },
        "opg": {
            "keywords": ["operational", "operations", "opg", "administrative",
                        "implementation", "execution", "operational guide"],
            "filename_patterns": [r"opg", r"operational", r"operations"],
            "weight": 0.85
        },
    }
    
    # Department/topic keywords
    DEPARTMENT_INDICATORS = {
        "health": {
            "keywords": ["health", "medical", "hospital", "clinic", "disease",
                        "treatment", "patient", "doctor", "nurse", "healthcare",
                        "pharmaceutical", "medicine", "therapy", "diagnosis"],
            "weight": 1.0
        },
        "finance": {
            "keywords": ["finance", "budget", "revenue", "expenditure", "fiscal",
                        "tax", "accounting", "treasury", "financial", "payment",
                        "funding", "allocation", "economic"],
            "weight": 1.0
        },
        "education": {
            "keywords": ["education", "school", "student", "teacher", "curriculum",
                        "learning", "academic", "university", "college", "examination",
                        "scholarship", "training"],
            "weight": 1.0
        },
        "agriculture": {
            "keywords": ["agriculture", "farming", "crop", "livestock", "rural",
                        "farmer", "harvest", "irrigation", "fertilizer", "seed",
                        "pastoral", "veterinary"],
            "weight": 1.0
        },
        "infrastructure": {
            "keywords": ["infrastructure", "road", "building", "construction",
                        "water", "electricity", "power", "housing", "transport",
                        "bridge", "drainage", "sanitation"],
            "weight": 1.0
        },
        "administration": {
            "keywords": ["administration", "civil service", "government", "public",
                        "ministry", "bureau", "office", "secretary", "commissioner",
                        "governor", "council", "committee"],
            "weight": 0.8
        },
        "legal": {
            "keywords": ["legal", "court", "justice", "law", "judicial", "attorney",
                        "prosecution", "judge", "magistrate", "litigation", "verdict"],
            "weight": 1.0
        },
        "security": {
            "keywords": ["security", "police", "safety", "emergency", "defense",
                        "protection", "enforcement", "crime", "patrol"],
            "weight": 1.0
        },
        "social_welfare": {
            "keywords": ["welfare", "social", "pension", "disability", "orphan",
                        "elderly", "vulnerable", "community", "women", "youth"],
            "weight": 0.9
        },
    }
    
    # Date patterns
    DATE_PATTERNS = [
        # Full dates
        (r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})", "%d-%m-%Y"),
        (r"(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})", "%Y-%m-%d"),
        # Month names
        (r"(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)[,\s]+(\d{4})", None),
        (r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})[,\s]+(\d{4})", None),
        # Year only
        (r"\b(20[0-2]\d)\b", "%Y"),
    ]
    
    # Section heading patterns
    SECTION_PATTERNS = [
        r"^(\d+(?:\.\d+)*)\s*[.:\-)]?\s*([A-Z][^.!?\n]{5,})$",  # "1. Introduction"
        r"^([A-Z][A-Z\s]{5,})$",  # "INTRODUCTION"
        r"^([IVXLC]+)\s*[.:\-)]\s*([A-Z][^.!?\n]{5,})$",  # "I. Introduction"
        r"^([a-z])\)\s*([A-Z][^.!?\n]{5,})$",  # "a) Point"
    ]
    
    def __init__(self):
        """Initialize the metadata extractor."""
        # Compile patterns
        self._section_patterns = [
            re.compile(p, re.MULTILINE) for p in self.SECTION_PATTERNS
        ]
    
    def extract(
        self,
        text: str,
        file_path: str,
        file_name: str,
        last_modified: Optional[datetime] = None,
        extraction_method: str = "standard"
    ) -> DocumentMetadata:
        """
        Extract metadata from document.
        
        Args:
            text: Document text content
            file_path: Path to source file
            file_name: Name of source file
            last_modified: File modification date
            extraction_method: Method used to extract text
            
        Returns:
            DocumentMetadata object
        """
        # Extract document title from filename
        document_title = self._extract_title(file_name, text)
        
        # Classify document type
        doc_type, doc_type_conf = self._classify_document_type(text, file_name)
        
        # Infer department
        department, dept_conf, topics = self._infer_department(text, file_name)
        
        # Extract dates
        effective_date = self._extract_date(text, "effective")
        
        # Extract section headings
        sections = self._extract_sections(text)
        
        # Calculate word count
        word_count = len(text.split())
        
        # Format last_updated
        last_updated_str = None
        if last_modified:
            last_updated_str = last_modified.strftime("%Y-%m-%d")
        
        return DocumentMetadata(
            document_title=document_title,
            file_path=file_path,
            file_name=file_name,
            document_type=doc_type,
            document_type_confidence=doc_type_conf,
            department=department,
            department_confidence=dept_conf,
            topics=topics,
            last_updated=last_updated_str,
            effective_date=effective_date,
            word_count=word_count,
            section_count=len(sections),
            section_headings=sections[:10],  # Limit to top 10
            extraction_method=extraction_method,
        )
    
    def _extract_title(self, file_name: str, text: str) -> str:
        """Extract document title from filename or content."""
        # Clean filename
        title = file_name.rsplit(".", 1)[0]  # Remove extension
        title = title.replace("_", " ").replace("-", " ")
        
        # Try to extract title from first line of document
        first_lines = text.strip().split("\n")[:3]
        for line in first_lines:
            line = line.strip()
            # Skip very short or very long lines
            if 10 < len(line) < 100:
                # Check if it looks like a title
                if line.isupper() or line.istitle():
                    if not line.endswith("."):
                        return line
        
        return title.title()
    
    def _classify_document_type(
        self,
        text: str,
        file_name: str
    ) -> tuple[str, float]:
        """
        Classify document type based on content and filename.
        
        Returns:
            Tuple of (document_type, confidence)
        """
        text_lower = text.lower()
        file_lower = file_name.lower()
        
        scores = {}
        
        for doc_type, indicators in self.DOCUMENT_TYPE_INDICATORS.items():
            score = 0.0
            
            # Check keywords in content
            for keyword in indicators["keywords"]:
                count = text_lower.count(keyword)
                if count > 0:
                    # Diminishing returns for multiple occurrences
                    score += min(count * 0.1, 0.5)
            
            # Check filename patterns
            for pattern in indicators["filename_patterns"]:
                if re.search(pattern, file_lower):
                    score += 0.5
            
            # Apply weight
            score *= indicators["weight"]
            
            scores[doc_type] = score
        
        if not scores or max(scores.values()) == 0:
            return "unknown", 0.0
        
        # Get best match
        best_type = max(scores, key=scores.get)
        best_score = scores[best_type]
        
        # Normalize confidence
        confidence = min(best_score / 2.0, 1.0)
        
        return best_type, confidence
    
    def _infer_department(
        self,
        text: str,
        file_name: str
    ) -> tuple[str, float, List[str]]:
        """
        Infer department and topics from content.
        
        Returns:
            Tuple of (department, confidence, topics)
        """
        text_lower = text.lower()
        file_lower = file_name.lower()
        
        scores = {}
        
        for dept, indicators in self.DEPARTMENT_INDICATORS.items():
            score = 0.0
            
            for keyword in indicators["keywords"]:
                count = text_lower.count(keyword)
                if count > 0:
                    score += min(count * 0.05, 0.3)
            
            # Check filename
            for keyword in indicators["keywords"][:3]:  # Top keywords
                if keyword in file_lower:
                    score += 0.3
            
            score *= indicators["weight"]
            scores[dept] = score
        
        if not scores or max(scores.values()) == 0:
            return "general", 0.3, []
        
        # Sort by score
        sorted_depts = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        # Best department
        best_dept, best_score = sorted_depts[0]
        
        # Get topics (departments with significant scores)
        topics = [
            dept for dept, score in sorted_depts[:3]
            if score > best_score * 0.5 and score > 0.1
        ]
        
        confidence = min(best_score / 1.5, 1.0)
        
        return best_dept, confidence, topics
    
    def _extract_date(self, text: str, date_type: str = "any") -> Optional[str]:
        """
        Extract date from document text.
        
        Args:
            text: Document text
            date_type: Type of date to look for ("effective", "updated", "any")
            
        Returns:
            Date string in YYYY-MM-DD format, or None
        """
        # Look for date keywords
        date_keywords = {
            "effective": ["effective date", "effective from", "commences on", "dated"],
            "updated": ["updated", "revised", "amended", "modified"],
            "any": ["date", "dated", "on the"]
        }
        
        keywords = date_keywords.get(date_type, date_keywords["any"])
        
        # Search near keywords
        for keyword in keywords:
            pattern = re.compile(
                rf"{keyword}[:\s]*(\d{{1,2}}[/\-]\d{{1,2}}[/\-]\d{{4}}|\d{{4}}[/\-]\d{{1,2}}[/\-]\d{{1,2}})",
                re.IGNORECASE
            )
            match = pattern.search(text)
            if match:
                date_str = match.group(1)
                try:
                    # Try to parse and normalize
                    for fmt in ["%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%Y-%m-%d"]:
                        try:
                            dt = datetime.strptime(date_str, fmt)
                            return dt.strftime("%Y-%m-%d")
                        except ValueError:
                            continue
                except Exception:
                    pass
        
        return None
    
    def _extract_sections(self, text: str) -> List[str]:
        """Extract section headings from document."""
        sections = []
        
        for pattern in self._section_patterns:
            matches = pattern.findall(text)
            for match in matches:
                if isinstance(match, tuple):
                    # Get the heading text (usually last group)
                    heading = match[-1] if match[-1] else match[0]
                else:
                    heading = match
                
                heading = heading.strip()
                if heading and len(heading) > 3 and heading not in sections:
                    sections.append(heading)
        
        return sections
    
    def update_chunk_metadata(
        self,
        chunk: Any,  # DocumentChunk
        document_metadata: DocumentMetadata
    ) -> None:
        """
        Update chunk with document-level metadata.
        
        Args:
            chunk: DocumentChunk to update
            document_metadata: Document-level metadata
        """
        chunk.document_type = document_metadata.document_type
        chunk.department = document_metadata.department
        chunk.last_updated = document_metadata.last_updated
        
        # If chunk doesn't have a section heading, use document title
        if not chunk.section_heading:
            chunk.section_heading = document_metadata.document_title




