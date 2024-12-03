from typing import Dict, List, Optional, Union
import pandas as pd
from naas_drivers import gsheet

from lib.abi.integration.integration import Integration, IntegrationConnectionError, IntegrationConfiguration
from dataclasses import dataclass
from pydantic import BaseModel, Field

@dataclass
class GoogleSheetsIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for Google Sheets integration."""
    pass

class GoogleSheetsIntegration(Integration):

    __configuration: GoogleSheetsIntegrationConfiguration

    def __init__(self, configuration: GoogleSheetsIntegrationConfiguration):
        """Initialize Google Sheets client."""
        super().__init__(configuration)
        self.__configuration = configuration
        
        # Test connection by attempting to initialize gsheet
        try:
            gsheet.connect()
        except Exception as e:
            raise IntegrationConnectionError(f"Failed to connect to Google Sheets: {str(e)}")

    def read_sheet(self, spreadsheet_url: str, sheet_name: str) -> pd.DataFrame:
        """Read data from a Google Sheet."""
        try:
            return gsheet.connect(spreadsheet_url).get(sheet_name=sheet_name)
        except Exception as e:
            raise IntegrationConnectionError(f"Failed to read Google Sheet: {str(e)}")

    def write_sheet(self, spreadsheet_url: str, sheet_name: str, 
                   data: pd.DataFrame, append: bool = False) -> None:
        """Write data to a Google Sheet.
        
        Args:
            spreadsheet_url (str): The full URL of the Google Spreadsheet
            sheet_name (str): Name of the specific sheet to write to
            data (pd.DataFrame): DataFrame containing the data to write
            append (bool): If True, append to existing data; if False, overwrite
        """
        try:
            gsheet.connect(spreadsheet_url).send(
                sheet_name=sheet_name,
                data=data,
                append=append
            )
        except Exception as e:
            raise IntegrationConnectionError(f"Failed to write to Google Sheet: {str(e)}")

def as_tools(configuration: GoogleSheetsIntegrationConfiguration):
    from langchain_core.tools import StructuredTool
    
    integration = GoogleSheetsIntegration(configuration)

    class ReadSheetSchema(BaseModel):
        spreadsheet_url: str = Field(..., description="Full URL of the Google Spreadsheet")
        sheet_name: str = Field(..., description="Name of the sheet to read")

    class WriteSheetSchema(BaseModel):
        spreadsheet_url: str = Field(..., description="Full URL of the Google Spreadsheet")
        sheet_name: str = Field(..., description="Name of the sheet to write to")
        data: pd.DataFrame = Field(..., description="DataFrame containing the data to write")
        append: bool = Field(False, description="Whether to append to existing data")
    
    return [
        StructuredTool(
            name="read_google_sheet",
            description="Read data from a Google Sheet",
            func=lambda spreadsheet_url, sheet_name: integration.read_sheet(spreadsheet_url, sheet_name),
            args_schema=ReadSheetSchema
        ),
        StructuredTool(
            name="write_google_sheet",
            description="Write data to a Google Sheet",
            func=lambda spreadsheet_url, sheet_name, data, append=False: 
                integration.write_sheet(spreadsheet_url, sheet_name, pd.read_json(data), append),
            args_schema=WriteSheetSchema
        )
    ] 