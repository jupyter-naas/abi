from typing import Dict, Optional, List
from datetime import datetime
from pathlib import Path
import replicate
import requests
import os

from lib.abi.integration.integration import Integration, IntegrationConnectionError, IntegrationConfiguration
from dataclasses import dataclass
from pydantic import BaseModel, Field

@dataclass
class ReplicateIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for Replicate integration.
    
    Attributes:
        api_key (str): Replicate API key for authentication
    """
    api_key: str

class ReplicateIntegration(Integration):
    __configuration: ReplicateIntegrationConfiguration

    def __init__(self, configuration: ReplicateIntegrationConfiguration):
        """Initialize Replicate client with API key."""
        super().__init__(configuration)
        self.__configuration = configuration
        os.environ["REPLICATE_API_TOKEN"] = self.__configuration.api_key
        
        # Test connection
        try:
            # Simple test prediction to verify connection
            replicate.Client(api_token=self.__configuration.api_key)
        except Exception as e:
            raise IntegrationConnectionError(f"Failed to connect to Replicate: {str(e)}")

    def _ensure_image_directory(self) -> Path:
        """Ensure the images directory exists and return its path."""
        image_dir = Path("src/data/datalake/l1_bronze/assets/replicate_images")
        image_dir.mkdir(parents=True, exist_ok=True)
        return image_dir

    def _download_image(self, url: str, filename: str) -> str:
        """Download image from URL and save to file."""
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        filepath = self._ensure_image_directory() / filename
        with open(filepath, "wb") as f:
            f.write(response.content)
        
        return str(filepath)

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
            name="generate_image",
            description="Generate images using Replicate's Flux Schnell model",
            func=lambda prompt, num_outputs=1, aspect_ratio="1:1": integration.generate_image(prompt, num_outputs, aspect_ratio),
            args_schema=GenerateImageSchema
        )
    ] 