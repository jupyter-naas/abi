from lib.abi.integration.integration import Integration, IntegrationConfiguration, IntegrationConnectionError
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Union, Tuple
import psycopg2
from psycopg2.extras import RealDictCursor, execute_values
from contextlib import contextmanager

LOGO_URL = "https://logo.clearbit.com/postgresql.org"

@dataclass
class PostgresIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for PostgreSQL integration.
    
    Attributes:
        host (str): Database host
        port (int): Database port
        database (str): Database name
        user (str): Database user
        password (str): Database password
        sslmode (str): SSL mode (disable, require, verify-ca, verify-full)
    """
    host: str
    port: int
    database: str
    user: str
    password: str
    sslmode: str = 'require'

class PostgresIntegration(Integration):
    """PostgreSQL integration client.
    
    This integration provides methods to interact with PostgreSQL's API endpoints.
    """

    __configuration: PostgresIntegrationConfiguration

    def __init__(self, configuration: PostgresIntegrationConfiguration):
        """Initialize PostgreSQL client."""
        super().__init__(configuration)
        self.__configuration = configuration

    @contextmanager
    def __get_connection(self):
        """Create a database connection context.
        
        Yields:
            psycopg2.extensions.connection: Database connection
            
        Raises:
            IntegrationConnectionError: If connection fails
        """
        try:
            connection = psycopg2.connect(
                host=self.__configuration.host,
                port=self.__configuration.port,
                dbname=self.__configuration.database,
                user=self.__configuration.user,
                password=self.__configuration.password,
                sslmode=self.__configuration.sslmode
            )
            yield connection
            connection.close()
        except Exception as e:
            raise IntegrationConnectionError(f"PostgreSQL connection failed: {str(e)}")

    def execute_query(self,
                     query: str,
                     params: Optional[Union[Tuple, Dict]] = None,
                     fetch: bool = True) -> Union[List[Dict], int]:
        """Execute a SQL query.
        
        Args:
            query (str): SQL query
            params (Union[Tuple, Dict], optional): Query parameters
            fetch (bool, optional): Whether to fetch results. Defaults to True
            
        Returns:
            Union[List[Dict], int]: Query results or number of affected rows
            
        Raises:
            IntegrationConnectionError: If the operation fails
        """
        try:
            with self.__get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query, params)
                    
                    if fetch:
                        results = cur.fetchall()
                        return [dict(row) for row in results]
                    else:
                        conn.commit()
                        return cur.rowcount
        except Exception as e:
            raise IntegrationConnectionError(f"PostgreSQL operation failed: {str(e)}")

    def batch_insert(self,
                    table: str,
                    columns: List[str],
                    values: List[Tuple],
                    page_size: int = 1000) -> int:
        """Insert multiple rows into a table.
        
        Args:
            table (str): Table name
            columns (List[str]): Column names
            values (List[Tuple]): Values to insert
            page_size (int, optional): Batch size. Defaults to 1000
            
        Returns:
            int: Number of inserted rows
            
        Raises:
            IntegrationConnectionError: If the operation fails
        """
        try:
            with self.__get_connection() as conn:
                with conn.cursor() as cur:
                    return execute_values(
                        cur,
                        f"INSERT INTO {table} ({', '.join(columns)}) VALUES %s",
                        values,
                        page_size=page_size
                    )
        except Exception as e:
            raise IntegrationConnectionError(f"PostgreSQL operation failed: {str(e)}")

    def call_procedure(self,
                      procedure: str,
                      params: Optional[Union[Tuple, Dict]] = None) -> Optional[List[Dict]]:
        """Call a stored procedure.
        
        Args:
            procedure (str): Procedure name
            params (Union[Tuple, Dict], optional): Procedure parameters
            
        Returns:
            Optional[List[Dict]]: Procedure results if any
            
        Raises:
            IntegrationConnectionError: If the operation fails
        """
        try:
            with self.__get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.callproc(procedure, params)
                    
                    try:
                        results = cur.fetchall()
                        return [dict(row) for row in results]
                    except psycopg2.ProgrammingError:
                        conn.commit()
                        return None
        except Exception as e:
            raise IntegrationConnectionError(f"PostgreSQL operation failed: {str(e)}")

    def get_table_schema(self, table: str) -> List[Dict]:
        """Get table schema information.
        
        Args:
            table (str): Table name
            
        Returns:
            List[Dict]: Column information
            
        Raises:
            IntegrationConnectionError: If the operation fails
        """
        query = """
            SELECT 
                column_name,
                data_type,
                character_maximum_length,
                column_default,
                is_nullable
            FROM information_schema.columns
            WHERE table_name = %s
            ORDER BY ordinal_position;
        """
        
        return self.execute_query(query, (table,))

    def create_table(self,
                    table: str,
                    columns: List[Dict[str, str]],
                    if_not_exists: bool = True) -> None:
        """Create a new table.
        
        Args:
            table (str): Table name
            columns (List[Dict[str, str]]): Column definitions
            if_not_exists (bool, optional): Add IF NOT EXISTS clause. Defaults to True
            
        Raises:
            IntegrationConnectionError: If the operation fails
        """
        try:
            column_defs = []
            for col in columns:
                definition = f"{col['name']} {col['type']}"
                if col.get('nullable') is False:
                    definition += " NOT NULL"
                if 'default' in col:
                    definition += f" DEFAULT {col['default']}"
                column_defs.append(definition)

            exists_clause = "IF NOT EXISTS" if if_not_exists else ""
            query = f"CREATE TABLE {exists_clause} {table} ({', '.join(column_defs)})"
            
            self.execute_query(query, fetch=False)
        except Exception as e:
            raise IntegrationConnectionError(f"PostgreSQL operation failed: {str(e)}")

def as_tools(configuration: PostgresIntegrationConfiguration):
    """Convert PostgreSQL integration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field
    
    integration = PostgresIntegration(configuration)
    
    class QuerySchema(BaseModel):
        query: str = Field(..., description="SQL query")
        params: Optional[Union[Tuple, Dict]] = Field(None, description="Query parameters")
        fetch: bool = Field(default=True, description="Whether to fetch results")

    class BatchInsertSchema(BaseModel):
        table: str = Field(..., description="Table name")
        columns: List[str] = Field(..., description="Column names")
        values: List[Tuple] = Field(..., description="Values to insert")
        page_size: int = Field(default=1000, description="Batch size")

    class ProcedureSchema(BaseModel):
        procedure: str = Field(..., description="Procedure name")
        params: Optional[Union[Tuple, Dict]] = Field(None, description="Procedure parameters")

    class TableSchema(BaseModel):
        table: str = Field(..., description="Table name")

    class CreateTableSchema(BaseModel):
        table: str = Field(..., description="Table name")
        columns: List[Dict[str, str]] = Field(..., description="Column definitions")
        if_not_exists: bool = Field(default=True, description="Add IF NOT EXISTS clause")
    
    return [
        StructuredTool(
            name="execute_postgres_query",
            description="Execute a PostgreSQL query",
            func=lambda query, params, fetch: integration.execute_query(query, params, fetch),
            args_schema=QuerySchema
        ),
        StructuredTool(
            name="batch_insert_postgres",
            description="Insert multiple rows into a PostgreSQL table",
            func=lambda table, columns, values, page_size:
                integration.batch_insert(table, columns, values, page_size),
            args_schema=BatchInsertSchema
        ),
        StructuredTool(
            name="call_postgres_procedure",
            description="Call a PostgreSQL stored procedure",
            func=lambda procedure, params: integration.call_procedure(procedure, params),
            args_schema=ProcedureSchema
        ),
        StructuredTool(
            name="get_postgres_table_schema",
            description="Get PostgreSQL table schema information",
            func=lambda table: integration.get_table_schema(table),
            args_schema=TableSchema
        ),
        StructuredTool(
            name="create_postgres_table",
            description="Create a new PostgreSQL table",
            func=lambda table, columns, if_not_exists:
                integration.create_table(table, columns, if_not_exists),
            args_schema=CreateTableSchema
        )
    ] 