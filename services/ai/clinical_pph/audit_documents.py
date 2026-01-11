"""
Clinical PPH Document Quality & Authority Audit

This script performs comprehensive audit of Clinical PPH guidelines and policy documents:
- Document metadata extraction (source, year, authority)
- Content quality assessment
- Scope analysis (prevention, diagnosis, management, referral)
- Conflict detection
- Authority hierarchy recommendations
"""

import sys
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import re

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.rag.utils import extract_text_from_pdf, extract_text_from_docx

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DocumentAuditor:
    """Comprehensive auditor for Clinical PPH guidelines"""
    
    def __init__(self, docs_dir: Path):
        self.docs_dir = docs_dir
        self.audit_results: List[Dict[str, Any]] = []
        
    def extract_metadata(self, text: str, filename: str) -> Dict[str, Any]:
        """
        Extract document metadata from content
        
        Returns:
            Dict with source_organization, publication_year, version, scope
        """
        metadata = {
            "filename": filename,
            "source_organization": "Unknown",
            "publication_year": None,
            "version": None,
            "scope": [],
            "authority_level": "Unknown",
            "document_type": "Unknown",
            "pages_estimated": len(text) // 3000,  # Rough estimate
            "character_count": len(text),
            "word_count": len(text.split()),
        }
        
        # Extract year (look for 2020-2025 patterns)
        year_patterns = [
            r'\b(202[0-5])\b',
            r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(202[0-5])',
            r'(\d{1,2})[/-](0?[1-9]|1[0-2])[/-](202[0-5])',
        ]
        years_found = []
        for pattern in year_patterns:
            matches = re.findall(pattern, text[:5000])  # Search first 5000 chars
            for match in matches:
                year = match if isinstance(match, str) else match[-1]
                if year.startswith('20'):
                    years_found.append(int(year))
        
        if years_found:
            metadata["publication_year"] = max(years_found)  # Use most recent year
        
        # Extract source organization
        org_keywords = {
            "WHO": ["World Health Organization", "WHO", "World Health Org"],
            "FIGO": ["International Federation of Gynecology", "FIGO"],
            "National": ["National guideline", "Federal Ministry", "National Policy"],
            "RANZCOG": ["Royal Australian and New Zealand", "RANZCOG"],
            "RCOG": ["Royal College of Obstetricians", "RCOG"],
            "ACOG": ["American College of Obstetricians", "ACOG"],
            "SOGON": ["Society of Gynaecology", "SOGON", "Nigerian"],
        }
        
        text_upper = text[:10000].upper()  # Search first 10000 chars
        for org, keywords in org_keywords.items():
            if any(keyword.upper() in text_upper for keyword in keywords):
                metadata["source_organization"] = org
                break
        
        # Determine authority level
        authority_hierarchy = {
            "WHO": "International - Highest",
            "FIGO": "International - High",
            "National": "National - Medium-High",
            "RCOG": "Regional/Professional - Medium",
            "RANZCOG": "Regional/Professional - Medium",
            "ACOG": "Regional/Professional - Medium",
            "SOGON": "National Professional - Medium",
        }
        metadata["authority_level"] = authority_hierarchy.get(
            metadata["source_organization"], "Unknown - Verify"
        )
        
        # Extract document type
        doc_type_keywords = {
            "Clinical Guideline": ["clinical guideline", "practice guideline", "clinical practice"],
            "Training Manual": ["training manual", "training guide", "participant manual"],
            "Policy Document": ["policy", "national policy", "health policy"],
            "Protocol": ["protocol", "clinical protocol", "management protocol"],
            "Standard Operating Procedure": ["sop", "standard operating procedure"],
        }
        
        text_lower = text[:5000].lower()
        for doc_type, keywords in doc_type_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                metadata["document_type"] = doc_type
                break
        
        # Extract scope (prevention, diagnosis, management, referral)
        scope_keywords = {
            "Prevention": ["prevent", "prevention", "prophylaxis", "risk reduction", "oxytocin"],
            "Diagnosis": ["diagnos", "assessment", "evaluation", "identification", "signs", "symptoms"],
            "Management": ["management", "treatment", "intervention", "therapy", "transfusion"],
            "Referral": ["referral", "transfer", "escalation", "specialist", "tertiary"],
            "Emergency Response": ["emergency", "shock", "resuscitation", "life-threatening"],
            "Monitoring": ["monitoring", "observation", "vital signs", "surveillance"],
        }
        
        text_sample = text[:20000].lower()  # Sample first 20k chars
        for scope_area, keywords in scope_keywords.items():
            keyword_count = sum(text_sample.count(keyword) for keyword in keywords)
            if keyword_count > 2:  # Present if mentioned multiple times
                metadata["scope"].append(f"{scope_area} ({keyword_count} mentions)")
        
        # Extract version if available
        version_pattern = r'(?:version|ver\.|v\.?)\s*([0-9]+(?:\.[0-9]+)*)'
        version_match = re.search(version_pattern, text[:5000], re.IGNORECASE)
        if version_match:
            metadata["version"] = version_match.group(1)
        
        return metadata
    
    def assess_text_quality(self, text: str) -> Dict[str, Any]:
        """
        Assess text extraction quality
        
        Returns:
            Dict with quality metrics
        """
        quality = {
            "has_noise": False,
            "noise_indicators": [],
            "has_tables": False,
            "has_structured_content": False,
            "readability": "Unknown",
            "issues": [],
        }
        
        # Check for extraction noise
        noise_patterns = [
            (r'\s{5,}', "Excessive whitespace"),
            (r'[^\w\s.,;:!?\-()]{5,}', "Special character sequences"),
            (r'(?:page|pg\.?)\s*\d+', "Page number remnants"),
            (r'(?:header|footer)', "Header/footer remnants"),
        ]
        
        for pattern, description in noise_patterns:
            if re.search(pattern, text[:5000], re.IGNORECASE):
                quality["has_noise"] = True
                quality["noise_indicators"].append(description)
        
        # Check for tables
        table_indicators = ["|", "┌", "─", "│", "Table", "Figure"]
        if any(indicator in text[:10000] for indicator in table_indicators):
            quality["has_tables"] = True
        
        # Check for structured content
        if re.search(r'(?:\d+\.|•|–|\n\s*\n)', text[:5000]):
            quality["has_structured_content"] = True
        
        # Basic readability assessment
        sentences = text.split('.')
        if len(sentences) > 10:
            avg_sentence_length = sum(len(s.split()) for s in sentences[:100]) / min(100, len(sentences))
            if avg_sentence_length < 5:
                quality["readability"] = "Poor - Very short sentences (possible extraction issue)"
                quality["issues"].append("Abnormally short sentences detected")
            elif avg_sentence_length > 50:
                quality["readability"] = "Poor - Very long sentences (possible extraction issue)"
                quality["issues"].append("Abnormally long sentences detected")
            else:
                quality["readability"] = "Good - Normal sentence structure"
        
        # Check for incomplete words or broken text
        broken_words = re.findall(r'\b\w{1,2}\s+\w{1,2}\s+\w{1,2}\b', text[:5000])
        if len(broken_words) > 20:
            quality["issues"].append("Possible broken/fragmented words detected")
        
        return quality
    
    def detect_conflicts(self, all_metadata: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Detect conflicting guidance across documents
        
        Returns:
            List of potential conflicts
        """
        conflicts = []
        
        # Check for multiple documents from different years covering same scope
        scope_years = {}
        for doc in all_metadata:
            for scope in doc.get("scope", []):
                scope_name = scope.split(" (")[0]  # Remove count
                if scope_name not in scope_years:
                    scope_years[scope_name] = []
                scope_years[scope_name].append({
                    "filename": doc["filename"],
                    "year": doc.get("publication_year"),
                    "organization": doc.get("source_organization"),
                })
        
        for scope, docs in scope_years.items():
            years = [d["year"] for d in docs if d["year"]]
            if len(set(years)) > 1:
                year_diff = max(years) - min(years)
                if year_diff > 2:  # More than 2 years difference
                    conflicts.append({
                        "type": "Potential Outdated Guidance",
                        "scope": scope,
                        "details": f"Documents from {min(years)} and {max(years)} cover this scope",
                        "affected_files": [d["filename"] for d in docs],
                        "recommendation": f"Verify if {min(years)} document is superseded",
                    })
        
        # Check for multiple authoritative sources
        orgs = [doc.get("source_organization") for doc in all_metadata]
        if len(set(orgs)) > 1 and "Unknown" not in orgs:
            conflicts.append({
                "type": "Multiple Authority Sources",
                "details": f"Documents from: {', '.join(set(orgs))}",
                "recommendation": "Establish clear authority hierarchy (e.g., WHO > National > Regional)",
            })
        
        return conflicts
    
    def audit_all_documents(self) -> Dict[str, Any]:
        """
        Perform comprehensive audit of all documents
        
        Returns:
            Complete audit report
        """
        logger.info(f"Starting document audit in: {self.docs_dir}")
        
        supported_formats = [".pdf", ".docx", ".txt", ".md"]
        document_files = [
            f for f in self.docs_dir.rglob("*")
            if f.is_file() and f.suffix.lower() in supported_formats
        ]
        
        if not document_files:
            logger.warning(f"No documents found in {self.docs_dir}")
            return {"status": "error", "message": "No documents found"}
        
        logger.info(f"Found {len(document_files)} documents to audit")
        
        all_metadata = []
        
        for doc_file in document_files:
            logger.info(f"\n{'='*80}")
            logger.info(f"Auditing: {doc_file.name}")
            logger.info(f"{'='*80}")
            
            try:
                # Extract text
                if doc_file.suffix.lower() == ".pdf":
                    text = extract_text_from_pdf(str(doc_file))
                elif doc_file.suffix.lower() == ".docx":
                    text = extract_text_from_docx(str(doc_file))
                else:
                    text = doc_file.read_text(encoding="utf-8", errors="ignore")
                
                if not text or len(text) < 100:
                    logger.warning(f"⚠️  Minimal text extracted ({len(text)} chars)")
                    continue
                
                logger.info(f"✓ Text extracted: {len(text)} characters, ~{len(text.split())} words")
                
                # Extract metadata
                metadata = self.extract_metadata(text, doc_file.name)
                logger.info(f"✓ Source: {metadata['source_organization']}")
                logger.info(f"✓ Year: {metadata['publication_year'] or 'Not found'}")
                logger.info(f"✓ Type: {metadata['document_type']}")
                logger.info(f"✓ Authority: {metadata['authority_level']}")
                logger.info(f"✓ Scope: {', '.join(metadata['scope']) if metadata['scope'] else 'Not determined'}")
                
                # Assess quality
                quality = self.assess_text_quality(text)
                logger.info(f"✓ Readability: {quality['readability']}")
                if quality["has_noise"]:
                    logger.warning(f"⚠️  Noise detected: {', '.join(quality['noise_indicators'])}")
                if quality["has_tables"]:
                    logger.info(f"✓ Contains tables/figures")
                if quality["issues"]:
                    logger.warning(f"⚠️  Issues: {', '.join(quality['issues'])}")
                
                # Store results
                metadata["quality_assessment"] = quality
                metadata["text_preview"] = text[:500]
                all_metadata.append(metadata)
                
            except Exception as e:
                logger.error(f"❌ Error processing {doc_file.name}: {e}")
                continue
        
        # Detect conflicts
        logger.info(f"\n{'='*80}")
        logger.info("CONFLICT ANALYSIS")
        logger.info(f"{'='*80}")
        
        conflicts = self.detect_conflicts(all_metadata)
        
        if conflicts:
            for conflict in conflicts:
                logger.warning(f"\n⚠️  {conflict['type']}")
                logger.warning(f"   {conflict.get('details', '')}")
                logger.warning(f"   Recommendation: {conflict.get('recommendation', 'Review manually')}")
        else:
            logger.info("✓ No conflicts detected")
        
        # Generate recommendations
        logger.info(f"\n{'='*80}")
        logger.info("RECOMMENDATIONS")
        logger.info(f"{'='*80}")
        
        recommendations = self.generate_recommendations(all_metadata, conflicts)
        for i, rec in enumerate(recommendations, 1):
            logger.info(f"\n{i}. {rec['title']}")
            logger.info(f"   {rec['description']}")
            logger.info(f"   Priority: {rec['priority']}")
        
        # Generate summary
        audit_report = {
            "audit_date": datetime.now().isoformat(),
            "documents_audited": len(all_metadata),
            "documents": all_metadata,
            "conflicts": conflicts,
            "recommendations": recommendations,
            "summary": {
                "total_documents": len(all_metadata),
                "sources": list(set(d["source_organization"] for d in all_metadata)),
                "years": sorted(set(d["publication_year"] for d in all_metadata if d["publication_year"])),
                "document_types": list(set(d["document_type"] for d in all_metadata)),
                "total_content_chars": sum(d["character_count"] for d in all_metadata),
                "total_content_words": sum(d["word_count"] for d in all_metadata),
            }
        }
        
        return audit_report
    
    def generate_recommendations(
        self, 
        all_metadata: List[Dict[str, Any]], 
        conflicts: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Generate actionable recommendations"""
        
        recommendations = []
        
        # Authority hierarchy
        orgs = set(d["source_organization"] for d in all_metadata)
        if len(orgs) > 1:
            recommendations.append({
                "title": "Establish Authority Hierarchy",
                "description": (
                    f"Multiple sources detected: {', '.join(orgs)}. "
                    "Recommend: WHO > FIGO > National Guidelines > Regional/Professional Bodies. "
                    "Implement metadata-based authority scoring for conflict resolution."
                ),
                "priority": "HIGH",
                "action": "Add 'authority_score' to metadata during ingestion",
            })
        
        # Outdated documents
        years = [d["publication_year"] for d in all_metadata if d["publication_year"]]
        if years and max(years) - min(years) > 2:
            recommendations.append({
                "title": "Flag Potentially Outdated Documents",
                "description": (
                    f"Documents span {min(years)}-{max(years)}. "
                    "Verify if older documents are superseded. "
                    "Consider excluding or lower-weighting documents >3 years old."
                ),
                "priority": "HIGH",
                "action": "Add 'is_superseded' flag and 'superseded_by' field to metadata",
            })
        
        # Text extraction quality
        poor_quality = [d for d in all_metadata if d.get("quality_assessment", {}).get("issues")]
        if poor_quality:
            recommendations.append({
                "title": "Improve Text Extraction Quality",
                "description": (
                    f"{len(poor_quality)} document(s) have extraction issues. "
                    "Consider using OCR or manual review for better quality."
                ),
                "priority": "MEDIUM",
                "action": "Re-process with OCR or review extraction scripts",
            })
        
        # Chunking strategy
        recommendations.append({
            "title": "Implement Clinical-Aware Chunking",
            "description": (
                "Current chunking: 900 chars (~180 words), 120 char overlap. "
                "Upgrade to: 300-600 tokens (~225-450 words), section-aligned, "
                "preserve clinical concepts (definitions, protocols, contraindications)."
            ),
            "priority": "CRITICAL",
            "action": "Implement semantic chunking that respects clinical section boundaries",
        })
        
        # Metadata richness
        recommendations.append({
            "title": "Enrich Metadata for Precision Retrieval",
            "description": (
                "Add: guideline_name, issuing_body, year, clinical_context, "
                "pph_severity (mild/moderate/severe), document_path, section_title, "
                "authority_score, is_superseded."
            ),
            "priority": "CRITICAL",
            "action": "Upgrade ingest.py to extract and index clinical metadata",
        })
        
        return recommendations


def main():
    """Run comprehensive document audit"""
    docs_dir = Path(__file__).parent / "docs"
    
    auditor = DocumentAuditor(docs_dir)
    report = auditor.audit_all_documents()
    
    # Save report
    import json
    report_path = Path(__file__).parent / "AUDIT_REPORT.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    logger.info(f"\n{'='*80}")
    logger.info(f"AUDIT COMPLETE")
    logger.info(f"{'='*80}")
    logger.info(f"Report saved to: {report_path}")
    logger.info(f"\nSUMMARY:")
    logger.info(f"  Documents audited: {report['summary']['total_documents']}")
    logger.info(f"  Sources: {', '.join(report['summary']['sources'])}")
    logger.info(f"  Years: {', '.join(map(str, report['summary']['years'])) if report['summary']['years'] else 'Not found'}")
    logger.info(f"  Conflicts detected: {len(report['conflicts'])}")
    logger.info(f"  Recommendations: {len(report['recommendations'])}")
    
    return report


if __name__ == "__main__":
    main()

