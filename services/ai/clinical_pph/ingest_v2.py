"""
World-Class Clinical PPH Document Ingestion System (Version 2)

This upgraded ingestion system implements:
- Clinical-aware chunking (300-600 tokens, section-aligned)
- Rich clinical metadata extraction
- Authority hierarchy scoring
- Document quality validation
- Evidence traceability
- Safe refusal capability
"""

import sys
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import hashlib
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

from sentence_transformers import SentenceTransformer
from app.core.config import settings
from app.rag.utils import extract_text_from_pdf, extract_text_from_docx
from clinical_pph.store import get_or_create_collection, delete_collection
from clinical_pph.clinical_chunker import ClinicalChunker
from clinical_pph.audit_documents import DocumentAuditor

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
DOCS_DIR = BASE_DIR / "docs"


class ClinicalMetadataExtractor:
    """Extracts rich clinical metadata from documents"""
    
    # Authority hierarchy (higher = more authoritative)
    AUTHORITY_SCORES = {
        "WHO": 100,
        "FIGO": 90,
        "National": 80,
        "RCOG": 70,
        "RANZCOG": 70,
        "ACOG": 70,
        "SOGON": 65,
        "Regional": 60,
        "Unknown": 50,
    }
    
    @classmethod
    def extract_metadata(cls, text: str, filename: str, doc_path: Path) -> Dict[str, Any]:
        """
        Extract comprehensive clinical metadata
        
        Returns:
            Dict with:
                - guideline_name: str
                - issuing_body: str
                - publication_year: int
                - clinical_scope: List[str]
                - authority_score: int
                - document_type: str
                - document_path: str
                - is_superseded: bool
                - superseded_by: Optional[str]
        """
        # Use existing auditor for initial extraction
        auditor = DocumentAuditor(DOCS_DIR)
        base_metadata = auditor.extract_metadata(text, filename)
        
        # Enhance with additional fields
        guideline_name = cls._extract_guideline_name(text, filename)
        
        metadata = {
            "guideline_name": guideline_name,
            "issuing_body": base_metadata["source_organization"],
            "publication_year": base_metadata["publication_year"] or 2024,
            "clinical_scope": [s.split(" (")[0] for s in base_metadata["scope"]],  # Remove counts
            "authority_score": cls.AUTHORITY_SCORES.get(base_metadata["source_organization"], 50),
            "document_type": base_metadata["document_type"],
            "document_path": str(doc_path),
            "is_superseded": False,  # Manual flag
            "superseded_by": None,
            "version": base_metadata.get("version"),
            "word_count": base_metadata["word_count"],
            "character_count": base_metadata["character_count"],
        }
        
        return metadata
    
    @classmethod
    def _extract_guideline_name(cls, text: str, filename: str) -> str:
        """Extract or generate guideline name"""
        # Try to find title in first 2000 chars
        first_lines = text[:2000].split('\n')
        
        for line in first_lines[:10]:
            line = line.strip()
            if len(line) > 20 and len(line) < 150:
                # Likely a title
                if any(keyword in line.lower() for keyword in ['guideline', 'manual', 'protocol', 'policy']):
                    return line
        
        # Fallback to filename
        name = filename.replace('.pdf', '').replace('.docx', '').replace('_', ' ')
        return name


class ClinicalPPHIngestorV2:
    """
    World-class document ingestor with clinical safety features
    """
    
    def __init__(self):
        self.chunker = ClinicalChunker(min_tokens=300, max_tokens=600, overlap_tokens=50)
        self.metadata_extractor = ClinicalMetadataExtractor()
        self.embedder: Optional[SentenceTransformer] = None
    
    def get_embedder(self) -> SentenceTransformer:
        """Get or initialize embedding model"""
        if self.embedder is None:
            model_name = getattr(settings, "EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
            logger.info(f"Loading embedding model: {model_name}")
            self.embedder = SentenceTransformer(model_name)
        return self.embedder
    
    def _stable_id(self, *parts: str) -> str:
        """Generate stable document ID"""
        return hashlib.md5("::".join(str(p) for p in parts).encode("utf-8")).hexdigest()
    
    def _extract_text(self, file_path: Path) -> Optional[str]:
        """Extract text from document"""
        try:
            if file_path.suffix.lower() == ".pdf":
                text = extract_text_from_pdf(str(file_path))
            elif file_path.suffix.lower() == ".docx":
                text = extract_text_from_docx(str(file_path))
            elif file_path.suffix.lower() in [".txt", ".md"]:
                text = file_path.read_text(encoding="utf-8", errors="ignore")
            else:
                logger.warning(f"Unsupported file format: {file_path.suffix}")
                return None
            
            return text.strip() if text else None
        
        except Exception as e:
            logger.error(f"Error extracting text from {file_path}: {e}")
            return None
    
    def ingest_document(
        self,
        file_path: Path,
        collection: Any,
        embedder: SentenceTransformer
    ) -> Dict[str, Any]:
        """
        Ingest a single clinical document with full metadata
        
        Returns:
            Statistics about ingestion
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"Ingesting: {file_path.name}")
        logger.info(f"{'='*80}")
        
        # Extract text
        text = self._extract_text(file_path)
        if not text or len(text) < 100:
            logger.warning(f"Insufficient text extracted from {file_path.name}")
            return {"status": "skipped", "reason": "insufficient_text", "chunks_created": 0}
        
        logger.info(f"✓ Extracted {len(text)} characters")
        
        # Extract document-level metadata
        doc_metadata = self.metadata_extractor.extract_metadata(text, file_path.name, file_path)
        logger.info(f"✓ Guideline: {doc_metadata['guideline_name']}")
        logger.info(f"✓ Issuing body: {doc_metadata['issuing_body']} (authority score: {doc_metadata['authority_score']})")
        logger.info(f"✓ Year: {doc_metadata['publication_year']}")
        logger.info(f"✓ Scope: {', '.join(doc_metadata['clinical_scope'])}")
        
        # Chunk document with clinical awareness
        chunks = self.chunker.chunk_document(text, file_path.name)
        
        if not chunks:
            logger.warning("No chunks generated")
            return {"status": "error", "reason": "no_chunks", "chunks_created": 0}
        
        logger.info(f"✓ Generated {len(chunks)} clinical-aware chunks")
        
        # Prepare for ingestion
        docs: List[str] = []
        metadatas: List[Dict[str, Any]] = []
        ids: List[str] = []
        
        for chunk in chunks:
            # Combine document and chunk metadata
            chunk_metadata = {
                # Document-level metadata
                "kb_id": "clinical_pph",
                "guideline_name": doc_metadata["guideline_name"],
                "issuing_body": doc_metadata["issuing_body"],
                "publication_year": doc_metadata["publication_year"],
                "authority_score": doc_metadata["authority_score"],
                "document_type": doc_metadata["document_type"],
                "document_path": doc_metadata["document_path"],
                "file_name": file_path.name,
                "is_superseded": doc_metadata["is_superseded"],
                
                # Chunk-level metadata
                "chunk_index": chunk.chunk_index,
                "section_title": chunk.section_title or "Unknown",
                "clinical_context": ",".join(chunk.clinical_context) if chunk.clinical_context else "general",
                "pph_severity": chunk.pph_severity or "any",
                "contains_dosage": chunk.contains_dosage,
                "contains_protocol": chunk.contains_protocol,
                "contains_contraindication": chunk.contains_contraindication,
                "token_count": chunk.token_count,
                
                # Evidence traceability
                "ingestion_date": datetime.now().isoformat(),
                "chunking_version": "v2_clinical_aware",
            }
            
            # Generate stable ID
            doc_id = self._stable_id(
                "clinical_pph_v2",
                file_path.name,
                str(chunk.chunk_index)
            )
            
            docs.append(chunk.text)
            metadatas.append(chunk_metadata)
            ids.append(doc_id)
        
        # Generate embeddings
        logger.info(f"Generating embeddings for {len(docs)} chunks...")
        embeddings = embedder.encode(docs, show_progress_bar=True).tolist()
        
        # Store in vector database
        logger.info("Storing in vector database...")
        try:
            collection.upsert(
                documents=docs,
                embeddings=embeddings,
                metadatas=metadatas,
                ids=ids
            )
            logger.info("✓ Successfully stored all chunks")
        except Exception as e:
            logger.error(f"Error storing chunks: {e}")
            try:
                collection.add(
                    documents=docs,
                    embeddings=embeddings,
                    metadatas=metadatas,
                    ids=ids
                )
                logger.info("✓ Successfully added chunks (fallback)")
            except Exception as e2:
                logger.error(f"Failed to store chunks: {e2}")
                return {"status": "error", "reason": str(e2), "chunks_created": 0}
        
        # Log quality metrics
        logger.info(f"\n{'─'*80}")
        logger.info("QUALITY METRICS:")
        logger.info(f"  Total chunks: {len(chunks)}")
        logger.info(f"  Chunks with dosages: {sum(1 for c in chunks if c.contains_dosage)}")
        logger.info(f"  Chunks with protocols: {sum(1 for c in chunks if c.contains_protocol)}")
        logger.info(f"  Chunks with contraindications: {sum(1 for c in chunks if c.contains_contraindication)}")
        
        severity_counts = {}
        for chunk in chunks:
            severity = chunk.pph_severity or 'any'
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        logger.info(f"  Severity distribution: {severity_counts}")
        
        return {
            "status": "success",
            "file": file_path.name,
            "chunks_created": len(chunks),
            "document_metadata": doc_metadata,
            "quality_metrics": {
                "chunks_with_dosages": sum(1 for c in chunks if c.contains_dosage),
                "chunks_with_protocols": sum(1 for c in chunks if c.contains_protocol),
                "chunks_with_contraindications": sum(1 for c in chunks if c.contains_contraindication),
                "severity_distribution": severity_counts,
            }
        }
    
    def ingest_all(self, clear: bool = False) -> Dict[str, Any]:
        """
        Ingest all documents in docs directory
        
        Args:
            clear: If True, clear existing collection before ingesting
            
        Returns:
            Comprehensive ingestion report
        """
        logger.info(f"\n{'#'*80}")
        logger.info("CLINICAL PPH INGESTION V2 - WORLD-CLASS RAG SYSTEM")
        logger.info(f"{'#'*80}\n")
        
        # Initialize collection
        if clear:
            logger.info("Clearing existing collection...")
            delete_collection()
        
        collection = get_or_create_collection()
        embedder = self.get_embedder()
        
        # Find all documents
        supported_formats = [".pdf", ".docx", ".txt", ".md"]
        document_files = [
            f for f in DOCS_DIR.rglob("*")
            if f.is_file() and f.suffix.lower() in supported_formats
        ]
        
        if not document_files:
            logger.warning(f"No documents found in {DOCS_DIR}")
            return {
                "status": "error",
                "message": "No documents found",
                "documents_processed": 0,
            }
        
        logger.info(f"Found {len(document_files)} documents to ingest\n")
        
        # Ingest each document
        results = []
        total_chunks = 0
        
        for doc_file in document_files:
            result = self.ingest_document(doc_file, collection, embedder)
            results.append(result)
            
            if result["status"] == "success":
                total_chunks += result["chunks_created"]
        
        # Generate summary report
        successful = [r for r in results if r["status"] == "success"]
        
        logger.info(f"\n{'#'*80}")
        logger.info("INGESTION COMPLETE")
        logger.info(f"{'#'*80}")
        logger.info(f"\nSUMMARY:")
        logger.info(f"  Documents processed: {len(successful)}/{len(document_files)}")
        logger.info(f"  Total chunks created: {total_chunks}")
        logger.info(f"  Average chunks per document: {total_chunks // len(successful) if successful else 0}")
        
        # Save ingestion report
        report = {
            "ingestion_date": datetime.now().isoformat(),
            "version": "v2_clinical_aware",
            "documents_processed": len(successful),
            "total_documents": len(document_files),
            "total_chunks": total_chunks,
            "results": results,
            "summary": {
                "total_dosage_chunks": sum(
                    r.get("quality_metrics", {}).get("chunks_with_dosages", 0)
                    for r in results if r["status"] == "success"
                ),
                "total_protocol_chunks": sum(
                    r.get("quality_metrics", {}).get("chunks_with_protocols", 0)
                    for r in results if r["status"] == "success"
                ),
                "total_contraindication_chunks": sum(
                    r.get("quality_metrics", {}).get("chunks_with_contraindications", 0)
                    for r in results if r["status"] == "success"
                ),
            }
        }
        
        report_path = BASE_DIR / "INGESTION_REPORT_V2.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        logger.info(f"\n✓ Ingestion report saved: {report_path}")
        
        return report


def main():
    """Main ingestion entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Clinical PPH Document Ingestion V2")
    parser.add_argument("--clear", action="store_true", help="Clear existing collection before ingesting")
    args = parser.parse_args()
    
    ingestor = ClinicalPPHIngestorV2()
    report = ingestor.ingest_all(clear=args.clear)
    
    return report


if __name__ == "__main__":
    main()

