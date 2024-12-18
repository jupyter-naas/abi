from lib.abi.integration.integration import Integration, IntegrationConfiguration, IntegrationConnectionError
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Union
from supabase import create_client, Client

LOGO_URL = "https://logo.clearbit.com/supabase.com"

@dataclass
class SupabaseIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for Supabase integration.
    
    Attributes:
        url (str): Supabase project URL
        key (str): Supabase project API key
        timeout (int): Request timeout in seconds
    """
    url: str
    key: str
    timeout: int = 60

class SupabaseIntegration(Integration):
    """Supabase integration client.
    
    This integration provides methods to interact with Supabase's API endpoints.
    It handles authentication and request management.
    """

    __configuration: SupabaseIntegrationConfiguration

    def __init__(self, configuration: SupabaseIntegrationConfiguration):
        """Initialize Supabase client."""
        super().__init__(configuration)
        self.__configuration = configuration
        
        self.__client = create_client(
            self.__configuration.url,
            self.__configuration.key,
            options={'timeout': self.__configuration.timeout}
        )

    def select(self,
               table: str,
               columns: str = '*',
               filters: Optional[Dict] = None,
               order: Optional[List[Dict[str, str]]] = None,
               limit: Optional[int] = None,
               offset: Optional[int] = None) -> List[Dict]:
        """Select data from a table.
        
        Args:
            table (str): Table name
            columns (str): Columns to select
            filters (Dict, optional): Query filters
            order (List[Dict[str, str]], optional): Order by configuration
            limit (int, optional): Maximum number of rows
            offset (int, optional): Number of rows to skip
            
        Returns:
            List[Dict]: Query results
            
        Raises:
            IntegrationConnectionError: If the operation fails
        """
        try:
            query = self.__client.table(table).select(columns)
            
            if filters:
                for key, value in filters.items():
                    if isinstance(value, dict):
                        operator = value.get('operator', 'eq')
                        query = getattr(query, operator)(key, value.get('value'))
                    else:
                        query = query.eq(key, value)
            
            if order:
                for order_config in order:
                    column = order_config['column']
                    ascending = order_config.get('ascending', True)
                    query = query.order(column, desc=not ascending)
            
            if limit is not None:
                query = query.limit(limit)
                
            if offset is not None:
                query = query.offset(offset)
            
            response = query.execute()
            return response.data
        except Exception as e:
            raise IntegrationConnectionError(f"Supabase operation failed: {str(e)}")

    def insert(self,
              table: str,
              data: Union[Dict, List[Dict]],
              upsert: bool = False) -> List[Dict]:
        """Insert data into a table.
        
        Args:
            table (str): Table name
            data (Union[Dict, List[Dict]]): Data to insert
            upsert (bool, optional): Whether to upsert. Defaults to False
            
        Returns:
            List[Dict]: Inserted records
            
        Raises:
            IntegrationConnectionError: If the operation fails
        """
        try:
            query = self.__client.table(table)
            if upsert:
                response = query.upsert(data).execute()
            else:
                response = query.insert(data).execute()
            return response.data
        except Exception as e:
            raise IntegrationConnectionError(f"Supabase operation failed: {str(e)}")

    def update(self,
              table: str,
              data: Dict,
              filters: Dict) -> List[Dict]:
        """Update records in a table.
        
        Args:
            table (str): Table name
            data (Dict): Update data
            filters (Dict): Update filters
            
        Returns:
            List[Dict]: Updated records
            
        Raises:
            IntegrationConnectionError: If the operation fails
        """
        try:
            query = self.__client.table(table).update(data)
            
            for key, value in filters.items():
                if isinstance(value, dict):
                    operator = value.get('operator', 'eq')
                    query = getattr(query, operator)(key, value.get('value'))
                else:
                    query = query.eq(key, value)
            
            response = query.execute()
            return response.data
        except Exception as e:
            raise IntegrationConnectionError(f"Supabase operation failed: {str(e)}")

    def delete(self,
              table: str,
              filters: Dict) -> List[Dict]:
        """Delete records from a table.
        
        Args:
            table (str): Table name
            filters (Dict): Delete filters
            
        Returns:
            List[Dict]: Deleted records
            
        Raises:
            IntegrationConnectionError: If the operation fails
        """
        try:
            query = self.__client.table(table).delete()
            
            for key, value in filters.items():
                if isinstance(value, dict):
                    operator = value.get('operator', 'eq')
                    query = getattr(query, operator)(key, value.get('value'))
                else:
                    query = query.eq(key, value)
            
            response = query.execute()
            return response.data
        except Exception as e:
            raise IntegrationConnectionError(f"Supabase operation failed: {str(e)}")

    def rpc(self,
           function: str,
           params: Optional[Dict] = None) -> Any:
        """Call a Postgres function via RPC.
        
        Args:
            function (str): Function name
            params (Dict, optional): Function parameters
            
        Returns:
            Any: Function result
            
        Raises:
            IntegrationConnectionError: If the operation fails
        """
        try:
            response = self.__client.rpc(function, params or {}).execute()
            return response.data
        except Exception as e:
            raise IntegrationConnectionError(f"Supabase operation failed: {str(e)}")

def as_tools(configuration: SupabaseIntegrationConfiguration):
    """Convert Supabase integration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field
    
    integration = SupabaseIntegration(configuration)
    
    class SelectSchema(BaseModel):
        table: str = Field(..., description="Table name")
        columns: str = Field(default='*', description="Columns to select")
        filters: Optional[Dict] = Field(None, description="Query filters")
        order: Optional[List[Dict[str, str]]] = Field(None, description="Order by configuration")
        limit: Optional[int] = Field(None, description="Maximum number of rows")
        offset: Optional[int] = Field(None, description="Number of rows to skip")

    class InsertSchema(BaseModel):
        table: str = Field(..., description="Table name")
        data: Union[Dict, List[Dict]] = Field(..., description="Data to insert")
        upsert: bool = Field(default=False, description="Whether to upsert")

    class UpdateSchema(BaseModel):
        table: str = Field(..., description="Table name")
        data: Dict = Field(..., description="Update data")
        filters: Dict = Field(..., description="Update filters")

    class DeleteSchema(BaseModel):
        table: str = Field(..., description="Table name")
        filters: Dict = Field(..., description="Delete filters")

    class RPCSchema(BaseModel):
        function: str = Field(..., description="Function name")
        params: Optional[Dict] = Field(None, description="Function parameters")
    
    return [
        StructuredTool(
            name="select_from_supabase",
            description="Select data from a Supabase table",
            func=lambda table, columns, filters, order, limit, offset:
                integration.select(table, columns, filters, order, limit, offset),
            args_schema=SelectSchema
        ),
        StructuredTool(
            name="insert_into_supabase",
            description="Insert data into a Supabase table",
            func=lambda table, data, upsert: integration.insert(table, data, upsert),
            args_schema=InsertSchema
        ),
        StructuredTool(
            name="update_in_supabase",
            description="Update records in a Supabase table",
            func=lambda table, data, filters: integration.update(table, data, filters),
            args_schema=UpdateSchema
        ),
        StructuredTool(
            name="delete_from_supabase",
            description="Delete records from a Supabase table",
            func=lambda table, filters: integration.delete(table, filters),
            args_schema=DeleteSchema
        ),
        StructuredTool(
            name="call_supabase_rpc",
            description="Call a Postgres function via RPC",
            func=lambda function, params: integration.rpc(function, params),
            args_schema=RPCSchema
        )
    ] 