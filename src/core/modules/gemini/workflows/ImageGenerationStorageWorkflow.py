from abi.workflow import Workflow, WorkflowConfiguration
from abi.workflow.workflow import WorkflowParameters
from abi.services.object_storage.ObjectStorageFactory import ObjectStorageFactory
from dataclasses import dataclass
from pydantic import Field
from datetime import datetime
import base64
from typing import Annotated, Optional
from fastapi import APIRouter
from langchain_core.tools import StructuredTool, BaseTool
from enum import Enum
from abi import logger
from src import secret

@dataclass
class ImageGenerationStorageWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for ImageGenerationStorage workflow."""
    storage_base_path: str = "storage"
    
class ImageGenerationStorageWorkflowParameters(WorkflowParameters):
    """Parameters for ImageGenerationStorage workflow."""
    prompt: Annotated[str, Field(
        ...,
        description="Text prompt to generate the image from",
        example="A beautiful sunset over mountains with a lake reflection"
    )]
    file_name: Optional[Annotated[str, Field(
        default="generated_image.png",
        description="Name for the generated image file",
        example="sunset_mountains.png"
    )]] = "generated_image.png"
    folder_name: Optional[Annotated[str, Field(
        default="images",
        description="Subfolder name within the timestamped directory",
        example="images"
    )]] = "images"

class ImageGenerationStorageWorkflow(Workflow):
    """Workflow for generating images and storing them in organized folder structure."""

    __configuration: ImageGenerationStorageWorkflowConfiguration

    def __init__(self, configuration: ImageGenerationStorageWorkflowConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def generate_and_store_image(self, parameters: ImageGenerationStorageWorkflowParameters) -> dict:
        """
        Generate a REAL image using Google Imagen 4.0 and store it.
        
        Returns:
            dict: Information about the generated REAL image and storage
        """
        try:
            logger.info(f"🎨 Generating image with Imagen 4.0: {parameters.prompt}")
            
            # Get API key
            api_key = secret.get('GOOGLE_API_KEY', '')
            if not api_key:
                raise Exception("Google API key not found - please configure GOOGLE_API_KEY")
            
            # Import requests here to avoid dependency issues
            import requests
            
            # Imagen 4.0 API endpoint (restore original working config)
            url = f'https://generativelanguage.googleapis.com/v1beta/models/imagen-4.0-generate-preview-06-06:predict?key={api_key}'
            
            headers = {
                'Content-Type': 'application/json'
            }
            
            # Imagen API payload
            payload = {
                'instances': [
                    {
                        'prompt': parameters.prompt
                    }
                ],
                'parameters': {
                    'sampleCount': 1,
                    'aspectRatio': '1:1',  # Square by default
                    'safetyFilterLevel': 'block_fewest',
                    'personGeneration': 'allow_adult'
                }
            }
            
            # Call Imagen 4.0 API
            logger.info("🔥 Calling Google Imagen 4.0...")
            response = requests.post(url, json=payload, headers=headers)
            
            if response.status_code != 200:
                # Handle specific error cases for better user experience
                if response.status_code == 400:
                    error_text = response.text.lower()
                    if 'safety' in error_text or 'policy' in error_text or 'guidelines' in error_text:
                        raise Exception("Sorry, I can't generate this type of image due to content safety guidelines. Please try a different prompt.")
                    elif 'biden' in error_text or 'trump' in error_text or 'political' in error_text:
                        raise Exception("Sorry, I can't generate images of political figures. Please try a different subject.")
                raise Exception(f"API call failed with status {response.status_code}: {response.text}")
            
            result = response.json()
            
            if 'predictions' not in result or not result['predictions']:
                # Check if it's a safety filter issue
                if result.get('error', {}).get('code') == 400 or 'safety' in str(result).lower():
                    raise Exception("Sorry, I can't generate this type of image due to content safety guidelines. Please try a different prompt.")
                elif not result['predictions']:
                    raise Exception("Sorry, I can't generate this image. It may violate content guidelines or the request was blocked for safety reasons. Please try a different prompt.")
                else:
                    raise Exception(f"No predictions returned from API: {result}")
            
            prediction = result['predictions'][0]
            
            if 'bytesBase64Encoded' not in prediction:
                raise Exception(f"No image data in prediction: {list(prediction.keys())}")
            
            # Decode the base64 image
            image_base64 = prediction['bytesBase64Encoded']
            generated_image_data = base64.b64decode(image_base64)
            
            logger.info(f"🖼️ Generated image data received! Size: {len(generated_image_data)} bytes")
            
            # Create timestamp folder structure
            timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
            module_folder = "google_gemini"
            folder_path = f"datastore/{module_folder}/{timestamp}/{parameters.folder_name}"
            
            # Initialize storage service
            storage_service = ObjectStorageFactory.ObjectStorageServiceFS__find_storage(
                self.__configuration.storage_base_path
            )
            
            # Generate smart filename from prompt if using default
            if parameters.file_name == "generated_image.png":
                # Extract key words from prompt for filename
                import re
                prompt_words = re.findall(r'\b[a-zA-Z]{3,}\b', parameters.prompt.lower())
                key_words = prompt_words[:3]  # Take first 3 meaningful words
                smart_name = "_".join(key_words) if key_words else "generated_image"
                file_name = f"{smart_name}.png"
            else:
                file_name = parameters.file_name or "generated_image.png"
                if not file_name.endswith(('.png', '.jpg', '.jpeg', '.webp')):
                    file_name = f"{file_name}.png"
            
            # Use the original image bytes for storage
            image_bytes = generated_image_data
            
            # Store the generated image
            storage_service.put_object(folder_path, file_name, image_bytes)
            logger.info(f"✅ Image saved: {file_name}")
            
            # Create simple prompt file
            prompt_file = file_name.replace('.png', '_prompt.txt').replace('.jpg', '_prompt.txt').replace('.jpeg', '_prompt.txt').replace('.webp', '_prompt.txt')
            
            # Store only the prompt
            storage_service.put_object(folder_path, prompt_file, parameters.prompt.encode('utf-8'))
            
            full_path = f"{self.__configuration.storage_base_path}/{folder_path}/{file_name}"
            prompt_path = f"{self.__configuration.storage_base_path}/{folder_path}/{prompt_file}"
            
            logger.info(f"✅ Image successfully generated and stored at: {full_path}")
            
            return {
                "success": True,
                "message": f"🎨 Image generated! Files: {file_name} & {prompt_file}",
                "image_path": full_path,
                "prompt_path": prompt_path,
                "folder": f"{folder_path}",
                "files": [file_name, prompt_file],
                "timestamp": timestamp,
                "model": "imagen-4.0-generate-preview-06-06"
            }
                
        except Exception as e:
            logger.error(f"❌ Error generating image: {str(e)}")
            return {
                "success": False,
                "message": f"❌ Error generating image: {str(e)}",
                "error": str(e)
            }

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="generate_and_store_image",
                description="Generate an image from a text prompt using Google Imagen 4.0 Preview and automatically store it in organized timestamped folders",
                func=lambda **kwargs: self.generate_and_store_image(
                    ImageGenerationStorageWorkflowParameters(**kwargs)
                ),
                args_schema=ImageGenerationStorageWorkflowParameters,
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