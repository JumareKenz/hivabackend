# MCP Implementation Guide
## Step-by-Step Migration Implementation

This guide provides detailed implementation steps for migrating Admin_chat to MCP format.

---

## Prerequisites

### Required Software
- Python 3.9+
- MCP SDK: `pip install mcp` or from source
- All existing Admin_chat dependencies
- Database access (PostgreSQL or MySQL)

### Required Knowledge
- Understanding of MCP protocol
- Familiarity with Admin_chat architecture
- Python async/await patterns
- Database query optimization

---

## Phase 1: Foundation Setup

### Step 1.1: Install MCP SDK

```bash
cd /root/hiva/services/ai/admin_chat

# Option 1: Install from PyPI (when available)
pip install mcp

# Option 2: Install from source
pip install git+https://github.com/modelcontextprotocol/python-sdk.git

# Verify installation
python -c "import mcp; print(mcp.__version__)"
```

### Step 1.2: Create MCP Server Structure

```bash
mkdir -p mcp_server/{config,validation,prompts}
touch mcp_server/__init__.py
touch mcp_server/server.py
touch mcp_server/config/mcp_config.json
touch mcp_server/validation/validate_migration.py
```

### Step 1.3: Verify Existing Services

```bash
# Test database connection
python test_db_connection.py

# Test SQL generation
python -c "
import asyncio
from app.services.sql_generator import sql_generator
async def test():
    result = await sql_generator.generate_sql('Show me total claims')
    print(result)
asyncio.run(test())
"
```

### Step 1.4: Run Initial Validation

```bash
python mcp_server/validation/validate_migration.py
```

Review the validation report and address any critical errors before proceeding.

---

## Phase 2: MCP Server Implementation

### Step 2.1: Implement Basic Server

The server implementation is provided in `mcp_server/server.py`. Review and customize as needed:

```python
# Key components to verify:
# 1. Server initialization
# 2. Resource registration
# 3. Tool registration
# 4. Prompt registration
# 5. Handler implementations
```

### Step 2.2: Test Server Startup

```bash
# Test server initialization
python -c "
import asyncio
from mcp_server.server import mcp_server
async def test():
    await mcp_server.initialize()
    print('Server initialized successfully')
asyncio.run(test())
"
```

### Step 2.3: Test Resource Handlers

```python
# Test schema resource
python -c "
import asyncio
from mcp_server.server import mcp_server
async def test():
    await mcp_server.initialize()
    result = await mcp_server._handle_schema_resource('schema://database/tables')
    print('Schema resource:', result[:200])
asyncio.run(test())
"
```

### Step 2.4: Test Tool Handlers

```python
# Test SQL generation tool
python -c "
import asyncio
from mcp_server.server import mcp_server
async def test():
    await mcp_server.initialize()
    result = await mcp_server._handle_generate_sql_tool({
        'query': 'Show me total claims'
    })
    print('SQL Generation:', result)
asyncio.run(test())
"
```

---

## Phase 3: Integration with Existing API

### Step 3.1: Create MCP Client Wrapper

Create `app/services/mcp_client.py`:

```python
"""
MCP Client wrapper for existing API endpoints
"""
from typing import Dict, Any, Optional
import asyncio
from mcp_server.server import mcp_server

class MCPClient:
    """Client wrapper for MCP server"""
    
    async def generate_sql(self, query: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Generate SQL via MCP"""
        await mcp_server.initialize()
        result = await mcp_server._handle_generate_sql_tool({
            "query": query,
            "session_id": session_id
        })
        return result
    
    async def execute_query(self, sql: str) -> Dict[str, Any]:
        """Execute query via MCP"""
        await mcp_server.initialize()
        result = await mcp_server._handle_execute_query_tool({
            "sql": sql
        })
        return result

mcp_client = MCPClient()
```

### Step 3.2: Add Feature Flag

Update `app/core/config.py`:

```python
class AdminSettings(BaseSettings):
    # ... existing settings ...
    
    # MCP Migration Feature Flag
    USE_MCP_MODE: bool = False  # Set to True to enable MCP mode
    MCP_GRADUAL_ROLLOUT: float = 0.0  # Percentage of traffic (0.0 to 1.0)
```

### Step 3.3: Update API Endpoint

Modify `app/api/v1/admin.py` to support dual mode:

```python
from app.core.config import settings
from app.services.mcp_client import mcp_client
import random

@router.post("/admin/query", response_model=AdminQueryResponse)
async def admin_query_data(
    request: AdminQueryRequest,
    user_info: Dict[str, Any] = Depends(admin_auth.require_admin)
):
    """Admin Insights with MCP support"""
    
    # Feature flag: Use MCP if enabled
    use_mcp = settings.USE_MCP_MODE and (
        settings.MCP_GRADUAL_ROLLOUT >= 1.0 or
        random.random() < settings.MCP_GRADUAL_ROLLOUT
    )
    
    if use_mcp:
        # Use MCP mode
        return await _handle_query_via_mcp(request)
    else:
        # Use legacy mode
        return await _handle_query_legacy(request)

async def _handle_query_via_mcp(request: AdminQueryRequest):
    """Handle query via MCP"""
    session_id = request.session_id or str(uuid.uuid4())
    
    # Generate SQL via MCP
    sql_result = await mcp_client.generate_sql(
        query=request.query,
        session_id=session_id
    )
    
    # Execute query via MCP
    execution_result = await mcp_client.execute_query(sql_result["sql"])
    
    # Format response
    return AdminQueryResponse(
        success=True,
        data=execution_result["data"],
        sql=sql_result["sql"],
        sql_explanation=sql_result["explanation"],
        visualization=execution_result["visualization"],
        summary=execution_result["summary"],
        session_id=session_id,
        confidence=sql_result["confidence"],
        row_count=execution_result["row_count"]
    )
```

---

## Phase 4: Data Migration

### Step 4.1: Backup Existing Data

```bash
# Backup conversation history (if persisted)
# Backup configuration files
# Backup database schema (if needed)

# Create backup directory
mkdir -p backups/pre_migration_$(date +%Y%m%d)
cp -r app/services/conversation_manager.py backups/pre_migration_$(date +%Y%m%d)/
```

### Step 4.2: Migrate Conversation Storage

If conversation history needs persistence:

```python
# Option 1: Add database persistence
# Option 2: Add Redis cache
# Option 3: Keep in-memory (current)

# Example: Add Redis persistence
import redis.asyncio as redis

class PersistentConversationManager(ConversationManager):
    def __init__(self, redis_client):
        super().__init__()
        self.redis = redis_client
    
    async def add_message(self, session_id, role, content, metadata=None):
        # Save to Redis
        await self.redis.setex(
            f"conversation:{session_id}",
            86400,  # 24 hours
            json.dumps(self._conversations[session_id])
        )
        super().add_message(session_id, role, content, metadata)
```

### Step 4.3: Validate Data Migration

```bash
# Run comprehensive validation
python mcp_server/validation/validate_migration.py

# Review validation report
cat mcp_server/validation/validation_report.json | jq
```

---

## Phase 5: Testing & Validation

### Step 5.1: Unit Tests

Create `tests/test_mcp_server.py`:

```python
import pytest
import asyncio
from mcp_server.server import mcp_server

@pytest.mark.asyncio
async def test_sql_generation():
    await mcp_server.initialize()
    result = await mcp_server._handle_generate_sql_tool({
        "query": "Show me total claims"
    })
    assert result["success"] == True
    assert "SELECT" in result["sql"].upper()
    assert result["confidence"] > 0.5

@pytest.mark.asyncio
async def test_query_execution():
    await mcp_server.initialize()
    result = await mcp_server._handle_execute_query_tool({
        "sql": "SELECT COUNT(*) as count FROM claims"
    })
    assert result["success"] == True
    assert "data" in result
    assert result["row_count"] >= 0
```

### Step 5.2: Integration Tests

Test end-to-end flow:

```python
@pytest.mark.asyncio
async def test_end_to_end_query():
    # Generate SQL
    sql_result = await mcp_client.generate_sql("Show me total claims")
    
    # Execute query
    exec_result = await mcp_client.execute_query(sql_result["sql"])
    
    # Verify results
    assert exec_result["success"] == True
    assert len(exec_result["data"]) > 0
```

### Step 5.3: Performance Testing

```python
import time

async def benchmark_mcp():
    start = time.time()
    result = await mcp_client.generate_sql("Show me total claims")
    generation_time = time.time() - start
    
    start = time.time()
    exec_result = await mcp_client.execute_query(result["sql"])
    execution_time = time.time() - start
    
    print(f"Generation: {generation_time:.2f}s")
    print(f"Execution: {execution_time:.2f}s")
    print(f"Total: {generation_time + execution_time:.2f}s")
```

### Step 5.4: Parallel Execution Testing

Compare legacy vs MCP:

```python
async def compare_legacy_vs_mcp(query: str):
    # Legacy
    legacy_start = time.time()
    legacy_result = await sql_generator.generate_sql(query)
    legacy_time = time.time() - legacy_start
    
    # MCP
    mcp_start = time.time()
    mcp_result = await mcp_client.generate_sql(query)
    mcp_time = time.time() - mcp_start
    
    # Compare
    assert legacy_result["sql"] == mcp_result["sql"]
    assert abs(legacy_time - mcp_time) / legacy_time < 0.1  # Within 10%
```

---

## Phase 6: Gradual Rollout

### Step 6.1: Enable for 10% of Traffic

```bash
# Update .env
USE_MCP_MODE=true
MCP_GRADUAL_ROLLOUT=0.1
```

### Step 6.2: Monitor Metrics

- Error rates
- Response times
- Query accuracy
- User feedback

### Step 6.3: Gradually Increase

```bash
# After 24 hours of stable operation at 10%
MCP_GRADUAL_ROLLOUT=0.25  # 25%

# After another 24 hours
MCP_GRADUAL_ROLLOUT=0.50  # 50%

# Continue until 100%
MCP_GRADUAL_ROLLOUT=1.0  # 100%
```

### Step 6.4: Rollback if Needed

```bash
# Immediate rollback
USE_MCP_MODE=false

# Or reduce rollout
MCP_GRADUAL_ROLLOUT=0.0
```

---

## Phase 7: Production Hardening

### Step 7.1: Add Monitoring

```python
# Add metrics collection
from prometheus_client import Counter, Histogram

mcp_queries_total = Counter('mcp_queries_total', 'Total MCP queries')
mcp_query_duration = Histogram('mcp_query_duration_seconds', 'MCP query duration')

@mcp_query_duration.time()
async def handle_query(query):
    mcp_queries_total.inc()
    # ... query handling
```

### Step 7.2: Add Logging

```python
import logging

logger = logging.getLogger("mcp_server")

async def handle_query(query):
    logger.info(f"Processing query: {query}")
    try:
        result = await process_query(query)
        logger.info(f"Query successful: {result['sql'][:100]}")
        return result
    except Exception as e:
        logger.error(f"Query failed: {str(e)}", exc_info=True)
        raise
```

### Step 7.3: Add Error Handling

```python
async def handle_query_with_retry(query, max_retries=2):
    for attempt in range(max_retries + 1):
        try:
            return await handle_query(query)
        except Exception as e:
            if attempt == max_retries:
                # Fallback to legacy
                logger.warning(f"MCP failed, falling back to legacy: {e}")
                return await legacy_handle_query(query)
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
```

---

## Troubleshooting

### Issue: MCP Server Won't Start

**Symptoms**: Server initialization fails

**Solutions**:
1. Check MCP SDK installation: `pip list | grep mcp`
2. Verify database connection
3. Check Python version: `python --version` (requires 3.9+)
4. Review error logs

### Issue: Queries Failing

**Symptoms**: SQL generation or execution errors

**Solutions**:
1. Verify database schema is accessible
2. Check SQL validation logic
3. Review LLM service (RunPod) status
4. Check query timeout settings

### Issue: Performance Degradation

**Symptoms**: Slower response times

**Solutions**:
1. Enable query caching
2. Optimize schema loading
3. Review database connection pool size
4. Check LLM service latency

### Issue: Data Inconsistencies

**Symptoms**: Different results between legacy and MCP

**Solutions**:
1. Run validation script
2. Compare SQL queries
3. Check conversation context
4. Verify schema cache freshness

---

## Next Steps

1. **Complete Implementation**: Finish all phases
2. **Documentation**: Update API docs with MCP endpoints
3. **Training**: Train team on MCP architecture
4. **Monitoring**: Set up dashboards and alerts
5. **Optimization**: Fine-tune based on production metrics

---

## References

- [MCP Specification](https://modelcontextprotocol.io/specification/2024-11-05/index)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Migration Strategy Document](./MCP_MIGRATION_STRATEGY.md)
- [MCP Server README](../mcp_server/README.md)

---

## Support

For questions or issues:
1. Review validation reports
2. Check troubleshooting section
3. Consult migration strategy document
4. Review MCP server logs


