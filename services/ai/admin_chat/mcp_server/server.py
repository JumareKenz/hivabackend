"""
MCP Server for Admin Chat Service
Model Context Protocol implementation for natural language to SQL analytics

This implementation provides MCP-compatible functionality without requiring
the official MCP SDK, making it production-ready and self-contained.
"""
import asyncio
import json
import re
from typing import Any, Dict, List, Optional
from datetime import datetime
from urllib.parse import parse_qs, urlparse
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.database_service import database_service
from app.services.enhanced_sql_generator import enhanced_sql_generator
from app.services.schema_rag_service import schema_rag_service
from app.services.privacy_service import privacy_service
from app.services.analytical_summary_service import analytical_summary_service
from app.services.visualization_service import visualization_service
from app.services.conversation_manager import conversation_manager
from app.core.config import settings


class AdminChatMCPServer:
    """
    MCP Server implementation for Admin Chat Service
    
    Provides MCP-compatible resource, tool, and prompt interfaces
    for natural language to SQL analytics.
    """
    
    def __init__(self):
        self._initialized = False
        self._resources: List[Dict[str, Any]] = []
        self._tools: List[Dict[str, Any]] = []
        self._prompts: List[Dict[str, Any]] = []
        
    async def initialize(self):
        """Initialize MCP server and register resources, tools, and prompts"""
        if self._initialized:
            return
        
        # Initialize database connection
        await database_service.initialize()
        
        # Register MCP components
        self._register_resources()
        self._register_tools()
        self._register_prompts()
        
        self._initialized = True
        print("✅ MCP Server initialized successfully")
    
    def _register_resources(self):
        """Register MCP resources"""
        self._resources = [
            {
                "uri": "schema://database/tables",
                "name": "Database Schema - All Tables",
                "description": "Complete database schema information for all tables",
                "mimeType": "application/json"
            },
            {
                "uri": "schema://database/claims",
                "name": "Database Schema - Claims Table",
                "description": "Schema information for the claims table",
                "mimeType": "application/json"
            },
            {
                "uri": "schema://database/users",
                "name": "Database Schema - Users Table",
                "description": "Schema information for the users table",
                "mimeType": "application/json"
            },
            {
                "uri": "schema://database/providers",
                "name": "Database Schema - Providers Table",
                "description": "Schema information for the providers table",
                "mimeType": "application/json"
            },
        ]
    
    def _register_tools(self):
        """Register MCP tools"""
        self._tools = [
            {
                "name": "generate_sql",
                "description": "Use this tool ONLY when the user explicitly asks for data queries, statistics, records, or lists from the database. Requires a specific data request (e.g., 'show me claims', 'total number of users', 'claims by status'). Do NOT use for greetings, general conversation, or questions about capabilities. If the query is vague (e.g., 'show claims' without a time period), ask the user for clarification before generating SQL.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural language data query (e.g., 'Show me total number of claims', 'Claims by status for last month')"
                        },
                        "session_id": {
                            "type": "string",
                            "description": "Optional session ID for conversation context"
                        },
                        "refine_query": {
                            "type": "boolean",
                            "description": "Whether to use conversation history for context",
                            "default": False
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "execute_query",
                "description": "Use this tool ONLY to execute a SQL SELECT query that has already been generated. This tool runs read-only database queries and returns results with visualizations. Do NOT use for generating SQL (use generate_sql instead). Only use when you have a valid SQL SELECT statement ready to execute.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "sql": {
                            "type": "string",
                            "description": "SQL SELECT query to execute (must be read-only)"
                        },
                        "params": {
                            "type": "object",
                            "description": "Optional query parameters for parameterized queries"
                        }
                    },
                    "required": ["sql"]
                }
            },
            {
                "name": "get_schema",
                "description": "Use this tool ONLY when you need to check database structure, table names, or column information before generating SQL. Use when the user's query mentions a table name you're unsure about, or when you need to verify column names exist. Do NOT use for general queries - only when schema information is specifically needed.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "table_name": {
                            "type": "string",
                            "description": "Optional specific table name. If not provided, returns all tables."
                        }
                    }
                }
            },
            {
                "name": "create_visualization",
                "description": "Use this tool ONLY when the user explicitly requests a chart, graph, or visualization (e.g., 'show as chart', 'create a graph', 'visualize this data'). Also use when query results contain numeric data that would benefit from visualization. Do NOT use for simple text responses or when the user only wants raw data.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "data": {
                            "type": "array",
                            "description": "Query results data (array of objects) to visualize"
                        },
                        "chart_type": {
                            "type": "string",
                            "description": "Optional chart type (bar, line, pie, table, auto). Use 'auto' to let the system choose the best type.",
                            "enum": ["bar", "line", "pie", "table", "auto"]
                        }
                    },
                    "required": ["data"]
                }
            },
            {
                "name": "manage_conversation",
                "description": "Use this tool ONLY for managing conversation context, retrieving previous conversation history, or clearing session data. Use 'get_history' to retrieve past messages in the session, 'get_summary' to get a conversation summary, or 'clear_history' to reset the conversation. Do NOT use for answering user queries or generating responses.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_id": {
                            "type": "string",
                            "description": "Session ID for the conversation"
                        },
                        "action": {
                            "type": "string",
                            "description": "Action to perform: 'get_history' to retrieve messages, 'clear_history' to reset, 'get_summary' to get summary",
                            "enum": ["get_history", "clear_history", "get_summary"]
                        }
                    },
                    "required": ["session_id", "action"]
                }
            }
        ]
    
    def _register_prompts(self):
        """Register MCP prompts"""
        self._prompts = [
            {
                "name": "sql_generation",
                "description": "Generate SQL from natural language query with schema context",
                "arguments": [
                    {
                        "name": "query",
                        "description": "Natural language query",
                        "required": True
                    },
                    {
                        "name": "schema_context",
                        "description": "Optional schema context (table names to focus on)",
                        "required": False
                    }
                ]
            },
            {
                "name": "data_summary",
                "description": "Generate natural language summary of query results",
                "arguments": [
                    {
                        "name": "data",
                        "description": "Query results data",
                        "required": True
                    },
                    {
                        "name": "query",
                        "description": "Original query",
                        "required": True
                    }
                ]
            }
        ]
    
    # Resource Handlers
    async def read_resource(self, uri: str) -> str:
        """Handle resource read requests"""
        if uri.startswith("schema://database/"):
            return await self._handle_schema_resource(uri)
        elif uri.startswith("data://database/"):
            return await self._handle_table_data_resource(uri)
        elif uri.startswith("context://session/"):
            return await self._handle_conversation_resource(uri)
        elif uri.startswith("results://query/"):
            return await self._handle_query_results_resource(uri)
        else:
            raise ValueError(f"Unknown resource URI: {uri}")
    
    async def _handle_schema_resource(self, uri: str) -> str:
        """Handle schema resource requests"""
        if uri == "schema://database/tables":
            schema_info = await database_service.get_schema_info()
            return json.dumps(schema_info, indent=2, default=str)
        elif uri.startswith("schema://database/"):
            table_name = uri.split("/")[-1]
            schema_info = await database_service.get_schema_info(table_name=table_name)
            return json.dumps(schema_info, indent=2, default=str)
        else:
            raise ValueError(f"Invalid schema URI: {uri}")
    
    async def _handle_table_data_resource(self, uri: str) -> str:
        """Handle table data resource requests"""
        parsed = urlparse(uri)
        table_name = parsed.path.split("/")[-1]
        params = parse_qs(parsed.query)
        
        limit = int(params.get("limit", [100])[0])
        
        query = f"SELECT * FROM {table_name} LIMIT {limit}"
        results = await database_service.execute_query(query)
        return json.dumps(results, indent=2, default=str)
    
    async def _handle_conversation_resource(self, uri: str) -> str:
        """Handle conversation context resource requests"""
        session_id = uri.split("/")[-1]
        messages = conversation_manager.get_messages(session_id)
        return json.dumps({
            "session_id": session_id,
            "messages": messages,
            "summary": conversation_manager.get_conversation_summary(session_id)
        }, indent=2, default=str)
    
    async def _handle_query_results_resource(self, uri: str) -> str:
        """Handle query results resource requests"""
        return json.dumps({
            "message": "Query results resource not yet implemented",
            "uri": uri
        })
    
    # Tool Handlers
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tool execution requests"""
        try:
            if name == "generate_sql":
                return await self._handle_generate_sql_tool(arguments)
            elif name == "execute_query":
                return await self._handle_execute_query_tool(arguments)
            elif name == "get_schema":
                return await self._handle_get_schema_tool(arguments)
            elif name == "create_visualization":
                return await self._handle_create_visualization_tool(arguments)
            elif name == "manage_conversation":
                return await self._handle_manage_conversation_tool(arguments)
            else:
                raise ValueError(f"Unknown tool: {name}")
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    async def _handle_generate_sql_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle SQL generation tool with Schema-RAG and self-correction"""
        query = arguments.get("query")
        session_id = arguments.get("session_id")
        refine_query = arguments.get("refine_query", False)
        
        if not query:
            raise ValueError("Query parameter is required")
        
        # STEP 1: Schema-RAG - Map user entities to database columns
        entity_mappings = await schema_rag_service.map_entities_to_columns(query)
        
        # STEP 2: Get conversation history if refining
        conversation_history = None
        if refine_query and session_id:
            conversation_history = conversation_manager.get_messages(
                session_id=session_id,
                max_messages=10
            )
        
        # STEP 3: Generate SQL with enhanced generator (includes self-correction)
        result = await enhanced_sql_generator.generate_sql(
            natural_language_query=query,
            conversation_history=conversation_history
        )
        
        # STEP 4: Validate SQL uses masked views only
        if result.get("sql"):
            sql = result["sql"]
            sql_upper = sql.upper()
            
            # CRITICAL: Ensure analytics_view_ prefix
            if 'ANALYTICS_VIEW' not in sql_upper:
                # Check for raw table references
                import re
                raw_tables = re.findall(r'FROM\s+([a-zA-Z_][a-zA-Z0-9_]*)', sql_upper)
                system_tables = {'INFORMATION_SCHEMA', 'SYS', 'MYSQL', 'PG_'}
                raw_tables = [t for t in raw_tables if not any(t.startswith(pref) for pref in system_tables)]
                
                if raw_tables:
                    raise ValueError(f"PHI VIOLATION: Query must use analytics_view_* tables only. Found raw tables: {raw_tables}")
        
        return {
            "success": True,
            "sql": result.get("sql"),
            "explanation": result.get("explanation"),
            "confidence": result.get("confidence", 0.8),
            "correction_attempts": result.get("correction_attempts", 0),
            "entity_mappings": entity_mappings.get("mapped_entities", [])
        }
    
    async def _handle_execute_query_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle query execution tool with privacy compliance"""
        sql = arguments.get("sql")
        params = arguments.get("params")
        original_query = arguments.get("original_query", "")
        
        if not sql:
            raise ValueError("SQL parameter is required")
        
        # CRITICAL: Validate SQL uses masked views only
        sql_upper = sql.upper()
        if 'ANALYTICS_VIEW' not in sql_upper:
            import re
            raw_tables = re.findall(r'FROM\s+([a-zA-Z_][a-zA-Z0-9_]*)', sql_upper)
            system_tables = {'INFORMATION_SCHEMA', 'SYS', 'MYSQL', 'PG_'}
            raw_tables = [t for t in raw_tables if not any(t.startswith(pref) for pref in system_tables)]
            
            if raw_tables:
                raise ValueError(f"PHI VIOLATION: Query must use analytics_view_* tables only. Found: {raw_tables}")
        
        # Execute query (database_service already validates)
        results = await database_service.execute_query(sql, params)
        
        # STEP 1: Apply small cell suppression (privacy compliance)
        results = privacy_service.apply_small_cell_suppression(results)
        
        # STEP 2: Validate results for stray PII
        from app.services.pii_validator import pii_validator
        sanitized_results, pii_detected = pii_validator.validate_query_results(results)
        results = sanitized_results
        
        # STEP 3: Generate analytical summary
        analytical_summary = analytical_summary_service.generate_summary(
            results,
            sql,
            original_query or "Query executed"
        )
        
        # STEP 4: Suggest visualization
        viz_suggestion = analytical_summary_service.suggest_visualization(results, sql)
        
        # STEP 5: Generate visualization (legacy support)
        visualization = visualization_service.analyze_data(results)
        formatted_table = visualization_service.format_table(results, max_rows=100)
        summary = visualization_service.generate_summary(
            results,
            f"Query executed: {sql[:100]}"
        )
        
        # STEP 6: Privacy warning if PII detected
        privacy_warning = None
        if pii_detected:
            privacy_warning = pii_validator.get_privacy_warning(pii_detected)
        
        return {
            "success": True,
            "data": results[:100],  # Limit to 100 rows
            "row_count": len(results),
            "analytical_summary": analytical_summary,
            "viz_suggestion": viz_suggestion,
            "visualization": {
                "type": visualization["type"],
                "table": formatted_table,
                "chart_config": visualization.get("chart_config", {}),
                "chart_image": visualization.get("chart_image", {}),
                "metadata": visualization.get("metadata", {})
            },
            "summary": summary,  # Legacy
            "privacy_warning": privacy_warning,
            "pii_detected": pii_detected if pii_detected else None
        }
    
    async def _handle_get_schema_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get schema tool"""
        table_name = arguments.get("table_name")
        
        schema_info = await database_service.get_schema_info(table_name=table_name)
        
        return {
            "success": True,
            "schema": schema_info
        }
    
    async def _handle_create_visualization_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle visualization creation tool"""
        data = arguments.get("data")
        chart_type = arguments.get("chart_type", "auto")
        
        if not data:
            raise ValueError("Data parameter is required")
        
        visualization = visualization_service.analyze_data(data)
        
        # Override chart type if specified
        if chart_type != "auto" and chart_type in ["bar", "line", "pie", "table"]:
            visualization["type"] = chart_type
        
        return {
            "success": True,
            "visualization": visualization
        }
    
    async def _handle_manage_conversation_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle conversation management tool"""
        session_id = arguments.get("session_id")
        action = arguments.get("action")
        
        if not session_id or not action:
            raise ValueError("session_id and action are required")
        
        if action == "get_history":
            messages = conversation_manager.get_messages(session_id)
            return {
                "success": True,
                "session_id": session_id,
                "messages": messages
            }
        elif action == "clear_history":
            conversation_manager.clear_conversation(session_id)
            return {
                "success": True,
                "session_id": session_id,
                "message": "Conversation history cleared"
            }
        elif action == "get_summary":
            summary = conversation_manager.get_conversation_summary(session_id)
            return {
                "success": True,
                "session_id": session_id,
                "summary": summary
            }
        else:
            raise ValueError(f"Unknown action: {action}")
    
    # Prompt Handlers
    async def get_prompt(self, name: str, arguments: Dict[str, Any]) -> str:
        """Handle prompt template requests"""
        if name == "sql_generation":
            return await self._get_sql_generation_prompt(arguments)
        elif name == "data_summary":
            return await self._get_data_summary_prompt(arguments)
        else:
            raise ValueError(f"Unknown prompt: {name}")
    
    async def _get_sql_generation_prompt(self, arguments: Dict[str, Any]) -> str:
        """Get SQL generation prompt template with Schema-RAG"""
        query = arguments.get("query", "")
        schema_context = arguments.get("schema_context", "")
        
        # Get entity mappings (Schema-RAG)
        entity_mappings = await schema_rag_service.map_entities_to_columns(query)
        entity_context = schema_rag_service.get_entity_mapping_context(
            entity_mappings.get('mapped_entities', [])
        )
        
        # Get comprehensive schema
        from app.services.schema_loader import schema_loader
        comprehensive_schema = await schema_loader.load_comprehensive_schema()
        schema_info = comprehensive_schema.get('table_schemas', {})
        
        # Build schema text
        schema_text = "=== DATABASE SCHEMA (Analytics Views Only) ===\n\n"
        schema_text += "IMPORTANT: All tables use 'analytics_view_' prefix. PII is masked.\n\n"
        
        for table_name, table_info in list(schema_info.items())[:20]:
            schema_text += f"Table: {table_name}\n"
            columns = table_info.get('columns', [])
            for col in columns[:15]:  # Limit columns
                col_name = col.get('column_name', '')
                col_type = col.get('data_type', '')
                schema_text += f"  - {col_name} ({col_type})\n"
            schema_text += "\n"
        
        prompt = f"""You are an expert SQL query generator for a MySQL database with strict privacy compliance.

{entity_context}

=== DATABASE SCHEMA ===
{schema_text}

=== USER QUERY ===
{query}

=== YOUR TASK ===
Generate a MySQL SELECT query that answers this question using ONLY analytics_view_* tables.
Return ONLY the SQL query starting with SELECT."""
        
        return prompt
    
    async def _get_data_summary_prompt(self, arguments: Dict[str, Any]) -> str:
        """Get data summary prompt template"""
        data = arguments.get("data", [])
        query = arguments.get("query", "")
        
        data_preview = json.dumps(data[:10], indent=2) if data else "No data"
        
        prompt = f"""Generate a natural language summary of the following query results.

=== ORIGINAL QUERY ===
{query}

=== QUERY RESULTS (sample) ===
{data_preview}

=== YOUR TASK ===
Provide a concise, informative summary of these results in natural language."""
        
        return prompt
    
    # Getters for MCP protocol
    def list_resources(self) -> List[Dict[str, Any]]:
        """List available resources"""
        return self._resources
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools"""
        return self._tools
    
    def list_prompts(self) -> List[Dict[str, Any]]:
        """List available prompts"""
        return self._prompts


# Global server instance
mcp_server = AdminChatMCPServer()


async def main():
    """Main entry point for MCP server (for testing)"""
    await mcp_server.initialize()
    
    print("MCP Server initialized")
    print(f"Resources: {len(mcp_server.list_resources())}")
    print(f"Tools: {len(mcp_server.list_tools())}")
    print(f"Prompts: {len(mcp_server.list_prompts())}")
    
    # Example: Test a tool call
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        print("\nTesting SQL generation tool...")
        result = await mcp_server.call_tool("generate_sql", {
            "query": "Show me total number of claims"
        })
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
