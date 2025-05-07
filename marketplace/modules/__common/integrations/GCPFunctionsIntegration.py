from lib.abi.integration.integration import (
    Integration,
    IntegrationConfiguration,
    IntegrationConnectionError,
)
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from google.oauth2 import service_account
from google.cloud import functions_v1
from google.cloud.functions_v1 import CloudFunction
import requests

LOGO_URL = "https://static-00.iconduck.com/assets.00/google-cloud-functions-icon-512x460-5z61oi5w.png"


@dataclass
class GCPFunctionsIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for GCP Cloud Functions integration.

    Attributes:
        service_account_path (str): Path to service account JSON file
        project_id (str): GCP project ID
        location (str): Functions location (e.g., 'us-central1')
    """

    service_account_path: str
    project_id: str
    location: str


class GCPFunctionsIntegration(Integration):
    """GCP Cloud Functions API integration client using service account.

    This integration provides methods to interact with GCP Cloud Functions' API endpoints.
    """

    __configuration: GCPFunctionsIntegrationConfiguration

    def __init__(self, configuration: GCPFunctionsIntegrationConfiguration):
        """Initialize Cloud Functions client with service account credentials."""
        super().__init__(configuration)
        self.__configuration = configuration

        try:
            # Load service account credentials
            credentials = service_account.Credentials.from_service_account_file(
                self.__configuration.service_account_path
            )

            # Initialize client
            self.__client = functions_v1.CloudFunctionsServiceClient(
                credentials=credentials
            )
        except Exception as e:
            pass
            # logger.debug(f"Failed to initialize Cloud Functions API client: {str(e)}")

    def __format_function_data(self, function: CloudFunction) -> Dict:
        """Format function data for response.

        Args:
            function (CloudFunction): Function instance

        Returns:
            Dict: Formatted function data
        """
        return {
            "name": function.name.split("/")[-1],
            "description": function.description,
            "status": function.status.name,
            "entry_point": function.entry_point,
            "runtime": function.runtime,
            "timeout": str(function.timeout),
            "available_memory_mb": function.available_memory_mb,
            "service_account_email": function.service_account_email,
            "update_time": str(function.update_time),
            "version_id": function.version_id,
            "labels": dict(function.labels or {}),
            "environment_variables": dict(function.environment_variables or {}),
            "url": function.https_trigger.url if function.https_trigger else None,
        }

    def list_functions(
        self, show_deleted: bool = False, filter_str: Optional[str] = None
    ) -> List[Dict]:
        """List Cloud Functions in the project.

        Args:
            show_deleted (bool, optional): Include deleted functions. Defaults to False
            filter_str (str, optional): Filter string for functions

        Returns:
            List[Dict]: List of function information

        Raises:
            IntegrationConnectionError: If the operation fails
        """
        try:
            parent = f"projects/{self.__configuration.project_id}/locations/{self.__configuration.location}"
            request = functions_v1.ListFunctionsRequest(
                parent=parent, show_deleted=show_deleted, filter=filter_str
            )

            functions = self.__client.list_functions(request=request)
            return [self.__format_function_data(f) for f in functions]
        except Exception as e:
            raise IntegrationConnectionError(
                f"Cloud Functions operation failed: {str(e)}"
            )

    def get_function(self, function_name: str) -> Dict:
        """Get details of a specific function.

        Args:
            function_name (str): Name of the function

        Returns:
            Dict: Function information

        Raises:
            IntegrationConnectionError: If the operation fails
        """
        try:
            name = f"projects/{self.__configuration.project_id}/locations/{self.__configuration.location}/functions/{function_name}"
            function = self.__client.get_function(name=name)
            return self.__format_function_data(function)
        except Exception as e:
            raise IntegrationConnectionError(
                f"Cloud Functions operation failed: {str(e)}"
            )

    def call_function(
        self, function_name: str, data: Dict, timeout: Optional[float] = None
    ) -> Dict:
        """Call a Cloud Function via HTTP trigger.

        Args:
            function_name (str): Name or URL of the function
            data (Dict): Request data
            timeout (float, optional): Request timeout in seconds

        Returns:
            Dict: Function response

        Raises:
            IntegrationConnectionError: If the operation fails
        """
        try:
            # If function_name is not a URL, construct it
            if not function_name.startswith("http"):
                function_info = self.get_function(function_name)
                if not function_info.get("url"):
                    raise ValueError(
                        f"Function {function_name} does not have an HTTP trigger"
                    )
                url = function_info["url"]
            else:
                url = function_name

            response = requests.post(url, json=data, timeout=timeout)
            response.raise_for_status()

            try:
                return response.json()
            except ValueError:
                return {"status": "success", "text": response.text}
        except Exception as e:
            raise IntegrationConnectionError(
                f"Cloud Functions operation failed: {str(e)}"
            )

    def get_function_logs(
        self,
        function_name: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        page_size: int = 100,
    ) -> List[Dict]:
        """Get logs for a specific function.

        Args:
            function_name (str): Name of the function
            start_time (str, optional): Start time in RFC3339 format
            end_time (str, optional): End time in RFC3339 format
            page_size (int, optional): Maximum number of log entries. Defaults to 100

        Returns:
            List[Dict]: Function logs

        Raises:
            IntegrationConnectionError: If the operation fails
        """
        from google.cloud import logging_v2

        try:
            logging_client = logging_v2.Client(
                credentials=service_account.Credentials.from_service_account_file(
                    self.__configuration.service_account_path
                ),
                project=self.__configuration.project_id,
            )

            filter_str = [
                f'resource.type="cloud_function"',
                f'resource.labels.function_name="{function_name}"',
            ]

            if start_time:
                filter_str.append(f'timestamp >= "{start_time}"')
            if end_time:
                filter_str.append(f'timestamp <= "{end_time}"')

            entries = logging_client.list_entries(
                filter=" AND ".join(filter_str),
                page_size=page_size,
                order_by=logging_v2.DESCENDING,
            )

            return [
                {
                    "timestamp": str(entry.timestamp),
                    "severity": entry.severity,
                    "text_payload": entry.text_payload,
                    "json_payload": dict(entry.json_payload)
                    if entry.json_payload
                    else None,
                    "trace": entry.trace,
                    "labels": dict(entry.labels or {}),
                }
                for entry in entries
            ]
        except Exception as e:
            raise IntegrationConnectionError(
                f"Cloud Functions operation failed: {str(e)}"
            )


def as_tools(configuration: GCPFunctionsIntegrationConfiguration):
    """Convert GCP Functions integration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    integration = GCPFunctionsIntegration(configuration)

    class ListFunctionsSchema(BaseModel):
        show_deleted: bool = Field(
            default=False, description="Include deleted functions"
        )
        filter_str: Optional[str] = Field(
            None, description="Filter string for functions"
        )

    class GetFunctionSchema(BaseModel):
        function_name: str = Field(..., description="Name of the function")

    class CallFunctionSchema(BaseModel):
        function_name: str = Field(..., description="Name or URL of the function")
        data: Dict = Field(..., description="Request data")
        timeout: Optional[float] = Field(None, description="Request timeout in seconds")

    class GetLogsSchema(BaseModel):
        function_name: str = Field(..., description="Name of the function")
        start_time: Optional[str] = Field(
            None, description="Start time in RFC3339 format"
        )
        end_time: Optional[str] = Field(None, description="End time in RFC3339 format")
        page_size: int = Field(default=100, description="Maximum number of log entries")

    return [
        StructuredTool(
            name="gcpfunctions_list_functions",
            description="List Cloud Functions in the project",
            func=lambda show_deleted, filter_str: integration.list_functions(
                show_deleted, filter_str
            ),
            args_schema=ListFunctionsSchema,
        ),
        StructuredTool(
            name="gcpfunctions_get_function",
            description="Get details of a specific Cloud Function",
            func=lambda function_name: integration.get_function(function_name),
            args_schema=GetFunctionSchema,
        ),
        StructuredTool(
            name="gcpfunctions_call_function",
            description="Call a Cloud Function via HTTP trigger",
            func=lambda function_name, data, timeout: integration.call_function(
                function_name, data, timeout
            ),
            args_schema=CallFunctionSchema,
        ),
        StructuredTool(
            name="gcpfunctions_get_logs",
            description="Get logs for a specific Cloud Function",
            func=lambda function_name,
            start_time,
            end_time,
            page_size: integration.get_function_logs(
                function_name, start_time, end_time, page_size
            ),
            args_schema=GetLogsSchema,
        ),
    ]
