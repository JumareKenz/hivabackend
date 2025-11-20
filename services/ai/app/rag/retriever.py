# services/ai/app/rag/retriever.py
import os
import chromadb
from sentence_transformers import SentenceTransformer
from typing import Optional

# Use absolute path for DB (same as ingest.py)
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(_BASE_DIR, "db")

# Import config for embedding model
from app.core.config import settings

EMBEDDING_MODEL = getattr(settings, "EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")

print(f"Loading embedding model for retrieval: {EMBEDDING_MODEL} ...")
print("⚠️  Note: First load may take 30-60 seconds to download model...")
model = SentenceTransformer(EMBEDDING_MODEL)
print("✓ Embedding model loaded")

# Ensure DB directory exists
os.makedirs(DB_DIR, exist_ok=True)

client = chromadb.PersistentClient(path=DB_DIR)
collection = client.get_or_create_collection("faqs")

def retrieve(query: str, k: int = 3, branch_id: Optional[str] = None) -> str:
    """
    Return top-k relevant chunks concatenated as context for RAG.
    
    Args:
        query: User query string
        k: Number of documents to retrieve
        branch_id: Optional branch ID to filter results (only return docs from this branch)
        
    Returns:
        Concatenated context string, or empty string if no results
    """
    try:
        # BGE models work better with query instruction prefix
        # For other models, this won't hurt
        if "bge" in EMBEDDING_MODEL.lower():
            query_for_embedding = f"Represent this sentence for searching relevant passages: {query}"
        else:
            query_for_embedding = query
        
        embedding = model.encode(query_for_embedding, show_progress_bar=False, normalize_embeddings=True).tolist()
        
        # Build query with optional branch filter
        where_clause = None
        if branch_id:
            where_clause = {"branch_id": branch_id}
        
        # Query with branch filtering
        results = collection.query(
            query_embeddings=[embedding],
            n_results=min(k * 2 if branch_id else k, 20),  # Get more if filtering by branch
            where=where_clause if where_clause else None
        )
        
        # STRICT MODE: Only use branch-specific docs if branch_id is provided
        # Don't fall back to general docs to prevent mixing branches
        if branch_id and results.get("documents") and len(results["documents"][0]) < k:
            # Only use what we have - don't mix with other branches
            # This prevents hallucination and mixing information
            pass
        
        if not results or not results.get("documents") or not results["documents"][0]:
            return ""
        
        docs = results["documents"][0][:k]  # Limit to k
        return "\n\n".join(docs)
    except Exception as e:
        print(f"Error in retrieval: {e}")
        return ""
