# Zamfara RAG System

Enterprise-grade Retrieval-Augmented Generation system for the Zamfara State FAQ Chatbot.

## Overview

This system provides accurate, auditable, and scalable FAQ responses using documents from the Zamfara directory. It's designed for government and administrative use cases with minimal hallucination and traceable answers.

## Architecture

```
zamfara_rag/
├── config/              # Configuration settings
│   └── settings.py      # Centralized configuration
├── preprocessing/       # Document processing
│   ├── loader.py        # Multi-format document loading
│   ├── cleaner.py       # Text cleaning and noise removal
│   ├── normalizer.py    # Text normalization
│   ├── chunker.py       # Semantic-aware chunking
│   └── metadata.py      # Metadata extraction
├── embeddings/          # Vector embeddings
│   └── generator.py     # Embedding generation
├── vector_store/        # Vector storage
│   └── store.py         # ChromaDB interface
├── retrieval/           # Document retrieval
│   └── retriever.py     # Query and re-ranking
├── generation/          # Answer generation
│   └── generator.py     # LLM-powered generation
├── evaluation/          # Quality assurance
│   └── hallucination_guard.py  # Verification
├── data/
│   └── raw_docs/        # Ingested document copies
└── main.py              # Main orchestration
```

## Quick Start

### 1. Ingest Documents

```bash
# From the ai/ directory
python -m zamfara_rag.main ingest --clear
```

### 2. Query the System

```bash
python -m zamfara_rag.main query "What is the policy on healthcare services?"
```

### 3. Interactive Mode

```bash
python -m zamfara_rag.main interactive
```

## Features

### Document Processing
- **Multi-format support**: PDF, DOCX, TXT, Markdown
- **OCR fallback**: Handles scanned documents
- **Text cleaning**: Removes headers, footers, page numbers
- **Normalization**: Standardizes formatting and abbreviations

### Semantic Chunking
- **Structure-aware**: Preserves section headings
- **Optimal size**: 300-700 tokens with 15% overlap
- **Self-contained**: Each chunk is meaningful standalone
- **Metadata-rich**: Full provenance tracking

### Metadata Design
Each chunk includes:
- `document_title`: Source document name
- `document_type`: policy, guideline, sop, faq, gazette, opg
- `department`: Inferred department/topic
- `section_heading`: Section context
- `file_path`: Full source path
- `last_updated`: Modification date

### Retrieval
- **Vector similarity**: Using BAAI/bge-small-en-v1.5 embeddings
- **Re-ranking**: Keyword overlap and phrase matching
- **Metadata filtering**: Filter by type, department
- **Deduplication**: Removes near-duplicate results

### Answer Generation
- **Grounded responses**: Uses only retrieved content
- **Inline citations**: [Document, Section] format
- **Formal tone**: Government-appropriate language
- **Safe fallback**: Clear "not available" response

### Hallucination Guard
- **Claim verification**: Checks each statement against sources
- **Citation validation**: Verifies cited sources exist
- **Suspicious content detection**: Flags specific numbers/dates not in sources
- **Regeneration/fallback**: Automatic recovery strategies

## Configuration

Key settings in `config/settings.py`:

```python
# Chunking
chunk_size_tokens = 500      # Target chunk size
chunk_overlap_percent = 0.15  # 15% overlap

# Retrieval
default_top_k = 5            # Documents to retrieve
min_similarity_threshold = 0.3
enable_reranking = True

# Generation
temperature = 0.1            # Low for factual accuracy
enable_verification = True
```

## API Integration

### Python API

```python
from zamfara_rag.main import ZamfaraRAGPipeline

# Initialize
pipeline = ZamfaraRAGPipeline()

# Ingest documents
stats = pipeline.ingest(clear=True)

# Query
result = await pipeline.query("What are the health policies?")
print(result.answer)
print(result.citations)
```

### Adding to FastAPI

```python
from fastapi import FastAPI
from zamfara_rag.main import ZamfaraRAGPipeline

app = FastAPI()
pipeline = ZamfaraRAGPipeline()

@app.post("/ask")
async def ask_question(question: str):
    result = await pipeline.query(question)
    return result.to_dict()
```

## Best Practices

### Document Updates
1. Add new documents to the source directory
2. Run incremental ingestion: `python -m zamfara_rag.main ingest`
3. For major changes, clear and re-ingest: `--clear`

### Re-indexing
- Schedule periodic re-indexing (weekly/monthly)
- Re-index after document structure changes
- Monitor vector store statistics

### Version Control
- Keep document versions in separate folders
- Use meaningful filenames with dates
- Maintain a document changelog

### Improving Accuracy
1. **Add curated Q&A**: Create `.jsonl` files with common questions
2. **Tune chunk size**: Adjust based on document type
3. **Review logs**: Check which queries return fallbacks
4. **Feedback loop**: Track user satisfaction

## Constraints

- ✅ Only uses Zamfara folder content
- ✅ No external knowledge
- ✅ Auditable and explainable
- ✅ Government-appropriate tone
- ❌ No hallucinated policies
- ❌ No speculation

## Troubleshooting

### No results returned
- Check if vector store is populated: `python -m zamfara_rag.main stats`
- Verify documents exist in source directory
- Lower `min_similarity_threshold` temporarily

### Poor answer quality
- Ensure documents are properly formatted
- Check for OCR errors in scanned documents
- Adjust chunk size for your content

### Slow performance
- Reduce `top_k` for faster retrieval
- Use smaller embedding model
- Enable caching for repeated queries

## Dependencies

- sentence-transformers>=2.6.0
- chromadb>=0.5.0
- pdfplumber>=0.11.0
- python-docx>=1.1.0
- httpx>=0.27.0

## License

Internal use only - Zamfara State Government




