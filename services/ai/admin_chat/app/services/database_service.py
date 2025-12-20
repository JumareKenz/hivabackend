"""
Database Service for Read-Only Analytics Queries
Supports both PostgreSQL and MySQL
"""
import os
import re
from typing import Optional, List, Dict, Any, Union
from contextlib import asynccontextmanager
import asyncio
from app.core.config import settings

# Database drivers
try:
    import asyncpg
    from asyncpg import Pool as PostgresPool
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False

try:
    import aiomysql
    from aiomysql import Pool as MySQLPool
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False


class DatabaseService:
    """Manages read-only database connections for analytics queries"""
    
    def __init__(self):
        self.pool: Optional[Union[PostgresPool, MySQLPool]] = None
        self.db_type: Optional[str] = None
        self._connection_config: Optional[Dict[str, Any]] = None
        self._initialized = False
    
    def _get_connection_config(self) -> Optional[Dict[str, Any]]:
        """Get database connection configuration from settings"""
        # Use settings from config (which loads from .env)
        db_type = (settings.ANALYTICS_DB_TYPE or "postgresql").lower()
        host = settings.ANALYTICS_DB_HOST
        port = settings.ANALYTICS_DB_PORT or ("5432" if db_type == "postgresql" else "3306")
        database = settings.ANALYTICS_DB_NAME
        user = settings.ANALYTICS_DB_USER
        password = settings.ANALYTICS_DB_PASSWORD
        
        if not all([host, database, user, password]):
            return None
        
        return {
            "type": db_type,
            "host": host,
            "port": int(port),
            "database": database,
            "user": user,
            "password": password
        }
    
    async def initialize(self):
        """Initialize database connection pool"""
        if self._initialized:
            return
        
        config = self._get_connection_config()
        if not config:
            print("⚠️  WARNING: Analytics database not configured. Admin insights will be disabled.")
            self._initialized = True
            return
        
        self.db_type = config["type"]
        self._connection_config = config
        
        try:
            if self.db_type == "postgresql":
                if not POSTGRES_AVAILABLE:
                    raise ImportError("asyncpg not installed. Install with: pip install asyncpg")
                
                conn_string = f"postgresql://{config['user']}:{config['password']}@{config['host']}:{config['port']}/{config['database']}"
                self.pool = await asyncpg.create_pool(
                    conn_string,
                    min_size=2,
                    max_size=10,
                    command_timeout=60,
                    server_settings={
                        'application_name': 'hiva_admin_insights',
                        'statement_timeout': '60000',
                    }
                )
                print("✅ PostgreSQL connection pool initialized")
                
            elif self.db_type == "mysql":
                if not MYSQL_AVAILABLE:
                    raise ImportError("aiomysql not installed. Install with: pip install aiomysql")
                
                self.pool = await aiomysql.create_pool(
                    host=config['host'],
                    port=config['port'],
                    db=config['database'],
                    user=config['user'],
                    password=config['password'],
                    minsize=2,
                    maxsize=10,
                    autocommit=False
                )
                print("✅ MySQL connection pool initialized")
            else:
                raise ValueError(f"Unsupported database type: {self.db_type}")
            
            self._initialized = True
            
        except Exception as e:
            print(f"❌ Failed to initialize database pool: {e}")
            self._initialized = True  # Mark as initialized to prevent retry loops
    
    async def close(self):
        """Close database connection pool"""
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()
            self.pool = None
    
    @asynccontextmanager
    async def get_connection(self):
        """Get a database connection from the pool"""
        if not self.pool:
            raise RuntimeError("Database pool not initialized. Call initialize() first.")
        
        conn = await self.pool.acquire()
        try:
            # Set connection to read-only mode
            if self.db_type == "postgresql":
                await conn.execute("SET TRANSACTION READ ONLY")
            elif self.db_type == "mysql":
                # MySQL doesn't support transaction-level read-only, but we validate queries
                pass
            yield conn
        finally:
            self.pool.release(conn)
    
    async def execute_query(
        self,
        query: str,
        params: Optional[List[Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute a read-only SQL query and return results as list of dicts
        
        Args:
            query: SQL query string
            params: Optional query parameters for parameterized queries
        
        Returns:
            List of dictionaries representing rows
        """
        if not self.pool:
            raise RuntimeError("Database not available")
        
        # Security: Ensure query is read-only (no INSERT, UPDATE, DELETE, DROP, etc.)
        query_upper = query.strip().upper()
        
        # Must start with SELECT
        if not query_upper.startswith('SELECT'):
            raise ValueError(f"Query must start with SELECT. Only read-only queries are allowed.")
        
        # Check for forbidden keywords (but allow them in string literals/comments)
        # Split by common SQL delimiters to avoid false positives
        forbidden_keywords = [
            'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER',
            'TRUNCATE', 'GRANT', 'REVOKE', 'EXEC', 'EXECUTE', 'REPLACE'
        ]
        
        # Check if any forbidden keyword appears as a standalone word (not in a string)
        words = re.split(r'[\s,;()]+', query_upper)
        for keyword in forbidden_keywords:
            if keyword in words:
                raise ValueError(f"Query contains forbidden keyword '{keyword}'. Only SELECT queries are allowed.")
        
        async with self.get_connection() as conn:
            try:
                if self.db_type == "postgresql":
                    if params:
                        rows = await conn.fetch(query, *params)
                    else:
                        rows = await conn.fetch(query)
                    # Convert asyncpg.Record to dict
                    return [dict(row) for row in rows]
                    
                elif self.db_type == "mysql":
                    async with conn.cursor(aiomysql.DictCursor) as cursor:
                        if params:
                            await cursor.execute(query, params)
                        else:
                            await cursor.execute(query)
                        rows = await cursor.fetchall()
                        # aiomysql DictCursor already returns dicts
                        return list(rows) if rows else []
                
            except Exception as e:
                raise RuntimeError(f"Query execution failed: {str(e)}")
    
    async def get_schema_info(self, table_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get database schema information
        
        Args:
            table_name: Optional specific table name, or None for all tables
        
        Returns:
            Schema information dictionary
        """
        if not self.pool:
            return {}
        
        try:
            if self.db_type == "postgresql":
                if table_name:
                    query = """
                        SELECT 
                            column_name,
                            data_type,
                            is_nullable,
                            column_default
                        FROM information_schema.columns
                        WHERE table_name = $1
                        ORDER BY ordinal_position;
                    """
                    columns = await self.execute_query(query, [table_name])
                    return {
                        "table_name": table_name,
                        "columns": columns
                    }
                else:
                    query = """
                        SELECT 
                            t.table_name,
                            json_agg(
                                json_build_object(
                                    'column_name', c.column_name,
                                    'data_type', c.data_type,
                                    'is_nullable', c.is_nullable
                                ) ORDER BY c.ordinal_position
                            ) as columns
                        FROM information_schema.tables t
                        JOIN information_schema.columns c 
                            ON t.table_name = c.table_name
                        WHERE t.table_schema = 'public'
                            AND t.table_type = 'BASE TABLE'
                        GROUP BY t.table_name
                        ORDER BY t.table_name;
                    """
                    tables = await self.execute_query(query)
                    return {"tables": tables}
                    
            elif self.db_type == "mysql":
                if table_name:
                    query = """
                        SELECT 
                            column_name,
                            data_type,
                            is_nullable,
                            column_default
                        FROM information_schema.columns
                        WHERE table_schema = %s AND table_name = %s
                        ORDER BY ordinal_position;
                    """
                    columns = await self.execute_query(query, [self._connection_config['database'], table_name])
                    return {
                        "table_name": table_name,
                        "columns": columns
                    }
                else:
                    query = """
                        SELECT 
                            t.table_name,
                            GROUP_CONCAT(
                                CONCAT(
                                    c.column_name, ':', c.data_type, ':', c.is_nullable
                                ) ORDER BY c.ordinal_position SEPARATOR '|'
                            ) as columns_info
                        FROM information_schema.tables t
                        JOIN information_schema.columns c 
                            ON t.table_schema = c.table_schema AND t.table_name = c.table_name
                        WHERE t.table_schema = %s
                            AND t.table_type = 'BASE TABLE'
                        GROUP BY t.table_name
                        ORDER BY t.table_name;
                    """
                    tables_raw = await self.execute_query(query, [self._connection_config['database']])
                    
                    # Parse columns_info into structured format
                    tables = []
                    for row in tables_raw:
                        columns_info = row.get('columns_info', '')
                        columns = []
                        if columns_info:
                            for col_info in columns_info.split('|'):
                                parts = col_info.split(':')
                                if len(parts) >= 3:
                                    columns.append({
                                        'column_name': parts[0],
                                        'data_type': parts[1],
                                        'is_nullable': parts[2]
                                    })
                        tables.append({
                            'table_name': row['table_name'],
                            'columns': columns
                        })
                    
                    return {"tables": tables}
        except Exception as e:
            print(f"Error fetching schema: {e}")
            return {}


# Global instance
database_service = DatabaseService()




