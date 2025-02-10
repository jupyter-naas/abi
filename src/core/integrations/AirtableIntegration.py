from lib.abi.integration.integration import Integration, IntegrationConfiguration, IntegrationConnectionError
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
import requests

LOGO_URL = "https://logo.clearbit.com/airtable.com"

@dataclass
class AirtableIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for Airtable integration.
    
    Attributes:
        api_key (str): Airtable Personal Access Token
        base_id (str): Airtable base ID
        base_url (str): Base URL for Airtable API. Defaults to "https://api.airtable.com/v0"
    """
    api_key: str
    base_id: str
    base_url: str = "https://api.airtable.com/v0"

class AirtableIntegration(Integration):
    """Airtable API integration client.
    
    This integration provides methods to interact with Airtable's API endpoints
    for database operations.
    """

    __configuration: AirtableIntegrationConfiguration

    def __init__(self, configuration: AirtableIntegrationConfiguration):
        """Initialize Airtable client with API key."""
        super().__init__(configuration)
        self.__configuration = configuration
        
        self.headers = {
            "Authorization": f"Bearer {self.__configuration.api_key}",
            "Content-Type": "application/json"
        }

    def _make_request(self, endpoint: str, method: str = "GET", params: Dict = None, json: Dict = None) -> Dict:
        """Make HTTP request to Airtable API.
        
        Args:
            endpoint (str): API endpoint
            method (str): HTTP method (GET, POST, etc.). Defaults to "GET"
            params (Dict, optional): Query parameters. Defaults to None.
            json (Dict, optional): JSON body for requests. Defaults to None.
            
        Returns:
            Dict: Response JSON
            
        Raises:
            IntegrationConnectionError: If request fails
        """
        url = f"{self.__configuration.base_url}/{self.__configuration.base_id}{endpoint}"
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                params=params,
                json=json
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise IntegrationConnectionError(f"Airtable API request failed: {str(e)}")

    def list_records(self, 
                    table_name: str, 
                    max_records: Optional[int] = None,
                    view: Optional[str] = None,
                    formula: Optional[str] = None) -> List[Dict]:
        """List records from a table.
        
        Args:
            table_name (str): Name of the table
            max_records (int, optional): Maximum number of records to return
            view (str, optional): Name of the view to use
            formula (str, optional): Formula to filter records
            
        Returns:
            List[Dict]: List of records
        """
        params = {}
        if max_records:
            params["maxRecords"] = max_records
        if view:
            params["view"] = view
        if formula:
            params["filterByFormula"] = formula
            
        response = self._make_request(f"/{table_name}", params=params)
        return response.get("records", [])

    def get_record(self, table_name: str, record_id: str) -> Dict:
        """Get a specific record.
        
        Args:
            table_name (str): Name of the table
            record_id (str): Record ID
            
        Returns:
            Dict: Record data
        """
        return self._make_request(f"/{table_name}/{record_id}")

    def create_records(self, table_name: str, records: List[Dict]) -> Dict:
        """Create new records.
        
        Args:
            table_name (str): Name of the table
            records (List[Dict]): List of records to create
            
        Returns:
            Dict: Created records data
        """
        return self._make_request(
            f"/{table_name}",
            method="POST",
            json={"records": records}
        )

    def update_records(self, table_name: str, records: List[Dict]) -> Dict:
        """Update existing records.
        
        Args:
            table_name (str): Name of the table
            records (List[Dict]): List of records to update
            
        Returns:
            Dict: Updated records data
        """
        return self._make_request(
            f"/{table_name}",
            method="PATCH",
            json={"records": records}
        )

    def delete_records(self, table_name: str, record_ids: List[str]) -> Dict:
        """Delete records.
        
        Args:
            table_name (str): Name of the table
            record_ids (List[str]): List of record IDs to delete
            
        Returns:
            Dict: Deletion confirmation
        """
        params = {"records[]": record_ids}
        return self._make_request(
            f"/{table_name}",
            method="DELETE",
            params=params
        )

def as_tools(configuration: AirtableIntegrationConfiguration):
    """Convert Airtable integration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field
    
    integration = AirtableIntegration(configuration)
    
    class ListRecordsSchema(BaseModel):
        table_name: str = Field(..., description="Name of the table")
        max_records: Optional[int] = Field(None, description="Maximum number of records to return")
        view: Optional[str] = Field(None, description="Name of the view to use")
        formula: Optional[str] = Field(None, description="Formula to filter records")

    class GetRecordSchema(BaseModel):
        table_name: str = Field(..., description="Name of the table")
        record_id: str = Field(..., description="Record ID")

    class CreateRecordsSchema(BaseModel):
        table_name: str = Field(..., description="Name of the table")
        records: List[Dict[str, Any]] = Field(..., description="List of records to create")

    class UpdateRecordsSchema(BaseModel):
        table_name: str = Field(..., description="Name of the table")
        records: List[Dict[str, Any]] = Field(..., description="List of records to update")

    class DeleteRecordsSchema(BaseModel):
        table_name: str = Field(..., description="Name of the table")
        record_ids: List[str] = Field(..., description="List of record IDs to delete")
    
    return [
        StructuredTool(
            name="list_airtable_records",
            description="List records from an Airtable table",
            func=lambda table_name, max_records, view, formula: integration.list_records(
                table_name, max_records, view, formula
            ),
            args_schema=ListRecordsSchema
        ),
        StructuredTool(
            name="get_airtable_record",
            description="Get a specific record from an Airtable table",
            func=lambda table_name, record_id: integration.get_record(table_name, record_id),
            args_schema=GetRecordSchema
        ),
        StructuredTool(
            name="create_airtable_records",
            description="Create new records in an Airtable table",
            func=lambda table_name, records: integration.create_records(table_name, records),
            args_schema=CreateRecordsSchema
        ),
        StructuredTool(
            name="update_airtable_records",
            description="Update existing records in an Airtable table",
            func=lambda table_name, records: integration.update_records(table_name, records),
            args_schema=UpdateRecordsSchema
        ),
        StructuredTool(
            name="delete_airtable_records",
            description="Delete records from an Airtable table",
            func=lambda table_name, record_ids: integration.delete_records(table_name, record_ids),
            args_schema=DeleteRecordsSchema
        )
    ]  