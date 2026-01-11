"""
Vector store module for Zamfara RAG system.

Provides ChromaDB-based vector storage with:
- Efficient similarity search
- Metadata filtering
- Persistence
- Batch operations
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import hashlib

try:
    from chromadb import PersistentClient
    from chromadb.config import Settings as ChromaSettings
    from chromadb.api.models.Collection import Collection
except ImportError:
    PersistentClient = None
    ChromaSettings = None
    Collection = None

logger = logging.getLogger(__name__)


class VectorStore:
    """
    ChromaDB-based vector store for document chunks.
    
    Features:
    - Persistent storage
    - Fast similarity search
    - Metadata filtering
    - Batch upsert operations
    - Collection management
    """
    
    _instance: Optional["VectorStore"] = None
    _client: Optional[PersistentClient] = None
    
    def __new__(cls, *args, **kwargs):
        """Singleton pattern for vector store."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(
        self,
        persist_dir: Path,
        collection_name: str = "zamfara_kb",
    ):
        """
        Initialize the vector store.
        
        Args:
            persist_dir: Directory for persistent storage
            collection_name: Name of the ChromaDB collection
        """
        if PersistentClient is None:
            raise ImportError(
                "chromadb is required. Install with: pip install chromadb"
            )
        
        self.persist_dir = Path(persist_dir)
        self.collection_name = collection_name
        
        # Initialize client
        self._init_client()
        
        # Get or create collection
        self._collection: Optional[Collection] = None
    
    def _init_client(self) -> None:
        """Initialize the ChromaDB client."""
        if VectorStore._client is not None:
            return
        
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Initializing ChromaDB at: {self.persist_dir}")
        
        VectorStore._client = PersistentClient(
            path=str(self.persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        
        logger.info("ChromaDB client initialized")
    
    @property
    def client(self) -> PersistentClient:
        """Get the ChromaDB client."""
        if VectorStore._client is None:
            self._init_client()
        return VectorStore._client
    
    @property
    def collection(self) -> Collection:
        """Get or create the collection."""
        if self._collection is None:
            self._collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={
                    "description": "Zamfara State Knowledge Base",
                    "hnsw:space": "cosine",  # Use cosine similarity
                },
            )
            logger.info(f"Collection '{self.collection_name}' ready")
        return self._collection
    
    def add_documents(
        self,
        ids: List[str],
        documents: List[str],
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]],
    ) -> int:
        """
        Add documents to the vector store.
        
        Args:
            ids: Unique identifiers for each document
            documents: Document texts
            embeddings: Vector embeddings
            metadatas: Metadata dictionaries
            
        Returns:
            Number of documents added
        """
        if not ids:
            return 0
        
        # Filter out any None values in metadata
        clean_metadatas = []
        for md in metadatas:
            clean_md = {}
            for k, v in md.items():
                if v is not None:
                    # ChromaDB only supports str, int, float, bool
                    if isinstance(v, (str, int, float, bool)):
                        clean_md[k] = v
                    elif isinstance(v, list):
                        # Convert lists to comma-separated strings
                        clean_md[k] = ",".join(str(x) for x in v)
                    else:
                        clean_md[k] = str(v)
            clean_metadatas.append(clean_md)
        
        logger.info(f"Adding {len(ids)} documents to vector store")
        
        try:
            # Use upsert to handle duplicates
            self.collection.upsert(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=clean_metadatas,
            )
            logger.info(f"Successfully added {len(ids)} documents")
            return len(ids)
        except Exception as e:
            logger.error(f"Failed to add documents: {e}")
            # Try add as fallback
            try:
                self.collection.add(
                    ids=ids,
                    documents=documents,
                    embeddings=embeddings,
                    metadatas=clean_metadatas,
                )
                return len(ids)
            except Exception as e2:
                logger.error(f"Fallback add also failed: {e2}")
                raise
    
    def search(
        self,
        query_embedding: List[float],
        k: int = 5,
        filter_dict: Optional[Dict[str, Any]] = None,
        include_distances: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Search for similar documents.
        
        Args:
            query_embedding: Query vector embedding
            k: Number of results to return
            filter_dict: Metadata filter (ChromaDB where clause)
            include_distances: Include distance scores
            
        Returns:
            List of result dictionaries with document, metadata, and score
        """
        include = ["documents", "metadatas"]
        if include_distances:
            include.append("distances")
        
        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=k,
                where=filter_dict,
                include=include,
            )
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
        
        # Format results
        formatted = []
        
        documents = (results.get("documents") or [[]])[0]
        metadatas = (results.get("metadatas") or [[]])[0]
        distances = (results.get("distances") or [[]])[0] if include_distances else [0.0] * len(documents)
        ids = (results.get("ids") or [[]])[0]
        
        for i, (doc, meta, dist, doc_id) in enumerate(zip(documents, metadatas, distances, ids)):
            # Convert distance to similarity score (cosine distance to similarity)
            similarity = 1 - dist if dist is not None else 0.0
            
            formatted.append({
                "id": doc_id,
                "document": doc,
                "metadata": meta or {},
                "distance": dist,
                "similarity": similarity,
                "rank": i + 1,
            })
        
        return formatted
    
    def search_with_metadata_filter(
        self,
        query_embedding: List[float],
        k: int = 5,
        document_type: Optional[str] = None,
        department: Optional[str] = None,
        min_similarity: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        Search with optional metadata filtering.
        
        Args:
            query_embedding: Query vector embedding
            k: Number of results to return
            document_type: Filter by document type
            department: Filter by department
            min_similarity: Minimum similarity threshold
            
        Returns:
            List of filtered results
        """
        # Build filter
        filter_conditions = []
        
        if document_type:
            filter_conditions.append({"document_type": document_type})
        
        if department:
            filter_conditions.append({"department": department})
        
        filter_dict = None
        if len(filter_conditions) == 1:
            filter_dict = filter_conditions[0]
        elif len(filter_conditions) > 1:
            filter_dict = {"$and": filter_conditions}
        
        # Search
        results = self.search(query_embedding, k=k * 2, filter_dict=filter_dict)
        
        # Apply similarity threshold
        filtered = [r for r in results if r["similarity"] >= min_similarity]
        
        return filtered[:k]
    
    def get_by_id(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a document by ID.
        
        Args:
            doc_id: Document ID
            
        Returns:
            Document data or None
        """
        try:
            results = self.collection.get(
                ids=[doc_id],
                include=["documents", "metadatas"],
            )
            
            if results["documents"]:
                return {
                    "id": doc_id,
                    "document": results["documents"][0],
                    "metadata": results["metadatas"][0] if results["metadatas"] else {},
                }
        except Exception as e:
            logger.error(f"Failed to get document {doc_id}: {e}")
        
        return None
    
    def delete_by_ids(self, ids: List[str]) -> int:
        """
        Delete documents by IDs.
        
        Args:
            ids: List of document IDs to delete
            
        Returns:
            Number of documents deleted
        """
        if not ids:
            return 0
        
        try:
            self.collection.delete(ids=ids)
            logger.info(f"Deleted {len(ids)} documents")
            return len(ids)
        except Exception as e:
            logger.error(f"Failed to delete documents: {e}")
            return 0
    
    def clear(self) -> None:
        """Clear all documents from the collection."""
        try:
            # Delete and recreate collection
            self.client.delete_collection(self.collection_name)
            self._collection = None
            logger.info(f"Cleared collection: {self.collection_name}")
        except Exception as e:
            logger.warning(f"Failed to clear collection: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get collection statistics."""
        try:
            count = self.collection.count()
            return {
                "collection_name": self.collection_name,
                "document_count": count,
                "persist_dir": str(self.persist_dir),
            }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {
                "collection_name": self.collection_name,
                "error": str(e),
            }
    
    def document_exists(self, doc_id: str) -> bool:
        """Check if a document exists."""
        try:
            results = self.collection.get(ids=[doc_id], include=[])
            return len(results["ids"]) > 0
        except Exception:
            return False
    
    @staticmethod
    def generate_chunk_id(file_path: str, chunk_index: int) -> str:
        """
        Generate a stable, unique ID for a chunk.
        
        Args:
            file_path: Path to source file
            chunk_index: Index of chunk in document
            
        Returns:
            Unique chunk ID
        """
        content = f"{file_path}::{chunk_index}"
        return hashlib.md5(content.encode("utf-8")).hexdigest()




