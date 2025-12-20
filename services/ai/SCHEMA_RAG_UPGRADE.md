# Schema-RAG Upgrade Plan

## Current Implementation

The Schema-RAG service (`app/services/schema_rag_service.py`) currently uses:
- **Dictionary-based lookup** (no vector search)
- **Simple substring matching**
- **In-memory entity cache**

## Available RAG Libraries

Your codebase already has:
- ✅ **ChromaDB** - Vector database (`chromadb`)
- ✅ **SentenceTransformers** - Embeddings (`sentence_transformers`)
- ✅ Model: `BAAI/bge-small-en-v1.5`

## Recommendation

**Option 1: Keep Current Implementation** (Recommended for now)
- ✅ Fast (no embedding computation)
- ✅ Simple and reliable
- ✅ Works well for exact matches (state names, etc.)
- ❌ Limited to exact/substring matching

**Option 2: Upgrade to Vector RAG** (For better fuzzy matching)
- ✅ Better fuzzy matching (e.g., "Kogi State" → "Kogi")
- ✅ Semantic similarity (e.g., "Federal Capital Territory" → "FCT")
- ✅ Can handle typos and variations
- ❌ Slower (embedding computation)
- ❌ More complex

## Current Status

The Schema-RAG service works well for:
- State name mapping (exact matches)
- Provider name mapping (substring matching)
- Status value mapping (exact matches)

For these use cases, the current dictionary-based approach is sufficient and faster.

## If You Want Vector RAG

I can upgrade the Schema-RAG service to use ChromaDB + SentenceTransformers for:
- Better fuzzy matching
- Semantic similarity
- Typo tolerance
- More sophisticated entity resolution

Would you like me to upgrade it to use vector RAG?

