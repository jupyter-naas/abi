from lib.abi.integration.integration import Integration, IntegrationConfiguration, IntegrationConnectionError
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import pandas as pd
import json

LOGO_URL = "https://upload.wikimedia.org/wikipedia/commons/thumb/3/30/Google_Sheets_logo_%282014-2020%29.svg/1498px-Google_Sheets_logo_%282014-2020%29.svg.png"

@dataclass
class GoogleSheetsIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for Google Sheets integration.
    
    Attributes:
        service_account_path (str): Path to service account JSON file
        scopes (List[str]): List of required API scopes
    """
    service_account_path: str
    scopes = ['https://www.googleapis.com/auth/spreadsheets']

class GoogleSheetsIntegration(Integration):
    """Google Sheets API integration client using service account.
    
    This integration provides methods to interact with Google Sheets' API endpoints
    for spreadsheet operations.
    """

    __configuration: GoogleSheetsIntegrationConfiguration

    def __init__(self, configuration: GoogleSheetsIntegrationConfiguration):
        """Initialize Sheets client with service account credentials."""
        super().__init__(configuration)
        self.__configuration = configuration
        credentials = service_account.Credentials.from_service_account_file(
            self.__configuration.service_account_path,
            scopes=self.__configuration.scopes
        )
        self.__service = build('sheets', 'v4', credentials=credentials)

    def get_spreadsheet_id_from_url(self, url: str) -> str:
        """Extract spreadsheet ID from a Google Sheets URL.
        
        Args:
            url (str): Google Sheets URL
            
        Returns:
            str: Spreadsheet ID
            
        Example:
            >>> url = "https://docs.google.com/spreadsheets/d/1z8_oCAolAIaA4Yif3E62x6jtnFYIy1PR43BksIOYKQ4/edit#gid=873987148"
            >>> GoogleSheetsIntegration.get_spreadsheet_id_from_url(url)
            "1z8_oCAolAIaA4Yif3E62x6jtnFYIy1PR43BksIOYKQ4"
        """
        # Extract ID from between /d/ and the next /
        start = url.find("/d/") + 3
        end = url.find("/", start)
        return url[start:end]
    
    def list_sheets(self, spreadsheet_url: str) -> List[Dict[str, Any]]:
        """List all sheets in a spreadsheet.
        
        Args:
            spreadsheet_url (str): Spreadsheet URL or ID
            
        Returns:
            List[Dict[str, Any]]: List of sheet metadata including sheetId, title, etc.
            
        Raises:
            IntegrationConnectionError: If the request fails
        """
        try:
            spreadsheet_id = self.get_spreadsheet_id_from_url(spreadsheet_url)
            result = self.__service.spreadsheets().get(
                spreadsheetId=spreadsheet_id
            ).execute()
            return result.get('sheets', [])
        except HttpError as e:
            raise IntegrationConnectionError(f"Google Sheets API request failed: {str(e)}")
        
    def create_sheet(self, spreadsheet_url: str, sheet_name: str) -> Dict[str, Any]:
        """Create a new sheet in an existing spreadsheet.
        
        Args:
            spreadsheet_url (str): Spreadsheet URL or ID
            sheet_name (str): Name of the new sheet
            
        Returns:
            Dict[str, Any]: Response containing the new sheet's metadata
            
        Raises:
            IntegrationConnectionError: If the request fails
        """
        try:
            spreadsheet_id = self.get_spreadsheet_id_from_url(spreadsheet_url)
            request_body = {
                'requests': [{
                    'addSheet': {
                        'properties': {
                            'title': sheet_name
                        }
                    }
                }]
            }
            
            result = self.__service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body=request_body
            ).execute()
            
            return result['replies'][0]['addSheet']['properties']
            
        except HttpError as e:
            raise IntegrationConnectionError(f"Google Sheets API request failed: {str(e)}")

    def update_sheet(self, spreadsheet_url: str, sheet_id: int, properties: Dict[str, Any]) -> Dict[str, Any]:
        """Update properties of an existing sheet.
        
        Args:
            spreadsheet_url (str): Spreadsheet URL or ID
            sheet_id (int): ID of the sheet to update
            properties (Dict[str, Any]): Properties to update (e.g. title, gridProperties)
            
        Returns:
            Dict[str, Any]: Response containing the updated sheet's metadata
            
        Raises:
            IntegrationConnectionError: If the request fails
        """
        try:
            spreadsheet_id = self.get_spreadsheet_id_from_url(spreadsheet_url)
            request_body = {
                'requests': [{
                    'updateSheetProperties': {
                        'properties': {
                            'sheetId': sheet_id,
                            **properties
                        },
                        'fields': ','.join(properties.keys())
                    }
                }]
            }
            
            result = self.__service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body=request_body
            ).execute()
            
            return result
            
        except HttpError as e:
            raise IntegrationConnectionError(f"Google Sheets API request failed: {str(e)}")

    def delete_sheet(self, spreadsheet_url: str, sheet_id: int) -> Dict[str, Any]:
        """Delete a sheet from a spreadsheet.
        
        Args:
            spreadsheet_url (str): Spreadsheet URL or ID
            sheet_id (int): ID of the sheet to delete
            
        Returns:
            Dict[str, Any]: Response from the API
            
        Raises:
            IntegrationConnectionError: If the request fails
        """
        try:
            spreadsheet_id = self.get_spreadsheet_id_from_url(spreadsheet_url)
            request_body = {
                'requests': [{
                    'deleteSheet': {
                        'sheetId': sheet_id
                    }
                }]
            }
            
            result = self.__service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body=request_body
            ).execute()
            
            return result
            
        except HttpError as e:
            raise IntegrationConnectionError(f"Google Sheets API request failed: {str(e)}")
        
    def get_values(self, spreadsheet_url: str, sheet_name: str) -> Dict:
        """Get all values from a sheet and return as a pandas DataFrame.
        
        Args:
            spreadsheet_url (str): Spreadsheet URL or ID
            sheet_name (str): Name of the sheet to read
            
        Returns:
            pd.DataFrame: DataFrame containing sheet data with column headers
            
        Raises:
            IntegrationConnectionError: If the request fails
            ValueError: If sheet is empty or has invalid format
        """
        try:
            spreadsheet_id = self.get_spreadsheet_id_from_url(spreadsheet_url)
            range_name = f"{sheet_name}!A1:ZZ"
            
            result = self.__service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                majorDimension="ROWS"
            ).execute()
            
            values = result.get('values', [])
            if not values:
                raise ValueError("Sheet is empty")
                
            # First row as headers
            headers = values[0]
            data = values[1:]
            
            # Create DataFrame
            df = pd.DataFrame(data, columns=headers)
            return df.to_dict(orient="records")
            
        except HttpError as e:
            raise IntegrationConnectionError(f"Google Sheets API request failed: {str(e)}")

    def get(self, sheet_name: str, items_per_page: int = 1000000) -> pd.DataFrame:
        """Get data from a sheet as a pandas DataFrame.
        
        Args:
            sheet_name (str): Name of the sheet to read
            items_per_page (int): Number of items to return per page. Defaults to 1000000.
            
        Returns:
            pd.DataFrame: DataFrame containing sheet data
            
        Raises:
            IntegrationConnectionError: If the request fails
            ValueError: If sheet is empty or has invalid format
        """
        try:
            range_name = f"{sheet_name}!A1:ZZ"
            
            result = self.__service.spreadsheets().values().get(
                spreadsheetId=self.__spreadsheet_id,
                range=range_name,
                majorDimension="ROWS"
            ).execute()
            
            values = result.get('values', [])
            if not values:
                return pd.DataFrame()
                
            # First row as headers
            headers = values[0]
            data = values[1:items_per_page+1]  # Limit to items_per_page
            
            # Create DataFrame
            return pd.DataFrame(data, columns=headers)
            
        except HttpError as e:
            raise IntegrationConnectionError(f"Google Sheets API request failed: {str(e)}")
        
    def send(self, spreadsheet_url: str, sheet_name: str, data: Union[pd.DataFrame, List[Dict]], append: bool = True) -> Dict:
        """Send data to a Google Sheet, either appending or overwriting existing data.
        
        Args:
            spreadsheet_url (str): Spreadsheet URL or ID
            sheet_name (str): Name of the sheet to write to
            data (Union[pd.DataFrame, List[Dict]]): Data to send, either as DataFrame or list of dicts
            append (bool): Whether to append (True) or overwrite (False) existing data. Defaults to True.
            
        Returns:
            Dict: Response from the API
            
        Raises:
            IntegrationConnectionError: If the request fails
            ValueError: If data is empty or has invalid format
        """
        try:
            spreadsheet_id = self.get_spreadsheet_id_from_url(spreadsheet_url)
            range_name = f"{sheet_name}!A1:ZZ"

            # Convert DataFrame to list of dicts if needed
            if isinstance(data, pd.DataFrame):
                data = data.astype(str).to_dict(orient="records")
                
            if not data:
                raise ValueError("Data is empty")
                
            # Convert list of dicts to list of lists for API
            headers = list(data[0].keys())
            values = [headers]
            for row in data:
                values.append([str(row.get(header, '')) for header in headers])
                
            if not append:
                # Clear existing data first
                try:
                    self.__service.spreadsheets().values().clear(
                        spreadsheetId=spreadsheet_id,
                        range=range_name
                    ).execute()
                except HttpError:
                    pass
                    
            # Append or update values
            if append:
                result = self.__service.spreadsheets().values().append(
                    spreadsheetId=spreadsheet_id,
                    range=range_name,
                    valueInputOption='RAW',
                    insertDataOption='INSERT_ROWS',
                    body={'values': values}
                ).execute()
            else:
                result = self.__service.spreadsheets().values().update(
                    spreadsheetId=spreadsheet_id,
                    range=range_name,
                    valueInputOption='RAW',
                    body={'values': values}
                ).execute()
                
            return result
            
        except HttpError as e:
            raise IntegrationConnectionError(f"Google Sheets API request failed: {str(e)}")

def as_tools(configuration: GoogleSheetsIntegrationConfiguration):
    """Convert Google Sheets integration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field
    
    integration = GoogleSheetsIntegration(configuration)
    
    class GetValuesSchema(BaseModel):
        spreadsheet_id: str = Field(..., description="Spreadsheet ID")
        range_name: str = Field(..., description="Range in A1 notation")
        major_dimension: str = Field(default="ROWS", description="Major dimension")

    class UpdateValuesSchema(BaseModel):
        spreadsheet_id: str = Field(..., description="Spreadsheet ID")
        range_name: str = Field(..., description="Range in A1 notation")
        values: List[List[Any]] = Field(..., description="Values to update")
        major_dimension: str = Field(default="ROWS", description="Major dimension")
        value_input_option: str = Field(default="RAW", description="How to interpret input")

    class AppendValuesSchema(BaseModel):
        spreadsheet_id: str = Field(..., description="Spreadsheet ID")
        range_name: str = Field(..., description="Range in A1 notation")
        values: List[List[Any]] = Field(..., description="Values to append")
        major_dimension: str = Field(default="ROWS", description="Major dimension")
        value_input_option: str = Field(default="RAW", description="How to interpret input")
        insert_data_option: str = Field(default="INSERT_ROWS", description="How to insert data")

    class ClearValuesSchema(BaseModel):
        spreadsheet_id: str = Field(..., description="Spreadsheet ID")
        range_name: str = Field(..., description="Range in A1 notation")

    class CreateSpreadsheetSchema(BaseModel):
        title: str = Field(..., description="Spreadsheet title")
        sheets: Optional[List[Dict]] = Field(None, description="List of sheet configurations")

    class ListSheetsSchema(BaseModel):
        spreadsheet_id: str = Field(..., description="Spreadsheet ID")
    
    return [
        StructuredTool(
            name="googlesheets_get_sheets_values",
            description="Get values from a Google Sheets range",
            func=lambda spreadsheet_id, range_name, major_dimension: integration.get_values(
                spreadsheet_id, range_name, major_dimension
            ),
            args_schema=GetValuesSchema
        ),
        StructuredTool(
            name="googlesheets_update_sheets_values",
            description="Update values in a Google Sheets range",
            func=lambda spreadsheet_id, range_name, values, major_dimension, value_input_option: 
                integration.update_values(spreadsheet_id, range_name, values, major_dimension, value_input_option),
            args_schema=UpdateValuesSchema
        ),
        StructuredTool(
            name="googlesheets_append_sheets_values",
            description="Append values to a Google Sheets range",
            func=lambda spreadsheet_id, range_name, values, major_dimension, value_input_option, insert_data_option:
                integration.append_values(spreadsheet_id, range_name, values, major_dimension, 
                                       value_input_option, insert_data_option),
            args_schema=AppendValuesSchema
        ),
        StructuredTool(
            name="googlesheets_clear_sheets_values",
            description="Clear values in a Google Sheets range",
            func=lambda spreadsheet_id, range_name: integration.clear_values(spreadsheet_id, range_name),
            args_schema=ClearValuesSchema
        ),
        StructuredTool(
            name="googlesheets_create_spreadsheet",
            description="Create a new Google Spreadsheet",
            func=lambda title, sheets: integration.create_spreadsheet(title, sheets),
            args_schema=CreateSpreadsheetSchema
        ),
        StructuredTool(
            name="googlesheets_list_sheets",
            description="List all sheets in a Google Spreadsheet",
            func=lambda spreadsheet_id: integration.list_sheets(spreadsheet_id),
            args_schema=ListSheetsSchema
        )
    ] 