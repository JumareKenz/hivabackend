"""
Semantic-aware chunking module for Zamfara RAG system.

Implements intelligent text chunking that preserves:
- Section headings and structure
- Document context
- Semantic coherence
- Metadata for each chunk
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from typing import Generator, Optional, List
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class DocumentChunk:
    """
    Represents a single chunk of a document with full metadata.
    
    This is the core unit stored in the vector database.
    """
    # Content
    text: str
    
    # Chunk identification
    chunk_id: str  # Unique identifier
    chunk_index: int  # Position in source document
    
    # Source document metadata
    document_title: str
    document_type: str  # policy, guideline, sop, faq
    file_path: str
    file_name: str
    
    # Structural metadata
    section_heading: str = ""
    subsection_heading: str = ""
    
    # Organizational metadata
    department: str = "unknown"
    
    # Temporal metadata
    last_updated: Optional[str] = None
    
    # Chunking metadata
    char_count: int = 0
    word_count: int = 0
    token_estimate: int = 0
    overlap_start: bool = False  # Has overlap from previous chunk
    overlap_end: bool = False    # Has overlap into next chunk
    
    # Context preservation
    preceding_context: str = ""  # Brief context from previous chunk
    
    def __post_init__(self):
        """Calculate counts if not set."""
        if self.char_count == 0:
            self.char_count = len(self.text)
        if self.word_count == 0:
            self.word_count = len(self.text.split())
        if self.token_estimate == 0:
            # Rough estimate: 4 characters per token
            self.token_estimate = self.char_count // 4
    
    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "chunk_id": self.chunk_id,
            "chunk_index": self.chunk_index,
            "document_title": self.document_title,
            "document_type": self.document_type,
            "file_path": self.file_path,
            "file_name": self.file_name,
            "section_heading": self.section_heading,
            "subsection_heading": self.subsection_heading,
            "department": self.department,
            "last_updated": self.last_updated,
            "char_count": self.char_count,
            "word_count": self.word_count,
            "token_estimate": self.token_estimate,
        }


@dataclass
class Section:
    """Represents a document section with heading."""
    heading: str
    content: str
    level: int = 1  # Heading level (1 = main, 2 = sub, etc.)
    subsections: List["Section"] = field(default_factory=list)


class SemanticChunker:
    """
    Chunks documents with semantic awareness.
    
    Strategy:
    1. Identify document structure (headings, sections)
    2. Split at natural boundaries (paragraphs, sections)
    3. Maintain chunk size within 300-700 token range
    4. Apply 10-20% overlap for context continuity
    5. Preserve section headings in each chunk
    """
    
    # Patterns for detecting headings
    HEADING_PATTERNS = [
        # Numbered headings: "1. Introduction", "1.1 Overview"
        (r"^(\d+(?:\.\d+)*)\s*[.:\-)]?\s*(.+)$", 1),
        # Letter headings: "A. Section", "a) Point"
        (r"^([A-Za-z])\s*[.:\-)]\s*(.+)$", 2),
        # Roman numerals: "I. First", "ii. Second"
        (r"^([IVXivx]+)\s*[.:\-)]\s*(.+)$", 2),
        # ALL CAPS headings
        (r"^([A-Z][A-Z\s]{3,})$", 1),
        # Underlined/emphasized (followed by newline)
        (r"^(.+)\n[=\-]{3,}$", 1),
    ]
    
    # Patterns for section breaks
    SECTION_BREAK_PATTERNS = [
        r"\n{3,}",  # Multiple blank lines
        r"\n\s*[_\-=]{5,}\s*\n",  # Horizontal rules
        r"\n\s*\*\s*\*\s*\*\s*\n",  # Asterisk separators
    ]
    
    def __init__(
        self,
        chunk_size_chars: int = 1500,  # ~375 tokens
        overlap_percent: float = 0.15,  # 15% overlap
        min_chunk_size: int = 200,
        max_chunk_size: int = 3000,
        preserve_headings: bool = True,
    ):
        """
        Initialize the semantic chunker.
        
        Args:
            chunk_size_chars: Target chunk size in characters
            overlap_percent: Overlap percentage (0.1 to 0.2)
            min_chunk_size: Minimum chunk size
            max_chunk_size: Maximum chunk size
            preserve_headings: Include section headings in chunks
        """
        self.chunk_size = chunk_size_chars
        self.overlap = int(chunk_size_chars * overlap_percent)
        self.min_size = min_chunk_size
        self.max_size = max_chunk_size
        self.preserve_headings = preserve_headings
        
        # Compile patterns
        self._heading_patterns = [
            (re.compile(p, re.MULTILINE), level)
            for p, level in self.HEADING_PATTERNS
        ]
        self._section_break_pattern = re.compile(
            "|".join(self.SECTION_BREAK_PATTERNS)
        )
    
    def chunk_document(
        self,
        text: str,
        document_title: str,
        document_type: str,
        file_path: str,
        file_name: str,
        department: str = "unknown",
        last_updated: Optional[str] = None,
    ) -> Generator[DocumentChunk, None, None]:
        """
        Chunk a document with semantic awareness.
        
        Args:
            text: Document text to chunk
            document_title: Title of the source document
            document_type: Type (policy, guideline, etc.)
            file_path: Path to source file
            file_name: Name of source file
            department: Department (if known)
            last_updated: Last modification date
            
        Yields:
            DocumentChunk objects
        """
        if not text or not text.strip():
            logger.warning(f"Empty text provided for chunking: {file_name}")
            return
        
        # Step 1: Parse document structure
        sections = self._parse_structure(text)
        
        # Step 2: Chunk each section
        chunk_index = 0
        previous_chunk_tail = ""
        
        for section in sections:
            section_chunks = self._chunk_section(
                section=section,
                document_title=document_title,
                document_type=document_type,
                file_path=file_path,
                file_name=file_name,
                department=department,
                last_updated=last_updated,
                start_index=chunk_index,
                preceding_context=previous_chunk_tail,
            )
            
            for chunk in section_chunks:
                yield chunk
                chunk_index = chunk.chunk_index + 1
                # Keep tail for overlap
                if len(chunk.text) > self.overlap:
                    previous_chunk_tail = chunk.text[-self.overlap:]
                else:
                    previous_chunk_tail = chunk.text
    
    def _parse_structure(self, text: str) -> List[Section]:
        """
        Parse document into sections based on headings and structure.
        
        Returns:
            List of Section objects
        """
        sections = []
        
        # Split by major section breaks first
        major_parts = self._section_break_pattern.split(text)
        
        for part in major_parts:
            part = part.strip()
            if not part:
                continue
            
            # Try to identify heading
            heading, content, level = self._extract_heading(part)
            
            if heading:
                sections.append(Section(
                    heading=heading,
                    content=content,
                    level=level
                ))
            else:
                # No clear heading, treat as content section
                sections.append(Section(
                    heading="",
                    content=part,
                    level=0
                ))
        
        # If no sections found, treat entire text as one section
        if not sections:
            sections.append(Section(
                heading="",
                content=text,
                level=0
            ))
        
        return sections
    
    def _extract_heading(self, text: str) -> tuple[str, str, int]:
        """
        Extract heading from text block.
        
        Returns:
            Tuple of (heading, remaining_content, heading_level)
        """
        lines = text.split("\n", 1)
        first_line = lines[0].strip()
        rest = lines[1] if len(lines) > 1 else ""
        
        # Check against heading patterns
        for pattern, level in self._heading_patterns:
            match = pattern.match(first_line)
            if match:
                # Extract heading text
                if match.lastindex and match.lastindex >= 2:
                    heading = match.group(2).strip()
                else:
                    heading = first_line
                return heading, rest.strip(), level
        
        # Check if first line looks like a title (short, no period)
        if len(first_line) < 100 and not first_line.endswith("."):
            # Could be a heading
            if first_line.isupper() or first_line.istitle():
                return first_line, rest.strip(), 1
        
        return "", text, 0
    
    def _chunk_section(
        self,
        section: Section,
        document_title: str,
        document_type: str,
        file_path: str,
        file_name: str,
        department: str,
        last_updated: Optional[str],
        start_index: int,
        preceding_context: str,
    ) -> Generator[DocumentChunk, None, None]:
        """
        Chunk a single section.
        
        Yields:
            DocumentChunk objects for this section
        """
        content = section.content
        heading = section.heading
        
        # If section is small enough, yield as single chunk
        if len(content) <= self.chunk_size:
            chunk_text = content
            if self.preserve_headings and heading:
                chunk_text = f"[Section: {heading}]\n\n{content}"
            
            yield DocumentChunk(
                text=chunk_text,
                chunk_id=f"{file_name}_{start_index}",
                chunk_index=start_index,
                document_title=document_title,
                document_type=document_type,
                file_path=file_path,
                file_name=file_name,
                section_heading=heading,
                department=department,
                last_updated=last_updated,
                preceding_context=preceding_context[:200] if preceding_context else "",
            )
            return
        
        # Split into paragraphs for natural boundaries
        paragraphs = self._split_paragraphs(content)
        
        # Build chunks from paragraphs
        current_chunk = []
        current_size = 0
        chunk_index = start_index
        prev_context = preceding_context
        
        for para in paragraphs:
            para_size = len(para)
            
            # If single paragraph exceeds max size, split it
            if para_size > self.max_size:
                # Yield current chunk first
                if current_chunk:
                    chunk_text = "\n\n".join(current_chunk)
                    if self.preserve_headings and heading:
                        chunk_text = f"[Section: {heading}]\n\n{chunk_text}"
                    
                    yield DocumentChunk(
                        text=chunk_text,
                        chunk_id=f"{file_name}_{chunk_index}",
                        chunk_index=chunk_index,
                        document_title=document_title,
                        document_type=document_type,
                        file_path=file_path,
                        file_name=file_name,
                        section_heading=heading,
                        department=department,
                        last_updated=last_updated,
                        preceding_context=prev_context[:200] if prev_context else "",
                        overlap_end=True,
                    )
                    prev_context = chunk_text[-self.overlap:] if len(chunk_text) > self.overlap else chunk_text
                    chunk_index += 1
                    current_chunk = []
                    current_size = 0
                
                # Split large paragraph
                for sub_chunk in self._split_large_text(para):
                    chunk_text = sub_chunk
                    if self.preserve_headings and heading:
                        chunk_text = f"[Section: {heading}]\n\n{sub_chunk}"
                    
                    yield DocumentChunk(
                        text=chunk_text,
                        chunk_id=f"{file_name}_{chunk_index}",
                        chunk_index=chunk_index,
                        document_title=document_title,
                        document_type=document_type,
                        file_path=file_path,
                        file_name=file_name,
                        section_heading=heading,
                        department=department,
                        last_updated=last_updated,
                        preceding_context=prev_context[:200] if prev_context else "",
                        overlap_start=bool(prev_context),
                        overlap_end=True,
                    )
                    prev_context = sub_chunk[-self.overlap:] if len(sub_chunk) > self.overlap else sub_chunk
                    chunk_index += 1
                continue
            
            # Check if adding paragraph exceeds chunk size
            if current_size + para_size + 2 > self.chunk_size and current_chunk:
                # Yield current chunk
                chunk_text = "\n\n".join(current_chunk)
                if self.preserve_headings and heading:
                    chunk_text = f"[Section: {heading}]\n\n{chunk_text}"
                
                yield DocumentChunk(
                    text=chunk_text,
                    chunk_id=f"{file_name}_{chunk_index}",
                    chunk_index=chunk_index,
                    document_title=document_title,
                    document_type=document_type,
                    file_path=file_path,
                    file_name=file_name,
                    section_heading=heading,
                    department=department,
                    last_updated=last_updated,
                    preceding_context=prev_context[:200] if prev_context else "",
                    overlap_end=True,
                )
                
                # Prepare for next chunk with overlap
                prev_context = chunk_text[-self.overlap:] if len(chunk_text) > self.overlap else chunk_text
                chunk_index += 1
                
                # Start new chunk - include overlap text
                current_chunk = [para]
                current_size = para_size
            else:
                current_chunk.append(para)
                current_size += para_size + 2
        
        # Yield final chunk
        if current_chunk:
            chunk_text = "\n\n".join(current_chunk)
            if self.preserve_headings and heading:
                chunk_text = f"[Section: {heading}]\n\n{chunk_text}"
            
            yield DocumentChunk(
                text=chunk_text,
                chunk_id=f"{file_name}_{chunk_index}",
                chunk_index=chunk_index,
                document_title=document_title,
                document_type=document_type,
                file_path=file_path,
                file_name=file_name,
                section_heading=heading,
                department=department,
                last_updated=last_updated,
                preceding_context=prev_context[:200] if prev_context else "",
                overlap_start=bool(prev_context),
            )
    
    def _split_paragraphs(self, text: str) -> List[str]:
        """Split text into paragraphs."""
        # Split on double newlines
        paragraphs = re.split(r"\n\s*\n", text)
        # Filter empty and normalize
        return [p.strip() for p in paragraphs if p.strip()]
    
    def _split_large_text(self, text: str) -> Generator[str, None, None]:
        """Split text larger than max_size by sentences."""
        # Split by sentences
        sentences = re.split(r"([.!?]+\s+)", text)
        
        # Recombine sentences with punctuation
        combined = []
        for i in range(0, len(sentences) - 1, 2):
            if i + 1 < len(sentences):
                combined.append(sentences[i] + sentences[i + 1])
            else:
                combined.append(sentences[i])
        
        current = []
        current_size = 0
        
        for sentence in combined:
            sent_size = len(sentence)
            
            if current_size + sent_size > self.chunk_size and current:
                yield " ".join(current)
                # Keep some overlap
                overlap_text = " ".join(current)[-self.overlap:]
                current = [overlap_text, sentence] if overlap_text else [sentence]
                current_size = len(overlap_text) + sent_size if overlap_text else sent_size
            else:
                current.append(sentence)
                current_size += sent_size
        
        if current:
            yield " ".join(current)




