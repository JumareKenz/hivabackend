"""
MCP Client Wrapper for Admin Chat Service
Provides seamless integration between existing API and MCP server
"""
import asyncio
import json
from typing import Dict, Any, Optional, List
from pathlib import Path
import sys

# Add mcp_server to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "mcp_server"))

from app.core.config import settings
from app.services.database_service import database_service
from app.services.sql_generator import sql_generator
from app.services.visualization_service import visualization_service
from app.services.conversation_manager import conversation_manager
from app.services.intent_router import intent_router


class MCPClient:
    """
    MCP Client wrapper that provides MCP-compatible interface
    while using existing Admin Chat services
    """
    
    def __init__(self):
        self._initialized = False
    
    async def initialize(self):
        """Initialize MCP client and underlying services"""
        if self._initialized:
            return
        
        # Initialize database connection
        await database_service.initialize()
        self._initialized = True
    
    async def generate_sql(
        self,
        query: str,
        session_id: Optional[str] = None,
        refine_query: bool = False
    ) -> Dict[str, Any]:
        """
        Generate SQL from natural language query (MCP-compatible)
        
        Args:
            query: Natural language query
            session_id: Optional session ID for context
            refine_query: Whether to use conversation history
        
        Returns:
            Dictionary with sql, explanation, and confidence
        """
        await self.initialize()
        
        conversation_history = None
        if refine_query and session_id:
            conversation_history = conversation_manager.get_messages(
                session_id=session_id,
                max_messages=10
            )
        
        try:
            # Use data specialist prompt for better accuracy
            data_specialist_prompt = intent_router.get_data_specialist_prompt()
            
            # Enhance query with data specialist context
            enhanced_query = f"{data_specialist_prompt}\n\nUser Query: {query}\n\nGenerate SQL query:"
            
            result = await sql_generator.generate_sql(
                natural_language_query=query,  # Use original query, prompt is in sql_generator
                conversation_history=conversation_history
            )
            
            return {
                "success": True,
                "sql": result.get("sql"),
                "explanation": result.get("explanation"),
                "confidence": result.get("confidence", 0.8)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    async def execute_query(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute SQL query and return results with visualization (MCP-compatible)
        
        Args:
            sql: SQL SELECT query
            params: Optional query parameters
        
        Returns:
            Dictionary with data, visualization, and summary
        """
        await self.initialize()
        
        try:
            # Execute query (database_service validates read-only)
            results = await database_service.execute_query(sql, params)
            
            # Generate visualization
            visualization = visualization_service.analyze_data(results)
            formatted_table = visualization_service.format_table(results, max_rows=100)
            summary = visualization_service.generate_summary(
                results,
                f"Query executed: {sql[:100]}"
            )
            
            return {
                "success": True,
                "data": results[:100],  # Limit to 100 rows
                "row_count": len(results),
                "visualization": {
                    "type": visualization["type"],
                    "table": formatted_table,
                    "chart_config": visualization.get("chart_config", {}),
                    "chart_image": visualization.get("chart_image", {}),
                    "metadata": visualization.get("metadata", {})
                },
                "summary": summary
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    async def get_schema(
        self,
        table_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get database schema information (MCP-compatible)
        
        Args:
            table_name: Optional specific table name
        
        Returns:
            Schema information dictionary
        """
        await self.initialize()
        
        try:
            schema_info = await database_service.get_schema_info(table_name=table_name)
            return {
                "success": True,
                "schema": schema_info
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    async def create_visualization(
        self,
        data: List[Dict[str, Any]],
        chart_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create visualization from data (MCP-compatible)
        
        Args:
            data: Query results data
            chart_type: Optional chart type (bar, line, pie, table, auto)
        
        Returns:
            Visualization dictionary
        """
        await self.initialize()
        
        try:
            visualization = visualization_service.analyze_data(data)
            
            # Override chart type if specified
            if chart_type and chart_type in ["bar", "line", "pie", "table"]:
                visualization["type"] = chart_type
            
            return {
                "success": True,
                "visualization": visualization
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    async def manage_conversation(
        self,
        session_id: str,
        action: str
    ) -> Dict[str, Any]:
        """
        Manage conversation history (MCP-compatible)
        
        Args:
            session_id: Session ID
            action: Action (get_history, clear_history, get_summary)
        
        Returns:
            Conversation management result
        """
        await self.initialize()
        
        try:
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
                return {
                    "success": False,
                    "error": f"Unknown action: {action}",
                    "error_type": "ValueError"
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }


# Global MCP client instance
mcp_client = MCPClient()


