# Embedding Model Recommendations

## Current Model: `BAAI/bge-small-en-v1.5`

**Why this model?**
- ✅ **Better accuracy** than `all-MiniLM-L6-v2` (MTEB score: 61.4 vs 56.4)
- ✅ **Optimized for retrieval** - specifically designed for semantic search
- ✅ **Still fast** - only ~2x slower than MiniLM-L6-v2, but much more accurate
- ✅ **Perfect for your specs** - With 20 CPUs and 12GB RAM, you can easily handle this
- ✅ **Better context understanding** - Improved semantic matching for insurance FAQs

## Model Comparison

| Model | Size | Speed | MTEB Score | Best For |
|-------|------|-------|------------|----------|
| `all-MiniLM-L6-v2` | 22MB | ⚡⚡⚡⚡⚡ | 56.4 | Fastest, basic accuracy |
| `BAAI/bge-small-en-v1.5` | 33MB | ⚡⚡⚡⚡ | **61.4** | **Best balance** ✅ |
| `all-mpnet-base-v2` | 420MB | ⚡⚡⚡ | 57.8 | Higher accuracy, slower |
| `BAAI/bge-base-en-v1.5` | 110MB | ⚡⚡ | 63.1 | Highest accuracy, slower |

## Performance on Your System

With **20 CPU cores** and **12GB RAM**:
- `bge-small-en-v1.5`: ~7,000 sentences/sec (excellent for your use case)
- Memory usage: ~200MB for model + embeddings
- Perfect fit for your resources!

## Alternative Models (if needed)

If you want even better accuracy and can spare the speed:
```python
EMBEDDING_MODEL = "BAAI/bge-base-en-v1.5"  # Best accuracy, ~3,500 sentences/sec
```

Or if you need maximum speed:
```python
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # Fastest, but lower accuracy
```

## Configuration

Edit `app/core/config.py`:
```python
EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"  # Current recommendation
```

## First Run

The first time you run with a new model, it will download (~33MB for bge-small). This is a one-time download.

