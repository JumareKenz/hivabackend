# MCP Migration Quick Reference

Quick reference guide for the Admin_chat to MCP migration.

---

## Migration Checklist

### Pre-Migration
- [ ] MCP SDK installed
- [ ] Validation script passes
- [ ] Database connection verified
- [ ] Backup created
- [ ] Feature flags configured

### Migration
- [ ] MCP server implemented
- [ ] Resources registered
- [ ] Tools implemented
- [ ] Prompts created
- [ ] Integration complete

### Post-Migration
- [ ] Validation passed
- [ ] Performance benchmarks met
- [ ] Documentation updated
- [ ] Team trained
- [ ] Monitoring in place

---

## Key Commands

### Setup
```bash
# Install MCP SDK
pip install mcp

# Run validation
python mcp_server/validation/validate_migration.py

# Test server
python -m mcp_server.server
```

### Configuration
```bash
# Enable MCP mode
USE_MCP_MODE=true
MCP_GRADUAL_ROLLOUT=0.1  # Start with 10%

# Full rollout
MCP_GRADUAL_ROLLOUT=1.0
```

### Rollback
```bash
# Immediate rollback
USE_MCP_MODE=false

# Or reduce rollout
MCP_GRADUAL_ROLLOUT=0.0
```

---

## MCP Resources

| URI | Description |
|-----|-------------|
| `schema://database/tables` | All tables schema |
| `schema://database/{table}` | Specific table schema |
| `data://database/{table}` | Table data |
| `context://session/{id}` | Conversation context |

---

## MCP Tools

| Tool | Purpose | Key Parameters |
|------|---------|----------------|
| `generate_sql` | Generate SQL from NL | `query`, `session_id` |
| `execute_query` | Execute SQL query | `sql`, `params` |
| `get_schema` | Get schema info | `table_name` |
| `create_visualization` | Create charts | `data`, `chart_type` |
| `manage_conversation` | Manage context | `session_id`, `action` |

---

## Common Issues

### Server Won't Start
```bash
# Check installation
pip list | grep mcp

# Check database
python test_db_connection.py

# Check logs
tail -f logs/mcp_server.log
```

### Queries Failing
```bash
# Validate SQL generation
python -c "
import asyncio
from mcp_server.server import mcp_server
async def test():
    await mcp_server.initialize()
    result = await mcp_server._handle_generate_sql_tool({
        'query': 'Show me total claims'
    })
    print(result)
asyncio.run(test())
"
```

### Performance Issues
```bash
# Check connection pool
# Review query cache
# Monitor LLM service latency
```

---

## File Locations

| File | Purpose |
|------|---------|
| `mcp_server/server.py` | MCP server implementation |
| `mcp_server/config/mcp_config.json` | Server configuration |
| `mcp_server/validation/validate_migration.py` | Validation scripts |
| `docs/MCP_MIGRATION_STRATEGY.md` | Full migration strategy |
| `docs/MCP_IMPLEMENTATION_GUIDE.md` | Implementation guide |

---

## Validation Results

After running validation, check:
- `mcp_server/validation/validation_report.json`
- Overall status (passed/failed)
- Error count
- Warning count
- Performance metrics

---

## Rollout Schedule

| Phase | Rollout % | Duration | Validation |
|-------|-----------|----------|------------|
| 1 | 10% | 24 hours | Monitor errors, performance |
| 2 | 25% | 24 hours | Continue monitoring |
| 3 | 50% | 24 hours | Monitor user feedback |
| 4 | 75% | 24 hours | Final validation |
| 5 | 100% | Ongoing | Full production |

---

## Support Contacts

- **Migration Strategy**: See `MCP_MIGRATION_STRATEGY.md`
- **Implementation**: See `MCP_IMPLEMENTATION_GUIDE.md`
- **Server Docs**: See `mcp_server/README.md`
- **Validation**: Run `validate_migration.py`

---

## Quick Links

- [MCP Specification](https://modelcontextprotocol.io/specification/2024-11-05/index)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Migration Strategy](./MCP_MIGRATION_STRATEGY.md)
- [Implementation Guide](./MCP_IMPLEMENTATION_GUIDE.md)


