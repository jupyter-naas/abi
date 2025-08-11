from abi.workflow import Workflow, WorkflowConfiguration
from abi.workflow.workflow import WorkflowParameters
from dataclasses import dataclass
from pydantic import Field
from fastapi import APIRouter
from langchain_core.tools import StructuredTool, BaseTool
from typing import Any, Dict
from enum import Enum
import requests
import json
from datetime import datetime
from pathlib import Path


@dataclass
class ArtificialAnalysisWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for ArtificialAnalysisWorkflow.
    
    Attributes:
        api_key (str): Artificial Analysis API key
        base_url (str): Base URL for Artificial Analysis API
    """
    api_key: str
    base_url: str = "https://artificialanalysis.ai/api/v2"


class ArtificialAnalysisWorkflowParameters(WorkflowParameters):
    """Parameters for ArtificialAnalysisWorkflow execution.
    
    Attributes:
        endpoint (str): API endpoint to fetch (llms, text-to-image, etc.)
        include_categories (bool): Include category breakdowns for media endpoints
    """
    endpoint: str = Field(default="llms", description="API endpoint to fetch (llms, text-to-image, etc.)")
    include_categories: bool = Field(default=False, description="Include category breakdowns for media endpoints")


class ArtificialAnalysisWorkflow(Workflow):
    """Workflow for fetching and storing Artificial Analysis API data."""
    
    __configuration: ArtificialAnalysisWorkflowConfiguration
    
    def __init__(self, configuration: ArtificialAnalysisWorkflowConfiguration):
        self.__configuration = configuration

    def run_workflow(self, parameters: ArtificialAnalysisWorkflowParameters) -> Dict[str, Any]:
        """Execute the workflow to fetch and save Artificial Analysis data.
        
        Args:
            parameters: Workflow parameters containing endpoint and options
            
        Returns:
            Dict containing operation results and file information
        """
        print(f"🚀 Starting Artificial Analysis data fetch for {parameters.endpoint}")
        
        # Fetch data from API
        api_data = self._fetch_models_data(parameters.endpoint, parameters.include_categories)
        
        if api_data.get('status') == 'error':
            return {"status": "error", "message": "Failed to fetch data from API"}
        
        # Save raw API data as JSON with UTC timestamp
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
        filename = f"{timestamp}_{parameters.endpoint}_data.json"
        
        # Create storage directory
        storage_dir = Path("storage/datastore/core/modules/abi/ArtificialAnalysisWorkflow")
        storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Save raw API response
        output_file = storage_dir / filename
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(api_data, f, indent=2, ensure_ascii=False)
        
        models_count = len(api_data.get('data', []))
        
        print(f"💾 Saved {models_count} models to: {output_file}")
        print(f"📊 Endpoint: {parameters.endpoint}")
        print(f"🕐 Timestamp: {timestamp}")
        
        return {
            "status": "success",
            "endpoint": parameters.endpoint,
            "models_count": models_count,
            "output_file": str(output_file),
            "timestamp": timestamp
        }

    def _fetch_models_data(self, endpoint: str, include_categories: bool = False) -> Dict[str, Any]:
        """Fetch model data from Artificial Analysis API."""
        url = f"{self.__configuration.base_url}/data/{endpoint}/models"
        
        headers = {
            'Authorization': f'Bearer {self.__configuration.api_key}',
            'Content-Type': 'application/json'
        }
        
        params = {}
        if include_categories:
            params['include_categories'] = 'true'
        
        try:
            print(f"🔍 Fetching data from: {url}")
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            models_count = len(data.get('data', []))
            print(f"✅ Successfully fetched {models_count} models from {endpoint}")
            
            return {
                "status": "success",
                "data": data.get('data', []),
                "metadata": {
                    "endpoint": endpoint,
                    "total_models": models_count,
                    "fetched_at": datetime.utcnow().isoformat(),
                    "api_url": url
                }
            }
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching data: {e}")
            return {
                "status": "error",
                "error": str(e),
                "endpoint": endpoint
            }

    def as_tools(self) -> list[BaseTool]:
        """Returns a list of LangChain tools for this workflow.
        
        Returns:
            list[BaseTool]: List containing the workflow tool
        """
        return [
            StructuredTool(
                name="artificial_analysis_data_fetch",
                description="Fetch AI model data from Artificial Analysis API and save as timestamped JSON files",
                func=lambda **kwargs: self.run(ArtificialAnalysisWorkflowParameters(**kwargs)),
                args_schema=ArtificialAnalysisWorkflowParameters
            )
        ]

    def as_api(
        self,
        router: APIRouter,
        route_name: str = "",
        name: str = "",
        description: str = "",
        description_stream: str = "",
        tags: list[str | Enum] | None = None,
    ) -> None:
        if tags is None:
            tags = []
        return None