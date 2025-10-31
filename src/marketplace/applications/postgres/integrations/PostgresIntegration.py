from lib.abi.integration.integration import Integration, IntegrationConfiguration, IntegrationConnectionError
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Union, Tuple
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
import pandas as pd


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
        
    def execute_pandas_query(self, query: str) -> pd.DataFrame:
        """Execute a SQL query and return results as a pandas DataFrame.
        
        Args:
            query (str): SQL query to execute
            
        Returns:
            pd.DataFrame: Query results as a pandas DataFrame
            
        Raises:
            IntegrationConnectionError: If the operation fails
        """
        try:
            with self.__get_connection() as conn:
                return pd.read_sql_query(query, conn)
        except Exception as e:
            raise IntegrationConnectionError(f"PostgreSQL query failed: {str(e)}")

    def execute_query(
        self,
        query: str,
        params: Optional[Union[Tuple, Dict]] = None,
        fetch: bool = True
    ) -> Union[List[Dict], int]:
        """Execute a SQL query.
        
        Args:
            query (str): SQL query
            params (Optional[Union[Tuple, Dict]], optional): Query parameters. Defaults to None.
            fetch (bool, optional): Whether to fetch results. Defaults to True.
            
        Returns:
            Union[List[Dict], int]: Query results or number of affected rows
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
        
    def list_tables(self) -> List[str]:
        """Get list of all tables in the connected database.
        
        Returns:
            List[str]: List of table names
        """
        query = """
            SELECT table_name 
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """
        try:
            results = self.execute_query(query)
            if isinstance(results, list):
                return [row['table_name'] for row in results]
            else:
                return []
        except Exception as e:
            raise IntegrationConnectionError(f"Failed to list tables: {str(e)}")
        
    def get_table_schema(self, table_name: str) -> List[Dict[str, Any]]:
        """Get schema information for a specific table.
        
        Args:
            table_name (str): Table name
            
        Returns:
            Dict[str, Any]: Table schema information
        """
        query = f"""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = '{table_name}'
            ORDER BY ordinal_position;
        """
        try:
            results = self.execute_query(query)
            if isinstance(results, list):
                return [dict(row) for row in results]
            else:
                return []
        except Exception as e:
            raise IntegrationConnectionError(f"Failed to get table schema: {str(e)}")

def as_tools(configuration: PostgresIntegrationConfiguration):
    """Convert PostgreSQL integration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field
    
    integration = PostgresIntegration(configuration)

    class QuerySchema(BaseModel):
        query: str = Field(..., description="SQL query")
        params: Optional[Union[Tuple, Dict]] = Field(None, description="Query parameters to be used in the query if needed.")
        fetch: bool = Field(description="Whether to fetch results")

    class ListTablesSchema(BaseModel):
        pass
    
    class GetTableSchemaSchema(BaseModel):
        table_name: str = Field(..., description="Table name")
    
    return [
        StructuredTool(
            name="postgres_execute_query",
            description="Execute a PostgreSQL query",
            func=lambda query, params, fetch: integration.execute_query(query, params, fetch),
            args_schema=QuerySchema
        ),
        StructuredTool(
            name="postgres_list_tables",
            description="Get list of all tables in the connected database",
            func=lambda: integration.list_tables(),
            args_schema=ListTablesSchema
        ),
        StructuredTool(
            name="postgres_get_table_schema",
            description="Get schema information for a specific table",
            func=lambda table_name: integration.get_table_schema(table_name),
            args_schema=GetTableSchemaSchema
        )
    ]