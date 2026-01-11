"""
Provider Knowledge Base Router.

This module now uses the production-grade Provider RAG system
with hybrid retrieval and zero-hallucination guarantees.
"""

from app.providers_rag.router import router

# Re-export the router for backward compatibility
# The new router provides:
# - /ask - Query endpoint with confidence scoring
# - /stream - Streaming endpoint (compatibility)
# - /health - Health check endpoint
# - /ingest - Knowledge base ingestion trigger

__all__ = ["router"]

