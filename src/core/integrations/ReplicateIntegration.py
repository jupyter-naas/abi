from typing import Dict, Optional, List
from datetime import datetime
from pathlib import Path
import replicate
import requests
from src import config
from lib.abi.integration.integration import Integration, IntegrationConnectionError, IntegrationConfiguration
from src.core.integrations.NaasIntegration import NaasIntegration, NaasIntegrationConfiguration
from dataclasses import dataclass
from pydantic import BaseModel, Field
from src.services import services, ObjectStorageExceptions

LOGO_URL = "https://logo.clearbit.com/replicate.com"

@dataclass
class ReplicateIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for Replicate integration.
    
    Attributes:
        api_key (str): Replicate API key for authentication
        storage_path (str): Path to storage bucket
        naas_integration_configuration (NaasIntegrationConfiguration): Naas integration configuration
    """
    api_key: str
    storage_path: str = "datalake/assets/image"
    naas_integration_configuration: NaasIntegrationConfiguration

class ReplicateIntegration(Integration):
    """Replicate API integration client.
    
    This integration provides methods to interact with Replicate's API endpoints.
    """

    __configuration: ReplicateIntegrationConfiguration

    def __init__(self, configuration: ReplicateIntegrationConfiguration):
        """Initialize Replicate client with API key."""
        super().__init__(configuration)
        self.__configuration = configuration
        self.__naas_integration = NaasIntegration(configuration.naas_integration_configuration)

    def _download_image(self, url: str, filename: str) -> str:
        """Download image from URL and save to file."""
        try:
            response = requests.get(url, timeout=30)

            # Save data to storage
            services.storage_service.put_object(
                prefix=self.__configuration.storage_path,
                key=filename,
                content=response.content
            )

            # Upload asset to Naas
            asset = self.__naas_integration.upload_asset(
                data=response.content,
                workspace_id=config.workspace_id,
                storage_name=config.storage_name,
                prefix=str(self.__configuration.storage_path),
                object_name=str(filename),
                visibility="public"
            )

            # Save asset URL to JSON
            asset_url = asset.get("asset").get("url")
            if asset_url.endswith("/"):
                asset_url = asset_url[:-1]
        except Exception as e:
            raise IntegrationConnectionError(f"Failed to download image: {str(e)}")
        
        return f"File successfully uploaded to storage: {asset_url}"

    def generate_image(self, prompt: str, num_outputs: int = 1, aspect_ratio: str = "1:1") -> List[str]:
        """Generate images using Replicate's Flux Schnell model."""
        try:
            output = replicate.run(
                "black-forest-labs/flux-schnell",
                input={
                    "prompt": prompt,
                    "num_outputs": num_outputs,
                    "aspect_ratio": aspect_ratio,
                    "go_fast": True,
                    "megapixels": "1",
                    "output_format": "webp",
                    "output_quality": 80,
                    "num_inference_steps": 4
                }
            )
            
            urls = output if isinstance(output, list) else [output]
            saved_paths = []
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            for i, url in enumerate(urls):
                filename = f"image_{timestamp}_{i+1}.webp"
                filepath = self._download_image(url, filename)
                saved_paths.append(filepath)
            
            return saved_paths
            
        except Exception as e:
            raise IntegrationConnectionError(f"Error generating image: {str(e)}")

def as_tools(configuration: ReplicateIntegrationConfiguration):
    from langchain_core.tools import StructuredTool
    
    integration = ReplicateIntegration(configuration)

    class GenerateImageSchema(BaseModel):
        prompt: str = Field(..., description="Text description of the image to generate")
        num_outputs: int = Field(1, description="Number of images to generate")
        aspect_ratio: str = Field("1:1", description="Image aspect ratio (e.g., '1:1', '16:9')")
    
    return [
        StructuredTool(
            name="replicate_generate_image",
            description="Generate images using Replicate's Flux Schnell model",
            func=lambda prompt, num_outputs=1, aspect_ratio="1:1": integration.generate_image(prompt, num_outputs, aspect_ratio),
            args_schema=GenerateImageSchema
        )
    ] 