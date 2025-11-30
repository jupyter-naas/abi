import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Dict, Set

import requests
from fastapi import APIRouter
from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core.workflow import Workflow, WorkflowConfiguration
from naas_abi_core.workflow.workflow import WorkflowParameters
from pydantic import Field


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
        validate_agents_only (bool): Only generate ontology for modules with active agents
    """

    endpoint: Annotated[
        str, Field(description="API endpoint to fetch (llms, text-to-image, etc.)")
    ] = "llms"
    include_categories: Annotated[
        bool, Field(description="Include category breakdowns for media endpoints")
    ] = False
    validate_agents_only: Annotated[
        bool, Field(description="Only generate ontology for modules with active agents")
    ] = True


class ArtificialAnalysisWorkflow(Workflow):
    """Workflow for fetching and storing Artificial Analysis API data."""

    __configuration: ArtificialAnalysisWorkflowConfiguration

    def __init__(self, configuration: ArtificialAnalysisWorkflowConfiguration):
        self.__configuration = configuration

    def run_workflow(
        self, parameters: ArtificialAnalysisWorkflowParameters
    ) -> Dict[str, Any]:
        """Execute the workflow to fetch and save Artificial Analysis data.

        Args:
            parameters: Workflow parameters containing endpoint and options

        Returns:
            Dict containing operation results and file information
        """
        print(f"🚀 Starting Artificial Analysis data fetch for {parameters.endpoint}")

        # Step 1: Get valid modules with agents
        valid_modules = (
            self._get_modules_with_agents()
            if parameters.validate_agents_only
            else set()
        )

        if parameters.validate_agents_only:
            print(
                f"🤖 Found {len(valid_modules)} modules with active agents: {', '.join(sorted(valid_modules))}"
            )

        # Step 2: Fetch data from API
        api_data = self._fetch_models_data(
            parameters.endpoint, parameters.include_categories
        )

        if api_data.get("status") == "error":
            return {"status": "error", "message": "Failed to fetch data from API"}

        # Step 3: Filter data for valid modules only
        filtered_data = api_data
        if parameters.validate_agents_only and valid_modules:
            filtered_data = self._filter_data_for_valid_modules(api_data, valid_modules)

        # Step 4: Save filtered data
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        filename = f"{timestamp}_{parameters.endpoint}_data.json"

        # Create storage directory
        storage_dir = Path(
            "storage/datastore/core/modules/abi/ArtificialAnalysisWorkflow"
        )
        storage_dir.mkdir(parents=True, exist_ok=True)

        # Save filtered API response
        output_file = storage_dir / filename
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(filtered_data, f, indent=2, ensure_ascii=False)

        models_count = len(filtered_data.get("data", []))
        original_count = len(api_data.get("data", []))

        print(f"💾 Saved {models_count}/{original_count} models to: {output_file}")
        print(f"📊 Endpoint: {parameters.endpoint}")
        print(f"🕐 Timestamp: {timestamp}")

        if parameters.validate_agents_only:
            print("✅ Filtered to models with corresponding agents only")

        return {
            "status": "success",
            "endpoint": parameters.endpoint,
            "models_count": models_count,
            "original_count": original_count,
            "valid_modules": list(valid_modules) if valid_modules else [],
            "output_file": str(output_file),
            "timestamp": timestamp,
        }

    def _fetch_models_data(
        self, endpoint: str, include_categories: bool = False
    ) -> Dict[str, Any]:
        """Fetch model data from Artificial Analysis API."""
        # Different URL structure for LLMs vs media endpoints
        if endpoint == "llms":
            url = f"{self.__configuration.base_url}/data/llms/models"
        else:
            # Media endpoints like text-to-image, text-to-speech, etc.
            url = f"{self.__configuration.base_url}/data/media/{endpoint}"

        headers = {
            "x-api-key": self.__configuration.api_key,
            "Content-Type": "application/json",
        }

        params = {}
        if include_categories:
            params["include_categories"] = "true"

        try:
            print(f"🔍 Fetching data from: {url}")
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()

            data = response.json()
            models_count = len(data.get("data", []))
            print(f"✅ Successfully fetched {models_count} models from {endpoint}")

            return {
                "status": "success",
                "data": data.get("data", []),
                "metadata": {
                    "endpoint": endpoint,
                    "total_models": models_count,
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "api_url": url,
                },
            }

        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching data: {e}")
            return {"status": "error", "error": str(e), "endpoint": endpoint}

    def _get_modules_with_agents(self) -> Set[str]:
        """Get set of module names that have agents folders with *Agent.py files.

        Returns:
            Set[str]: Module names that have active agents
        """
        valid_modules: Set[str] = set()
        core_modules_path = Path("src/core/modules")

        if not core_modules_path.exists():
            print(f"⚠️  Core modules path not found: {core_modules_path}")
            return valid_modules

        print(f"🔍 Scanning for modules with agents in: {core_modules_path}")

        # Scan each module directory
        for module_dir in core_modules_path.iterdir():
            if not module_dir.is_dir() or module_dir.name.startswith("."):
                continue

            agents_dir = module_dir / "agents"
            if not agents_dir.exists():
                continue

            # Look for *Agent.py files
            agent_files = list(agents_dir.glob("*Agent.py"))
            if agent_files:
                valid_modules.add(module_dir.name)
                print(f"  ✅ {module_dir.name}: Found {len(agent_files)} agent files")
            else:
                print(
                    f"  ❌ {module_dir.name}: Has agents/ folder but no *Agent.py files"
                )

        return valid_modules

    def _filter_data_for_valid_modules(
        self, api_data: Dict[str, Any], valid_modules: Set[str]
    ) -> Dict[str, Any]:
        """Filter API data to only include models that have corresponding agent modules.

        Args:
            api_data: Raw API data from Artificial Analysis
            valid_modules: Set of module names with agents

        Returns:
            Dict[str, Any]: Filtered API data
        """
        if not api_data.get("data"):
            return api_data

        filtered_models = []
        skipped_models = []

        for model in api_data["data"]:
            # Extract provider/module name from model data
            module_name = self._extract_module_name_from_model(model)

            if module_name in valid_modules:
                filtered_models.append(model)
            else:
                skipped_models.append(
                    {
                        "name": model.get("name", "Unknown"),
                        "provider": model.get("provider", "Unknown"),
                        "reason": f"No agent found for module: {module_name}",
                    }
                )

        print("📋 Filtered results:")
        print(f"  ✅ Keeping {len(filtered_models)} models with agents")
        print(f"  ❌ Skipping {len(skipped_models)} models without agents")

        if skipped_models:
            print("  📝 Skipped models:")
            for skipped in skipped_models[:5]:  # Show first 5
                print(
                    f"    • {skipped['name']} ({skipped['provider']}) - {skipped['reason']}"
                )
            if len(skipped_models) > 5:
                print(f"    • ... and {len(skipped_models) - 5} more")

        # Return filtered data with same structure
        filtered_data = api_data.copy()
        filtered_data["data"] = filtered_models

        return filtered_data

    def _extract_module_name_from_model(self, model: Dict[str, Any]) -> str:
        """Extract the module name from a model's provider information.

        Args:
            model: Model data from API

        Returns:
            str: Module name (e.g., 'openai', 'anthropic', 'mistral')
        """
        provider = model.get("provider", "").lower()
        model_name = model.get("name", "").lower()

        # Map providers to module names
        provider_mapping = {
            "openai": "chatgpt",
            "anthropic": "claude",
            "mistral": "mistral",
            "google": "gemini",
            "meta": "llama",
            "perplexity": "perplexity",
            "xai": "grok",
            "together": "together",
            "groq": "groq",
        }

        # Try to match by provider first
        for provider_key, module_name in provider_mapping.items():
            if provider_key in provider:
                return module_name

        # Try to match by model name patterns
        if "gpt" in model_name or "openai" in model_name:
            return "chatgpt"
        elif "claude" in model_name or "anthropic" in model_name:
            return "claude"
        elif "mistral" in model_name:
            return "mistral"
        elif "gemini" in model_name or "palm" in model_name:
            return "gemini"
        elif "llama" in model_name or "meta" in model_name:
            return "llama"
        elif "grok" in model_name or "xai" in model_name:
            return "grok"

        # Default to provider name if no mapping found
        return provider.replace(" ", "").replace("-", "").lower()

    def as_tools(self) -> list[BaseTool]:
        """Returns a list of LangChain tools for this workflow.

        Returns:
            list[BaseTool]: List containing the workflow tool
        """
        return [
            StructuredTool(
                name="artificial_analysis_data_fetch",
                description="Fetch AI model data from Artificial Analysis API, filter for modules with active agents, and save as timestamped JSON files",
                func=lambda **kwargs: self.run(
                    ArtificialAnalysisWorkflowParameters(**kwargs)
                ),
                args_schema=ArtificialAnalysisWorkflowParameters,
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
