from abi.workflow import Workflow, WorkflowConfiguration
from src.core.modules.common.integrations.LinkedInIntegration import (
    LinkedInIntegration,
    LinkedInIntegrationConfiguration,
)
from src.core.modules.common.integrations.GoogleSearchIntegration import (
    GoogleSearchIntegration,
    GoogleSearchIntegrationConfiguration,
)
from src.core.modules.common.integrations.NaasIntegration import (
    NaasIntegration,
    NaasIntegrationConfiguration,
)
from dataclasses import dataclass
from pydantic import Field
from datetime import datetime
from abi import logger
from typing import Optional, Tuple
from abi.workflow.workflow import WorkflowParameters
from langchain_core.tools import StructuredTool
from fastapi import APIRouter
from pathlib import Path
import json
import requests
from src import config
from src.services import services
from abi.services.object_storage.ObjectStoragePort import (
    Exceptions as ObjectStorageExceptions,
)
from abi.utils.String import create_id_from_string


@dataclass
class LinkedInOrganizationWorkflowsConfiguration(WorkflowConfiguration):
    """Configuration for LinkedIn Organization Workflow.

    Attributes:
        linkedin_integration_config (LinkedInIntegrationConfiguration): LinkedIn integration configuration
    """

    linkedin_integration_config: LinkedInIntegrationConfiguration
    naas_integration_config: NaasIntegrationConfiguration
    google_search_integration_config: GoogleSearchIntegrationConfiguration
    data_store_path: str = "datalake/opendata/organizations"


class LinkedInOrganizationParameters(WorkflowParameters):
    """Parameters for Organization Analysis Workflow execution.

    Attributes:
        organization_name (str): Name of the organization
        linkedin_url (str): LinkedIn profile or organization post URL
        use_cache (bool): Use cache to store the data
    """

    organization_name: Optional[str] = Field(
        None,
        description="Name of the organization. If not provided, use the LinkedIn URL.",
    )
    use_cache: bool = Field(True, description="Use cache to store the data")


class LinkedInOrganizationWorkflows(Workflow):
    """Workflow for fetching LinkedIn posts from a profile or organization."""

    __configuration: LinkedInOrganizationWorkflowsConfiguration

    def __init__(self, configuration: LinkedInOrganizationWorkflowsConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__linkedin_integration = LinkedInIntegration(
            self.__configuration.linkedin_integration_config
        )
        self.__naas_integration = NaasIntegration(
            self.__configuration.naas_integration_config
        )
        self.__google_search_integration = GoogleSearchIntegration(
            self.__configuration.google_search_integration_config
        )

    def init_storage(self, organization_name: str) -> Tuple[str, Path]:
        organization_id = create_id_from_string(organization_name)
        return Path(
            self.__configuration.data_store_path
        ) / f"{organization_id}", f"linkedin_{organization_id}_organization_data.json"

    def get_organization_info(self, parameters: LinkedInOrganizationParameters) -> dict:
        """Get organization data from the OpenData store."""
        # Initialize storage
        output_dir, file_name = self.init_storage(parameters.organization_name)

        # Get organization data from storage
        try:
            file_content = services.storage_service.get_object(
                output_dir, file_name
            ).decode("utf-8")
            data = json.loads(file_content)
            if "linkedin_url" in data:
                linkedin_url = data["linkedin_url"]
        except Exception:
            file_content = None
            data = None
            linkedin_url = None

        # Get organization data from LinkedIn
        if data is None or parameters.use_cache is False:
            if linkedin_url is None:
                logger.info(
                    f"Extracting LinkedIn URL from GoogleSearchIntegration for '{parameters.organization_name}'"
                )
                linkedin_url = (
                    self.__google_search_integration.search_linkedin_organization_url(
                        parameters.organization_name
                    )
                )
                logger.debug(f"LinkedIn URL: {linkedin_url}")

            if linkedin_url is not None:
                logger.info(
                    f"Extracting organization data from LinkedInIntegration for '{parameters.organization_name}'"
                )
                df = self.__linkedin_integration.get_organization_details(linkedin_url)
                if len(df) > 0:
                    data = {
                        "organization_name": parameters.organization_name,
                        "organization_id": create_id_from_string(
                            parameters.organization_name
                        ),
                        "linkedin_url": linkedin_url,
                        "data": df.to_dict("records"),
                        "output_dir": str(output_dir),
                        "date_extracted": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    }
                    logger.info(f"Data successfully extracted: {data}")
                else:
                    logger.error(f"No data found for '{parameters.organization_name}'")

                # Save data to storage
                services.storage_service.put_object(
                    prefix=output_dir,
                    key=file_name,
                    content=json.dumps(data, indent=4, ensure_ascii=False).encode(
                        "utf-8"
                    ),
                )
        return data

    def get_organization_logo_url(
        self, parameters: LinkedInOrganizationParameters
    ) -> str:
        """Get organization logo URL from the OpenData store."""
        # Initialize storage
        data = self.get_organization_info(parameters)
        if data is None:
            return None
        logo_url = data.get("data", [{}])[0].get("LOGO_URL")
        output_dir = data.get("output_dir")
        organization_id = data.get("organization_id")
        asset_file_name = f"naas_assets_{organization_id}.json"
        logo_file_name = f"linkedin_{organization_id}_logo.png"

        # Get logo asset
        try:
            file_content = services.storage_service.get_object(
                output_dir, asset_file_name
            ).decode("utf-8")
            data = json.loads(file_content)
            asset_url = data.get("organization_logo_url")
        except ObjectStorageExceptions.ObjectNotFound:
            file_content = None
            data = {}
            asset_url = None

        # Download logo
        if asset_url is None or parameters.use_cache is False:
            try:
                response = requests.get(logo_url)

                # Save data to storage
                services.storage_service.put_object(
                    prefix=output_dir, key=logo_file_name, content=response.content
                )

                # Upload asset to Naas
                asset = self.__naas_integration.upload_asset(
                    data=response.content,
                    workspace_id=config.workspace_id,
                    storage_name=config.storage_name,
                    prefix=str(output_dir),
                    object_name=str(logo_file_name),
                    visibility="public",
                )

                # Save asset URL to JSON
                asset_url = asset.get("asset").get("url")
                if asset_url.endswith("/"):
                    asset_url = asset_url[:-1]
                data["organization_logo_url"] = asset_url
                services.storage_service.put_object(
                    prefix=output_dir,
                    key=asset_file_name,
                    content=json.dumps(data, indent=4, ensure_ascii=False).encode(
                        "utf-8"
                    ),
                )
            except Exception as e:
                logger.error(f"Error downloading logo from {logo_url}: {e}")
        logger.debug(f"Logo URL: {asset_url}")
        return asset_url

    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this workflow."""
        return [
            StructuredTool(
                name="linkedin_get_organization_info",
                description="Extract organization information from LinkedIn using the organization name.",
                func=lambda **kwargs: self.get_organization_info(
                    LinkedInOrganizationParameters(**kwargs)
                ),
                args_schema=LinkedInOrganizationParameters,
            ),
            StructuredTool(
                name="linkedin_get_organization_logo_url",
                description="Get LinkedIn organization logo URL.",
                func=lambda **kwargs: self.get_organization_logo_url(
                    LinkedInOrganizationParameters(**kwargs)
                ),
                args_schema=LinkedInOrganizationParameters,
            ),
        ]

    def as_api(self, router: APIRouter) -> None:
        pass
