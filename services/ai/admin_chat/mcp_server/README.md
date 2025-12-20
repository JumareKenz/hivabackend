# Admin Chat MCP Server

Model Context Protocol (MCP) server implementation for the Admin Chat Service, enabling natural language to SQL analytics through standardized MCP interfaces.

## Overview

This MCP server provides:
- **Resources**: Database schema, table data, conversation context
- **Tools**: SQL generation, query execution, visualization, conversation management
- **Prompts**: Predefined templates for SQL generation and data summarization

## Architecture

```
mcp_server/
├── server.py              # Main MCP server implementation
├── config/
│   └── mcp_config.json   # MCP server configuration
├── validation/
│   └── validate_migration.py  # Migration validation scripts
└── README.md             # This file
```

## Installation

### Prerequisites

```bash
# Install MCP SDK
pip install mcp

# Or from source
pip install git+https://github.com/modelcontextprotocol/python-sdk.git
```

### Setup

1. Ensure Admin Chat service dependencies are installed
2. Configure database connection in `.env` file
3. Run validation script to verify setup

```bash
cd /root/hiva/services/ai/admin_chat
python mcp_server/validation/validate_migration.py
```

## Usage

### Running the MCP Server

```bash
# Via stdio (for MCP clients)
python -m mcp_server.server

# Or as a module
python mcp_server/server.py
```

### MCP Client Integration

The server can be integrated with MCP-compatible clients (Claude Desktop, Cursor, etc.) by configuring the server path in the client's MCP settings.

Example configuration for Claude Desktop:

```json
{
  "mcpServers": {
    "admin-chat": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/root/hiva/services/ai/admin_chat"
    }
  }
}
```

## Resources

### Schema Resources

- `schema://database/tables` - Complete database schema
- `schema://database/{table_name}` - Schema for specific table

### Data Resources

- `data://database/{table_name}?limit=100` - Table data with pagination

### Context Resources

- `context://session/{session_id}` - Conversation context for a session

## Tools

### generate_sql

Generate SQL from natural language query.

**Parameters:**
- `query` (string, required): Natural language query
- `session_id` (string, optional): Session ID for context
- `refine_query` (boolean, optional): Use conversation history

**Example:**
```json
{
  "name": "generate_sql",
  "arguments": {
    "query": "Show me total number of claims",
    "session_id": "session-123"
  }
}
```

### execute_query

Execute a SQL SELECT query and return results with visualization.

**Parameters:**
- `sql` (string, required): SQL SELECT query
- `params` (object, optional): Query parameters

**Example:**
```json
{
  "name": "execute_query",
  "arguments": {
    "sql": "SELECT COUNT(*) as count FROM claims"
  }
}
```

### get_schema

Get database schema information.

**Parameters:**
- `table_name` (string, optional): Specific table name

### create_visualization

Create visualization from query results.

**Parameters:**
- `data` (array, required): Query results data
- `chart_type` (string, optional): Chart type (bar, line, pie, table, auto)

### manage_conversation

Manage conversation history and context.

**Parameters:**
- `session_id` (string, required): Session ID
- `action` (string, required): Action (get_history, clear_history, get_summary)

## Prompts

### sql_generation

Generate SQL from natural language with schema context.

**Variables:**
- `query`: Natural language query
- `schema_context`: Optional schema context

### data_summary

Generate natural language summary of query results.

**Variables:**
- `data`: Query results data
- `query`: Original query

## Validation

Run migration validation:

```bash
python mcp_server/validation/validate_migration.py
```

This validates:
- Schema integrity
- Data integrity
- Functional correctness
- Performance benchmarks
- Semantic consistency

## Configuration

Edit `config/mcp_config.json` to customize:
- Resource cache TTLs
- Tool timeouts
- Performance limits
- Security settings

## Security

- All queries are validated to be read-only (SELECT only)
- SQL injection protection via parameterized queries
- Connection pooling with read-only transactions
- API key authentication (via existing Admin Chat auth)

## Performance

- Schema caching (1 hour TTL)
- Query result caching (configurable)
- Connection pooling
- Optimized SQL generation for common queries

## Troubleshooting

### Server won't start

1. Check database connection in `.env`
2. Verify MCP SDK installation
3. Check Python path and imports

### Queries failing

1. Verify database is accessible
2. Check SQL generation logs
3. Validate query syntax

### Performance issues

1. Check database connection pool size
2. Review query execution times
3. Enable query caching

## Migration Status

See `docs/MCP_MIGRATION_STRATEGY.md` for complete migration plan and status.

## Support

For issues or questions:
1. Check validation report: `mcp_server/validation/validation_report.json`
2. Review logs
3. Consult migration strategy document


