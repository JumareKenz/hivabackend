# Vanna AI Integration Guide

## Overview

Vanna AI has been integrated into the HIVA Admin Chat service to provide enhanced SQL generation capabilities with:

- **RAG (Retrieval-Augmented Generation)**: Uses context from database schema and example queries
- **Learning Capabilities**: Learns from successful queries to improve over time
- **Better Accuracy**: Improved SQL generation for complex queries
- **Context Awareness**: Better understanding of database relationships and patterns

## Architecture

### Components

1. **VannaService** (`app/services/vanna_service.py`)
   - Custom Vanna model implementation using Groq API
   - Manages training data (DDL, examples, documentation)
   - Provides SQL generation with RAG

2. **SQLGenerator** (`app/services/sql_generator.py`)
   - Updated to use Vanna AI with fallback to legacy mode
   - Automatic training on successful queries
   - Seamless integration with existing codebase

3. **Training Script** (`train_vanna.py`)
   - Command-line tool for training Vanna
   - Supports schema training and example queries

## Configuration

### Environment Variables

Add to your `.env` file:

```bash
# Vanna AI Configuration (optional - defaults shown)
USE_VANNA_AI=true                    # Enable Vanna AI (default: true)
VANNA_FALLBACK_TO_LEGACY=true        # Fallback to legacy if Vanna fails (default: true)
```

### Settings

In `app/core/config.py`:

```python
USE_VANNA_AI: bool = True  # Enable/disable Vanna AI
VANNA_FALLBACK_TO_LEGACY: bool = True  # Fallback to legacy SQL generator
```

## Installation

1. **Install Dependencies**

```bash
cd /root/hiva/services/ai/admin_chat
pip install -r requirements.txt
```

This will install `vanna>=0.5.0` along with other dependencies.

2. **Initialize Vanna**

Vanna will automatically initialize on service startup if:
- `USE_VANNA_AI=true`
- Database is configured and available
- Vanna package is installed

## Training

### Initial Training

Train Vanna on your database schema:

```bash
cd /root/hiva/services/ai/admin_chat
python train_vanna.py
```

This will:
- Connect to your database
- Extract schema information (tables, columns, relationships)
- Train Vanna on DDL (Data Definition Language)
- Save training data to `vanna_data/training_data.json`

### Training on Examples

Train Vanna on example question-SQL pairs:

```bash
python train_vanna.py --examples
```

This adds common query patterns to Vanna's knowledge base.

### Adding Custom Examples

Add specific examples for your use case:

```bash
python train_vanna.py --add-example "show me claims by status" "SELECT CASE WHEN status = 0 THEN 'Pending' ... END as status_name, COUNT(*) FROM claims GROUP BY status"
```

With optional tag:

```bash
python train_vanna.py --add-example "show me claims by status" "SELECT ..." --tag "status_aggregation"
```

## Usage

### Automatic Usage

Vanna AI is automatically used when:
1. `USE_VANNA_AI=true` in config
2. Vanna is successfully initialized
3. A SQL generation request is made

The system will:
1. Try Vanna AI first
2. Fall back to legacy SQL generator if Vanna fails (if `VANNA_FALLBACK_TO_LEGACY=true`)

### API Response

The API response includes a `source` field indicating which generator was used:

```json
{
  "sql": "SELECT ...",
  "explanation": "...",
  "confidence": 0.9,
  "source": "vanna"  // or "legacy"
}
```

### Automatic Learning

Successful queries are automatically trained to Vanna (async, non-blocking):
- Helps Vanna learn from real usage patterns
- Improves accuracy over time
- No manual intervention needed

## Training Data Storage

Training data is stored in:
```
/root/hiva/services/ai/admin_chat/vanna_data/training_data.json
```

This file contains:
- **DDL**: Database schema (CREATE TABLE statements)
- **question_sql**: Example question-SQL pairs
- **documentation**: Additional documentation about the database

## Benefits

### 1. Improved Accuracy
- Better understanding of database relationships
- Context-aware SQL generation
- Learns from successful patterns

### 2. RAG-Based Generation
- Uses relevant schema information
- References example queries
- Better handling of complex queries

### 3. Continuous Learning
- Automatically learns from successful queries
- Improves over time without manual intervention
- Adapts to your specific database patterns

### 4. Backward Compatibility
- Seamless fallback to legacy generator
- No breaking changes to existing code
- Can be disabled via configuration

## Troubleshooting

### Vanna Not Initializing

1. **Check Dependencies**
   ```bash
   pip list | grep vanna
   ```
   Should show `vanna>=0.5.0`

2. **Check Database Connection**
   ```bash
   python -c "from app.services.database_service import database_service; import asyncio; asyncio.run(database_service.initialize()); print('DB OK' if database_service.pool else 'DB Not Available')"
   ```

3. **Check Logs**
   Look for initialization messages in service logs:
   - `✅ Vanna AI initialized successfully`
   - `⚠️  Vanna AI initialization failed`

### Poor SQL Generation

1. **Train on More Examples**
   ```bash
   python train_vanna.py --examples
   ```

2. **Add Specific Examples**
   For queries that fail, add them as examples:
   ```bash
   python train_vanna.py --add-example "your question" "correct SQL"
   ```

3. **Check Training Data**
   ```bash
   cat vanna_data/training_data.json
   ```
   Verify schema and examples are present.

### Fallback to Legacy

If Vanna consistently falls back to legacy:
1. Check error logs for specific issues
2. Verify database schema is accessible
3. Ensure Groq API is working (used by Vanna)
4. Consider disabling Vanna temporarily: `USE_VANNA_AI=false`

## Performance

- **Initialization**: ~2-5 seconds on first startup
- **SQL Generation**: Similar to legacy (uses same Groq API)
- **Training**: Non-blocking, runs in background
- **Storage**: Training data is small (~few KB to MB)

## Best Practices

1. **Regular Training**: Run `train_vanna.py --examples` periodically
2. **Add Examples**: Add successful query patterns as examples
3. **Monitor**: Check `source` field in API responses
4. **Documentation**: Add database documentation via `train_on_documentation()`

## Advanced Usage

### Programmatic Training

```python
from app.services.vanna_service import vanna_service

# Train on example
await vanna_service.train_on_example(
    question="show me claims by status",
    sql="SELECT ...",
    tag="status_aggregation"
)

# Train on DDL
await vanna_service.train_on_ddl("CREATE TABLE ...")

# Train on documentation
await vanna_service.train_on_documentation("Claims table contains...")
```

### Custom Vanna Model

The implementation uses a custom `CustomVannaModel` that:
- Works with Groq API (instead of OpenAI)
- Stores training data locally
- Integrates with existing database service

## Migration from Legacy

The integration is **backward compatible**:
- Legacy generator still works
- Vanna can be enabled/disabled via config
- No code changes required in API endpoints
- Gradual migration supported

## Support

For issues or questions:
1. Check logs: `tail -f server.log`
2. Run training script: `python train_vanna.py --examples`
3. Verify configuration: Check `.env` and `config.py`
4. Test database connection: Use health endpoint

## Future Enhancements

Potential improvements:
- [ ] Vector database for better RAG
- [ ] Query validation and correction
- [ ] Performance metrics and analytics
- [ ] Multi-database support
- [ ] Query explanation generation

