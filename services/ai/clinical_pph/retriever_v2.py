"""
Precision Retrieval Layer with Clinical Metadata Filtering

This module implements world-class retrieval features:
- Semantic search with clinical metadata filtering
- Authority-aware re-ranking
- Evidence validation
- Citation tracking
"""

from __future__ import annotations

import logging
from typing import Any, Optional, List, Dict, Tuple
from dataclasses import dataclass

from sentence_transformers import SentenceTransformer

from app.core.config import settings
from clinical_pph.store import get_or_create_collection

logger = logging.getLogger(__name__)

_embedder: Optional[SentenceTransformer] = None


@dataclass
class RetrievedChunk:
    """Represents a retrieved chunk with full metadata"""
    text: str
    distance: float  # Lower is better (more similar)
    
    # Document metadata
    guideline_name: str
    issuing_body: str
    publication_year: int
    authority_score: int
    
    # Chunk metadata
    section_title: str
    clinical_context: str
    pph_severity: str
    contains_dosage: bool
    contains_protocol: bool
    contains_contraindication: bool
    
    # Evidence traceability
    document_path: str
    chunk_index: int
    
    def to_citation(self) -> str:
        """Generate inline citation"""
        return f"({self.guideline_name}, {self.publication_year}, Section: {self.section_title})"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "text": self.text,
            "distance": self.distance,
            "citation": self.to_citation(),
            "guideline_name": self.guideline_name,
            "issuing_body": self.issuing_body,
            "publication_year": self.publication_year,
            "authority_score": self.authority_score,
            "section_title": self.section_title,
            "clinical_context": self.clinical_context,
            "pph_severity": self.pph_severity,
            "contains_dosage": self.contains_dosage,
            "contains_protocol": self.contains_protocol,
            "contains_contraindication": self.contains_contraindication,
            "document_path": self.document_path,
            "chunk_index": self.chunk_index,
        }


def _get_embedder() -> SentenceTransformer:
    """Get or create the embedding model singleton"""
    global _embedder
    if _embedder is None:
        model_name = getattr(settings, "EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
        logger.info(f"Initializing embedding model for Clinical PPH: {model_name}")
        try:
            _embedder = SentenceTransformer(model_name)
            logger.info(f"Embedding model loaded successfully: {model_name}")
        except Exception as e:
            logger.error(f"Failed to load embedding model {model_name}: {e}")
            raise
    return _embedder


def retrieve_with_metadata(
    query: str,
    k: int = 5,
    clinical_context: Optional[str] = None,
    pph_severity: Optional[str] = None,
    min_authority_score: int = 0,
    exclude_superseded: bool = True
) -> List[RetrievedChunk]:
    """
    Retrieve relevant documents with precision metadata filtering
    
    Args:
        query: User query string
        k: Number of documents to retrieve (default: 5)
        clinical_context: Filter by context (e.g., 'prevention', 'management')
        pph_severity: Filter by severity ('mild', 'moderate', 'severe', 'any')
        min_authority_score: Minimum authority score (0-100)
        exclude_superseded: Exclude superseded documents (default: True)
        
    Returns:
        List of RetrievedChunk objects with full metadata and citations
    """
    query = (query or "").strip()
    if not query:
        logger.warning("Empty query provided to retriever")
        return []
    
    try:
        # Get collection
        collection = get_or_create_collection()
        collection_count = collection.count()
        
        if collection_count == 0:
            logger.warning("Clinical PPH collection is empty. Run ingestion first.")
            return []
        
        # Generate query embedding
        embedder = _get_embedder()
        try:
            query_embedding = embedder.encode([query], show_progress_bar=False).tolist()[0]
        except Exception as e:
            logger.error(f"Failed to encode query: {e}")
            return []
        
        # Build metadata filter
        where_filter: Dict[str, Any] = {}
        
        if exclude_superseded:
            where_filter["is_superseded"] = False
        
        if min_authority_score > 0:
            where_filter["authority_score"] = {"$gte": min_authority_score}
        
        # Note: ChromaDB doesn't support complex OR logic in where filters well
        # So we'll retrieve more results and filter/re-rank in Python
        search_k = k * 3 if (clinical_context or pph_severity) else k
        
        # Query the collection
        try:
            if where_filter:
                res = collection.query(
                    query_embeddings=[query_embedding],
                    n_results=min(search_k, 20),  # Cap at 20 for performance
                    where=where_filter,
                    include=["documents", "metadatas", "distances"],
                )
            else:
                res = collection.query(
                    query_embeddings=[query_embedding],
                    n_results=min(search_k, 20),
                    include=["documents", "metadatas", "distances"],
                )
        except Exception as e:
            logger.error(f"Failed to query collection: {e}")
            return []
        
        docs = (res.get("documents") or [[]])[0]
        mds = (res.get("metadatas") or [[]])[0]
        distances = (res.get("distances") or [[]])[0]
        
        if not docs:
            logger.info(f"No documents retrieved for query: '{query[:50]}...'")
            return []
        
        # Parse into RetrievedChunk objects
        chunks: List[RetrievedChunk] = []
        for i, (doc, metadata, distance) in enumerate(zip(docs, mds, distances)):
            # Additional filtering
            if clinical_context:
                chunk_contexts = metadata.get("clinical_context", "").split(",")
                if clinical_context not in chunk_contexts and "general" not in chunk_contexts:
                    continue
            
            if pph_severity:
                chunk_severity = metadata.get("pph_severity", "any")
                if chunk_severity != "any" and chunk_severity != pph_severity:
                    continue
            
            chunk = RetrievedChunk(
                text=doc,
                distance=distance,
                guideline_name=metadata.get("guideline_name", "Unknown"),
                issuing_body=metadata.get("issuing_body", "Unknown"),
                publication_year=metadata.get("publication_year", 2024),
                authority_score=metadata.get("authority_score", 50),
                section_title=metadata.get("section_title", "Unknown"),
                clinical_context=metadata.get("clinical_context", "general"),
                pph_severity=metadata.get("pph_severity", "any"),
                contains_dosage=metadata.get("contains_dosage", False),
                contains_protocol=metadata.get("contains_protocol", False),
                contains_contraindication=metadata.get("contains_contraindication", False),
                document_path=metadata.get("document_path", ""),
                chunk_index=metadata.get("chunk_index", 0),
            )
            chunks.append(chunk)
        
        # Re-rank by authority score (break ties with distance)
        chunks.sort(key=lambda c: (-c.authority_score, c.distance))
        
        # Return top k
        result_chunks = chunks[:k]
        
        logger.debug(f"Retrieved {len(result_chunks)} chunks for query length={len(query)}")
        
        return result_chunks
    
    except Exception as e:
        logger.error(f"Error retrieving from Clinical PPH: {e}", exc_info=True)
        return []


def retrieve_with_citations(
    query: str,
    k: int = 5,
    **kwargs
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Retrieve documents and return formatted context with inline citations
    
    Args:
        query: User query
        k: Number of chunks to retrieve
        **kwargs: Additional filters for retrieve_with_metadata
        
    Returns:
        Tuple of (formatted_context, citations_list)
        formatted_context: Text with inline citations
        citations_list: List of citation dicts for verification
    """
    chunks = retrieve_with_metadata(query, k=k, **kwargs)
    
    if not chunks:
        return "", []
    
    # Build context with inline citations
    context_parts = []
    citations = []
    
    for i, chunk in enumerate(chunks, 1):
        citation_marker = f"[{i}]"
        context_parts.append(f"{chunk.text}\n{citation_marker}")
        
        citations.append({
            "id": i,
            "citation": chunk.to_citation(),
            "guideline_name": chunk.guideline_name,
            "issuing_body": chunk.issuing_body,
            "section_title": chunk.section_title,
            "document_path": chunk.document_path,
            "authority_score": chunk.authority_score,
        })
    
    formatted_context = "\n\n---\n\n".join(context_parts)
    
    return formatted_context, citations


def validate_evidence_exists(
    query: str,
    threshold_distance: float = 0.75,  # Phase 1: Adjusted from 0.6 to 0.75
    query_type: str = "direct"  # "direct", "comparative", "emergency_protocol"
) -> Tuple[bool, str]:
    """
    Validate if evidence exists in knowledge base for query
    
    Phase 1: Adjusted threshold from 0.6 to 0.75 to reduce false refusals
    on legitimate clinical protocol questions while maintaining safety.
    
    Args:
        query: User query
        threshold_distance: Maximum distance to consider relevant (default: 0.75)
        query_type: Type of query for threshold adjustment
            - "direct": Standard factual query (threshold: 0.75)
            - "comparative": Guideline comparison (threshold: 0.80)
            - "emergency_protocol": Emergency procedure query (threshold: 0.75)
        
    Returns:
        Tuple of (evidence_exists, message)
        evidence_exists: True if relevant evidence found
        message: Explanation if no evidence
    """
    # Adjust threshold based on query type
    if query_type == "comparative":
        # Comparative queries ("difference between", "which guideline") have lower semantic similarity
        adjusted_threshold = 0.80
    elif query_type == "emergency_protocol":
        # Emergency protocol queries use standard threshold
        adjusted_threshold = 0.75
    else:
        # Direct queries use standard threshold
        adjusted_threshold = threshold_distance
    
    chunks = retrieve_with_metadata(query, k=3)
    
    if not chunks:
        return False, "No relevant information found in the Clinical PPH knowledge base."
    
    # Check if best match is within threshold
    best_distance = chunks[0].distance
    
    if best_distance > adjusted_threshold:
        return False, (
            "This information is not explicitly stated in the available PPH clinical "
            "guidelines in this knowledge base. For specific medical guidance, please "
            "consult with a healthcare professional or refer to the original clinical guidelines."
        )
    
    return True, ""


# Backward compatibility function
def retrieve(query: str, k: int = 5) -> str:
    """
    Legacy retrieval function for backward compatibility
    
    Returns formatted context without citations (for existing code)
    """
    chunks = retrieve_with_metadata(query, k=k)
    
    if not chunks:
        return ""
    
    parts = [chunk.text for chunk in chunks]
    return "\n\n---\n\n".join(parts).strip()

