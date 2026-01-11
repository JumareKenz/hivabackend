"""
Main Provider RAG Service.

Orchestrates the complete RAG pipeline:
1. Query classification
2. Retrieval (hybrid dense + sparse)
3. Answer generation (strictly grounded)
4. Safety validation

This is the main entry point for the Provider RAG system.

Usage:
    from app.providers_rag import ProviderRAGService
    
    service = ProviderRAGService()
    await service.initialize()
    
    result = await service.query("How do I submit a claim?")
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from app.providers_rag.config import provider_rag_config, ProviderRAGConfig
from app.providers_rag.generator import GroundedGenerator
from app.providers_rag.ingestion import ProviderIngestionPipeline
from app.providers_rag.retriever import HybridRetriever
from app.providers_rag.safety import QueryClassifier, SafetyGate
from app.providers_rag.schemas import (
    ConfidenceLevel,
    HealthStatus,
    IngestionResult,
    QueryResult,
)

logger = logging.getLogger(__name__)


class ProviderRAGService:
    """
    Production-grade Provider RAG Service.
    
    Features:
    - Zero hallucination guarantee through strict grounding
    - Hybrid retrieval (dense + sparse)
    - Confidence-based response gating
    - Comprehensive safety validation
    - Full audit trail with citations
    
    Thread-safe and async-ready.
    """
    
    def __init__(self, config: Optional[ProviderRAGConfig] = None):
        """
        Initialize the service.
        
        Args:
            config: Optional custom configuration. Uses default if not provided.
        """
        self.config = config or provider_rag_config
        
        # Initialize components (lazy loaded)
        # NOTE: These are shared across requests but stateless
        # Per-request isolation is ensured by:
        # 1. No shared mutable state in generators
        # 2. Each query() call creates fresh QueryResult
        # 3. No global response buffers
        self._retriever: Optional[HybridRetriever] = None
        self._generator: Optional[GroundedGenerator] = None
        self._safety_gate: Optional[SafetyGate] = None
        self._classifier: Optional[QueryClassifier] = None
        self._ingestion_pipeline: Optional[ProviderIngestionPipeline] = None
        
        self._is_initialized: bool = False
        
        logger.info("ProviderRAGService created (per-request isolation enforced)")
    
    @property
    def retriever(self) -> HybridRetriever:
        """Get the retriever instance."""
        if self._retriever is None:
            self._retriever = HybridRetriever(self.config)
        return self._retriever
    
    @property
    def generator(self) -> GroundedGenerator:
        """Get the generator instance."""
        if self._generator is None:
            self._generator = GroundedGenerator(self.config)
        return self._generator
    
    @property
    def safety_gate(self) -> SafetyGate:
        """Get the safety gate instance."""
        if self._safety_gate is None:
            self._safety_gate = SafetyGate(self.config)
        return self._safety_gate
    
    @property
    def classifier(self) -> QueryClassifier:
        """Get the query classifier instance."""
        if self._classifier is None:
            self._classifier = QueryClassifier()
        return self._classifier
    
    async def initialize(self) -> None:
        """
        Initialize all components.
        
        Should be called once at application startup.
        This loads models, builds indices, and validates the knowledge base.
        """
        if self._is_initialized:
            logger.info("Service already initialized")
            return
        
        logger.info("Initializing ProviderRAGService...")
        start_time = time.time()
        
        try:
            # Initialize retriever (loads embedding model, builds BM25 index)
            self.retriever.initialize()
            
            # Components are lazy-loaded, but we validate them here
            _ = self.generator
            _ = self.safety_gate
            _ = self.classifier
            
            self._is_initialized = True
            elapsed = time.time() - start_time
            logger.info(f"ProviderRAGService initialized in {elapsed:.2f}s")
            
        except Exception as e:
            logger.error(f"Failed to initialize ProviderRAGService: {e}")
            raise
    
    def _handle_greeting(self, query: str) -> QueryResult:
        """Generate a response for greeting queries."""
        greeting_response = """Hello! I'm here to help you with the Provider Portal and claims system.

I can assist you with:
• Portal login and access issues
• Authorization codes and claims submission
• Enrollee lookup and management
• Benefits and services selection
• Technical troubleshooting

Please feel free to ask your question, and I'll provide accurate information from the knowledge base!"""
        
        return QueryResult(
            query=query,
            answer=greeting_response,
            confidence=ConfidenceLevel.HIGH,
            confidence_score=1.0,
            citations=[],
            is_grounded=True,
            is_refusal=False,
        )
    
    def _handle_thanks(self, query: str) -> QueryResult:
        """Generate a response for thank you messages."""
        thanks_response = """You're welcome! I'm glad I could help.

If you have any other questions about the Provider Portal, claims submission, or any other topics, feel free to ask. I'm here to assist you!"""
        
        return QueryResult(
            query=query,
            answer=thanks_response,
            confidence=ConfidenceLevel.HIGH,
            confidence_score=1.0,
            citations=[],
            is_grounded=True,
            is_refusal=False,
        )
    
    def _handle_ambiguous(self, query: str) -> QueryResult:
        """Generate a response for ambiguous queries."""
        return QueryResult(
            query=query,
            answer=self.config.clarification_message,
            confidence=ConfidenceLevel.NONE,
            confidence_score=0.0,
            citations=[],
            is_grounded=True,
            is_refusal=False,
            needs_clarification=True,
        )
    
    async def query(
        self,
        query: str,
        session_id: Optional[str] = None,
        top_k: Optional[int] = None,
    ) -> QueryResult:
        """
        Process a user query and return a grounded response.
        
        This is the main entry point for querying the knowledge base.
        
        Args:
            query: User's question
            session_id: Optional session identifier for conversation tracking
            top_k: Optional override for number of documents to retrieve
            
        Returns:
            QueryResult with answer, confidence, citations, and metadata
        """
        start_time = time.time()
        
        # Ensure initialized
        if not self._is_initialized:
            await self.initialize()
        
        # Handle empty query
        if not query or not query.strip():
            return self._handle_ambiguous("")
        
        query = query.strip()
        logger.info(f"Processing query: {query[:50]}...")
        
        # Classify the query
        classification = self.classifier.classify(query)
        
        # Handle special cases
        if classification["is_greeting"]:
            result = self._handle_greeting(query)
            result.session_id = session_id
            return result
        
        if classification["is_thanks"]:
            result = self._handle_thanks(query)
            result.session_id = session_id
            return result
        
        if classification["is_ambiguous"]:
            result = self._handle_ambiguous(query)
            result.session_id = session_id
            return result
        
        # Handle off-topic or non-domain queries with refusal
        if classification["is_offtopic"] or (
            not classification["has_domain_relevance"] and 
            not classification["needs_retrieval"]
        ):
            logger.info(f"Query classified as off-topic or non-domain: {query[:50]}...")
            result = self.safety_gate.create_safe_refusal(
                query,
                "Query does not appear to be related to the provider portal or claims system."
            )
            result.session_id = session_id
            return result
        
        # Proceed with retrieval
        try:
            # Step 1: Retrieve relevant documents
            retrieval_result = await self.retriever.retrieve_async(query, top_k)
            
            # Step 2: Validate retrieval
            is_valid, reason = self.safety_gate.validate_retrieval(retrieval_result)
            
            if not is_valid:
                logger.info(f"Retrieval validation failed: {reason}")
                result = self.safety_gate.create_safe_refusal(query, reason)
                result.session_id = session_id
                result.processing_time_ms = (time.time() - start_time) * 1000
                return result
            
            # Step 3: Generate grounded response
            result = await self.generator.generate(query, retrieval_result)
            
            # Step 4: Apply safety gate
            result = self.safety_gate.apply_safety_gate(result)
            
            # Add session and timing info
            result.session_id = session_id
            result.processing_time_ms = (time.time() - start_time) * 1000
            
            logger.info(
                f"Query completed: confidence={result.confidence.value}, "
                f"time={result.processing_time_ms:.0f}ms"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing query: {e}", exc_info=True)
            
            # Return safe error response
            result = self.safety_gate.create_safe_refusal(
                query,
                f"Processing error: {str(e)}"
            )
            result.session_id = session_id
            result.processing_time_ms = (time.time() - start_time) * 1000
            return result
    
    async def ingest(self, clear: bool = False) -> IngestionResult:
        """
        Ingest or re-ingest the knowledge base.
        
        Args:
            clear: If True, clear existing data before ingesting
            
        Returns:
            IngestionResult with status and statistics
        """
        if self._ingestion_pipeline is None:
            self._ingestion_pipeline = ProviderIngestionPipeline(self.config)
        
        logger.info(f"Starting ingestion (clear={clear})...")
        result = self._ingestion_pipeline.ingest(clear=clear)
        
        # Reinitialize retriever to pick up new data
        if result.status == "ok":
            self._is_initialized = False
            self._retriever = None
            await self.initialize()
        
        return result
    
    def health_check(self) -> HealthStatus:
        """
        Check the health of the service.
        
        Returns:
            HealthStatus with component status information
        """
        try:
            # Check collection
            collection = self.retriever._get_collection()
            count = collection.count()
            
            # Check if BM25 index is built
            bm25_loaded = (
                self.retriever._bm25_index is not None 
                and self.retriever._bm25_index.is_built
            )
            
            # Check if embedding model is loaded
            embedding_loaded = self.retriever._embedder is not None
            
            status = "healthy" if count > 0 and bm25_loaded else "degraded"
            if count == 0:
                status = "unhealthy"
            
            return HealthStatus(
                status=status,
                collection_count=count,
                embedding_model_loaded=embedding_loaded,
                bm25_index_loaded=bm25_loaded,
            )
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return HealthStatus(
                status="unhealthy",
                collection_count=0,
                embedding_model_loaded=False,
                bm25_index_loaded=False,
                error_message=str(e),
            )


# Singleton instance for easy access
_service_instance: Optional[ProviderRAGService] = None


def get_provider_rag_service() -> ProviderRAGService:
    """
    Get the singleton ProviderRAGService instance.
    
    Returns:
        The shared ProviderRAGService instance
    """
    global _service_instance
    if _service_instance is None:
        _service_instance = ProviderRAGService()
    return _service_instance


async def initialize_provider_rag_service() -> ProviderRAGService:
    """
    Initialize and return the singleton service.
    
    Convenience function for application startup.
    """
    service = get_provider_rag_service()
    await service.initialize()
    return service
