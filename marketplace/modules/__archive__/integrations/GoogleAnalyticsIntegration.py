from lib.abi.integration.integration import (
    Integration,
    IntegrationConfiguration,
    IntegrationConnectionError,
)
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Union
from google.oauth2 import service_account
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    RunReportRequest,
    RunRealtimeReportRequest,
    DateRange,
    Metric,
    Dimension,
    MetricType,
    FilterExpression,
    Filter,
    OrderBy,
)

LOGO_URL = (
    "https://logos-world.net/wp-content/uploads/2021/02/Google-Analytics-Logo.png"
)


@dataclass
class GoogleAnalyticsIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for Google Analytics integration.

    Attributes:
        service_account_path (str): Path to service account JSON file
        property_id (str): GA4 property ID (format: properties/XXXXXX)
    """

    service_account_path: str
    property_id: str


class GoogleAnalyticsIntegration(Integration):
    """Google Analytics Data API (GA4) integration client using service account.

    This integration provides methods to interact with Google Analytics' API endpoints.
    """

    __configuration: GoogleAnalyticsIntegrationConfiguration

    def __init__(self, configuration: GoogleAnalyticsIntegrationConfiguration):
        """Initialize Analytics client with service account credentials."""
        super().__init__(configuration)
        self.__configuration = configuration

        try:
            # Load service account credentials
            credentials = service_account.Credentials.from_service_account_file(
                self.__configuration.service_account_path,
                scopes=["https://www.googleapis.com/auth/analytics.readonly"],
            )

            # Initialize client
            self.__client = BetaAnalyticsDataClient(credentials=credentials)
        except Exception as e:
            pass
            # logger.debug(f"Failed to initialize Analytics API client: {str(e)}")

    def run_report(
        self,
        metrics: List[str],
        dimensions: Optional[List[str]] = None,
        date_ranges: Optional[List[Dict[str, str]]] = None,
        dimension_filters: Optional[Dict] = None,
        metric_filters: Optional[Dict] = None,
        offset: int = 0,
        limit: int = 10000,
    ) -> Dict:
        """Run a Google Analytics report.

        Args:
            metrics (List[str]): List of metrics
            dimensions (List[str], optional): List of dimensions
            date_ranges (List[Dict], optional): List of date ranges
            dimension_filters (Dict, optional): Dimension filter expressions
            metric_filters (Dict, optional): Metric filter expressions
            offset (int, optional): Results offset. Defaults to 0
            limit (int, optional): Maximum results. Defaults to 10000

        Returns:
            Dict: Report results

        Raises:
            IntegrationConnectionError: If the operation fails
        """
        try:
            request = RunReportRequest(
                property=f"properties/{self.__configuration.property_id}",
                metrics=[Metric(name=m) for m in metrics],
                dimensions=[Dimension(name=d) for d in (dimensions or [])],
                date_ranges=[
                    DateRange(**dr)
                    for dr in (
                        date_ranges or [{"start_date": "7daysAgo", "end_date": "today"}]
                    )
                ],
                offset=offset,
                limit=limit,
            )

            if dimension_filters:
                request.dimension_filter = FilterExpression(dimension_filters)
            if metric_filters:
                request.metric_filter = FilterExpression(metric_filters)

            response = self.__client.run_report(request)

            return self.__format_report_response(response)
        except Exception as e:
            raise IntegrationConnectionError(
                f"Google Analytics operation failed: {str(e)}"
            )

    def run_realtime_report(
        self,
        metrics: List[str],
        dimensions: Optional[List[str]] = None,
        dimension_filters: Optional[Dict] = None,
        metric_filters: Optional[Dict] = None,
        limit: int = 10000,
    ) -> Dict:
        """Run a Google Analytics realtime report.

        Args:
            metrics (List[str]): List of metrics
            dimensions (List[str], optional): List of dimensions
            dimension_filters (Dict, optional): Dimension filter expressions
            metric_filters (Dict, optional): Metric filter expressions
            limit (int, optional): Maximum results. Defaults to 10000

        Returns:
            Dict: Realtime report results

        Raises:
            IntegrationConnectionError: If the operation fails
        """
        try:
            request = RunRealtimeReportRequest(
                property=f"properties/{self.__configuration.property_id}",
                metrics=[Metric(name=m) for m in metrics],
                dimensions=[Dimension(name=d) for d in (dimensions or [])],
                limit=limit,
            )

            if dimension_filters:
                request.dimension_filter = FilterExpression(dimension_filters)
            if metric_filters:
                request.metric_filter = FilterExpression(metric_filters)

            response = self.__client.run_realtime_report(request)

            return self.__format_report_response(response)
        except Exception as e:
            raise IntegrationConnectionError(
                f"Google Analytics operation failed: {str(e)}"
            )

    def __format_report_response(self, response: Any) -> Dict:
        """Format the API response into a more usable structure.

        Args:
            response: Raw API response

        Returns:
            Dict: Formatted response
        """
        result = {
            "row_count": response.row_count,
            "rows": [],
            "totals": [],
            "maximums": [],
            "minimums": [],
            "metadata": {
                "metrics": [m.name for m in response.metric_headers],
                "dimensions": [d.name for d in response.dimension_headers]
                if response.dimension_headers
                else [],
            },
        }

        # Process rows
        for row in response.rows:
            row_data = {}

            # Add dimensions
            for i, dimension in enumerate(row.dimension_values):
                row_data[result["metadata"]["dimensions"][i]] = dimension.value

            # Add metrics
            for i, metric in enumerate(row.metric_values):
                row_data[result["metadata"]["metrics"][i]] = metric.value

            result["rows"].append(row_data)

        # Process totals, maximums, and minimums if available
        if hasattr(response, "totals") and response.totals:
            result["totals"] = [
                {
                    m: v.value
                    for m, v in zip(result["metadata"]["metrics"], total.metric_values)
                }
                for total in response.totals
            ]

        if hasattr(response, "maximums") and response.maximums:
            result["maximums"] = [
                {
                    m: v.value
                    for m, v in zip(
                        result["metadata"]["metrics"], maximum.metric_values
                    )
                }
                for maximum in response.maximums
            ]

        if hasattr(response, "minimums") and response.minimums:
            result["minimums"] = [
                {
                    m: v.value
                    for m, v in zip(
                        result["metadata"]["metrics"], minimum.metric_values
                    )
                }
                for minimum in response.minimums
            ]

        return result


def as_tools(configuration: GoogleAnalyticsIntegrationConfiguration):
    """Convert Google Analytics integration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    integration = GoogleAnalyticsIntegration(configuration)

    class RunReportSchema(BaseModel):
        metrics: List[str] = Field(
            ..., description="List of metrics (e.g., 'screenPageViews', 'sessions')"
        )
        dimensions: Optional[List[str]] = Field(
            None, description="List of dimensions (e.g., 'date', 'country')"
        )
        date_ranges: Optional[List[Dict[str, str]]] = Field(
            None,
            description="List of date ranges (e.g., [{'start_date': '7daysAgo', 'end_date': 'today'}])",
        )
        dimension_filters: Optional[Dict] = Field(
            None, description="Dimension filter expressions"
        )
        metric_filters: Optional[Dict] = Field(
            None, description="Metric filter expressions"
        )
        offset: int = Field(default=0, description="Results offset")
        limit: int = Field(default=10000, description="Maximum results")

    class RunRealtimeReportSchema(BaseModel):
        metrics: List[str] = Field(
            ..., description="List of metrics (e.g., 'activeUsers', 'screenPageViews')"
        )
        dimensions: Optional[List[str]] = Field(
            None, description="List of dimensions (e.g., 'country', 'city')"
        )
        dimension_filters: Optional[Dict] = Field(
            None, description="Dimension filter expressions"
        )
        metric_filters: Optional[Dict] = Field(
            None, description="Metric filter expressions"
        )
        limit: int = Field(default=10000, description="Maximum results")

    return [
        StructuredTool(
            name="googleanalytics_run_report",
            description="Run a Google Analytics report",
            func=lambda metrics,
            dimensions,
            date_ranges,
            dimension_filters,
            metric_filters,
            offset,
            limit: integration.run_report(
                metrics,
                dimensions,
                date_ranges,
                dimension_filters,
                metric_filters,
                offset,
                limit,
            ),
            args_schema=RunReportSchema,
        ),
        StructuredTool(
            name="googleanalytics_run_realtime_report",
            description="Run a Google Analytics realtime report",
            func=lambda metrics,
            dimensions,
            dimension_filters,
            metric_filters,
            limit: integration.run_realtime_report(
                metrics, dimensions, dimension_filters, metric_filters, limit
            ),
            args_schema=RunRealtimeReportSchema,
        ),
    ]
