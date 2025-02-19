from src.core.integrations.GoogleSheetsIntegration import (
    GoogleSheetsIntegration,
    GoogleSheetsIntegrationConfiguration
)
from abi import logger
from src import secret

# Initialize configuration
configuration = GoogleSheetsIntegrationConfiguration(
    service_account_path=secret.get("GOOGLE_SERVICE_ACCOUNT_PATH"),
)

# Initialize integration
google_sheets = GoogleSheetsIntegration(configuration)

# Test list sheets
spreadsheet_url = "https://docs.google.com/spreadsheets/d/1z8_oCAolAIaA4Yif3E62x6jtnFYIy1PR43BksIOYKQ4/edit#gid=873987148"
sheets = google_sheets.list_sheets(spreadsheet_url)
# logger.info(sheets)

# Test get values
sheet_name = "POSTS"
values = google_sheets.get(spreadsheet_url, sheet_name)
logger.info(values)