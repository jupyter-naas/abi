from lib.abi.integration.integration import Integration, IntegrationConfiguration, IntegrationConnectionError
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Union
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

LOGO_URL = "https://upload.wikimedia.org/wikipedia/commons/thumb/3/30/Google_Sheets_logo_%282014-2020%29.svg/1498px-Google_Sheets_logo_%282014-2020%29.svg.png"

@dataclass
class GoogleSheetsIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for Google Sheets integration.
    
    Attributes:
        service_account_path (str): Path to service account JSON file
        subject_email (str): Email of the user to impersonate
        scopes (List[str]): List of required API scopes
    """
    service_account_path: str
    subject_email: str
    scopes: List[str] = None

    def __post_init__(self):
        if self.scopes is None:
            self.scopes = ['https://www.googleapis.com/auth/spreadsheets']

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

        try:
            # Load service account credentials
            credentials = service_account.Credentials.from_service_account_file(
                self.__configuration.service_account_path,
                scopes=self.__configuration.scopes
            )

            # Create delegated credentials for impersonation
            delegated_credentials = credentials.with_subject(self.__configuration.subject_email)
            
            # Build the service
            self.__service = build('sheets', 'v4', credentials=delegated_credentials)
        except Exception as e:
            pass
            # logger.debug(f"Failed to initialize Sheets API client: {str(e)}")

    def get_values(self,
                  spreadsheet_id: str,
                  range_name: str,
                  major_dimension: str = "ROWS") -> List[List[Any]]:
        """Get values from a spreadsheet range.
        
        Args:
            spreadsheet_id (str): Spreadsheet ID
            range_name (str): Range in A1 notation
            major_dimension (str, optional): Major dimension. Defaults to "ROWS"
            
        Returns:
            List[List[Any]]: Values in the range
            
        Raises:
            IntegrationConnectionError: If the request fails
        """
        try:
            result = self.__service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                majorDimension=major_dimension
            ).execute()
            return result.get('values', [])
        except HttpError as e:
            raise IntegrationConnectionError(f"Google Sheets API request failed: {str(e)}")

    def update_values(self,
                     spreadsheet_id: str,
                     range_name: str,
                     values: List[List[Any]],
                     major_dimension: str = "ROWS",
                     value_input_option: str = "RAW") -> Dict:
        """Update values in a spreadsheet range.
        
        Args:
            spreadsheet_id (str): Spreadsheet ID
            range_name (str): Range in A1 notation
            values (List[List[Any]]): Values to update
            major_dimension (str, optional): Major dimension. Defaults to "ROWS"
            value_input_option (str, optional): How to interpret input. Defaults to "RAW"
            
        Returns:
            Dict: Update result
            
        Raises:
            IntegrationConnectionError: If the request fails
        """
        try:
            body = {
                'values': values,
                'majorDimension': major_dimension
            }
            
            result = self.__service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                body=body,
                valueInputOption=value_input_option
            ).execute()
            return result
        except HttpError as e:
            raise IntegrationConnectionError(f"Google Sheets API request failed: {str(e)}")

    def append_values(self,
                     spreadsheet_id: str,
                     range_name: str,
                     values: List[List[Any]],
                     major_dimension: str = "ROWS",
                     value_input_option: str = "RAW",
                     insert_data_option: str = "INSERT_ROWS") -> Dict:
        """Append values to a spreadsheet range.
        
        Args:
            spreadsheet_id (str): Spreadsheet ID
            range_name (str): Range in A1 notation
            values (List[List[Any]]): Values to append
            major_dimension (str, optional): Major dimension. Defaults to "ROWS"
            value_input_option (str, optional): How to interpret input. Defaults to "RAW"
            insert_data_option (str, optional): How to insert data. Defaults to "INSERT_ROWS"
            
        Returns:
            Dict: Append result
            
        Raises:
            IntegrationConnectionError: If the request fails
        """
        try:
            body = {
                'values': values,
                'majorDimension': major_dimension
            }
            
            result = self.__service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                body=body,
                valueInputOption=value_input_option,
                insertDataOption=insert_data_option
            ).execute()
            return result
        except HttpError as e:
            raise IntegrationConnectionError(f"Google Sheets API request failed: {str(e)}")

    def clear_values(self,
                    spreadsheet_id: str,
                    range_name: str) -> Dict:
        """Clear values in a spreadsheet range.
        
        Args:
            spreadsheet_id (str): Spreadsheet ID
            range_name (str): Range in A1 notation
            
        Returns:
            Dict: Clear result
            
        Raises:
            IntegrationConnectionError: If the request fails
        """
        try:
            result = self.__service.spreadsheets().values().clear(
                spreadsheetId=spreadsheet_id,
                range=range_name
            ).execute()
            return result
        except HttpError as e:
            raise IntegrationConnectionError(f"Google Sheets API request failed: {str(e)}")

    def create_spreadsheet(self,
                         title: str,
                         sheets: Optional[List[Dict]] = None) -> Dict:
        """Create a new spreadsheet.
        
        Args:
            title (str): Spreadsheet title
            sheets (List[Dict], optional): List of sheet configurations
            
        Returns:
            Dict: Created spreadsheet data
            
        Raises:
            IntegrationConnectionError: If the request fails
        """
        try:
            spreadsheet = {
                'properties': {
                    'title': title
                }
            }
            
            if sheets:
                spreadsheet['sheets'] = sheets
                
            result = self.__service.spreadsheets().create(
                body=spreadsheet
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
        )
    ] 