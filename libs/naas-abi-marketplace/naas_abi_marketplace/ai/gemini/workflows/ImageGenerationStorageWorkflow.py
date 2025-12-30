import base64
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Annotated, Optional
from fastapi import APIRouter
from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core import logger
from naas_abi_core.workflow import Workflow, WorkflowConfiguration
from naas_abi_core.workflow.workflow import WorkflowParameters
from pydantic import Field 
from naas_abi_marketplace.ai.gemini import ABIModule
from naas_abi_core.utils.StorageUtils import StorageUtils
import requests
import os


@dataclass
class ImageGenerationStorageWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for ImageGenerationStorage workflow."""
    gemini_api_key: str = field(default_factory=lambda: ABIModule.get_instance().configuration.gemini_api_key)
    datastore_path: str = field(default_factory=lambda: ABIModule.get_instance().configuration.datastore_path)
    model: str = "imagen-4.0-generate-preview-06-06"
    base_url: str = "https://generativelanguage.googleapis.com/v1beta/models"


class ImageGenerationStorageWorkflowParameters(WorkflowParameters):
    """Parameters for ImageGenerationStorage workflow."""
    prompt: Annotated[
        str,
        Field(
            ...,
            description="Text prompt to generate the image from",
            example="A beautiful sunset over mountains with a lake reflection",
        ),
    ]
    file_name: Optional[
        Annotated[
            str,
            Field(
                description="Name for the generated image file",
                example="sunset_mountains.png",
            ),
        ]
    ] = "generated_image.png"
    folder_name: Optional[
        Annotated[
            str,
            Field(
                description="Subfolder name within the timestamped directory",
                example="images",
            ),
        ]
    ] = "images"


class ImageGenerationStorageWorkflow(Workflow):
    """Workflow for generating images and storing them in organized folder structure."""

    __configuration: ImageGenerationStorageWorkflowConfiguration
    __storage_utils: StorageUtils

    def __init__(self, configuration: ImageGenerationStorageWorkflowConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__storage_utils = StorageUtils(ABIModule.get_instance().engine.services.object_storage)
        self.headers = {
            "Content-Type": "application/json"
        }

    def generate_image(
        self, parameters: ImageGenerationStorageWorkflowParameters
    ) -> dict:
        """
        Generate a REAL image using Google Imagen 4.0 and store it.

        Returns:
            dict: Information about the generated REAL image and storage
        """
        try:
            logger.info(f"🎨 Generating image with Imagen 4.0: {parameters.prompt}")

            # Imagen 4.0 API endpoint (restore original working config)
            url = f"{self.__configuration.base_url}/{self.__configuration.model}:predict?key={self.__configuration.gemini_api_key}"

            # Imagen API payload
            payload = {
                "instances": [{"prompt": parameters.prompt}],
                "parameters": {
                    "sampleCount": 1,
                    "aspectRatio": "1:1",  # Square by default
                    "safetyFilterLevel": "block_fewest",
                    "personGeneration": "allow_adult",
                },
            }

            # Call Imagen 4.0 API
            logger.info("🔥 Calling Google Imagen 4.0...")
            response = requests.post(url, json=payload, headers=self.headers)

            if response.status_code != 200:
                # Handle specific error cases for better user experience
                if response.status_code == 400:
                    error_text = response.text.lower()
                    if (
                        "safety" in error_text
                        or "policy" in error_text
                        or "guidelines" in error_text
                    ):
                        raise Exception(
                            "Sorry, I can't generate this type of image due to content safety guidelines. Please try a different prompt."
                        )
                    elif (
                        "biden" in error_text
                        or "trump" in error_text
                        or "political" in error_text
                    ):
                        raise Exception(
                            "Sorry, I can't generate images of political figures. Please try a different subject."
                        )
                raise Exception(
                    f"API call failed with status {response.status_code}: {response.text}"
                )

            result = response.json()

            if "predictions" not in result or not result["predictions"]:
                # Check if it's a safety filter issue
                if (
                    result.get("error", {}).get("code") == 400
                    or "safety" in str(result).lower()
                ):
                    raise Exception(
                        "Sorry, I can't generate this type of image due to content safety guidelines. Please try a different prompt."
                    )
                elif not result["predictions"]:
                    raise Exception(
                        "Sorry, I can't generate this image. It may violate content guidelines or the request was blocked for safety reasons. Please try a different prompt."
                    )
                else:
                    raise Exception(f"No predictions returned from API: {result}")

            prediction = result["predictions"][0]

            if "bytesBase64Encoded" not in prediction:
                raise Exception(
                    f"No image data in prediction: {list(prediction.keys())}"
                )

            # Decode the base64 image
            image_base64 = prediction["bytesBase64Encoded"]
            generated_image_data = base64.b64decode(image_base64)

            logger.info(
                f"🖼️ Generated image data received! Size: {len(generated_image_data)} bytes"
            )

            # Create timestamp folder structure
            timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
            folder_path = os.path.join(
                self.__configuration.datastore_path,
                "generate_images",
            )

            # Generate smart filename from prompt if using default
            if parameters.file_name == "generated_image.png":
                # Extract key words from prompt for filename
                import re
                prompt_words = re.findall(
                    r"\b[a-zA-Z]{3,}\b", parameters.prompt.lower()
                )
                key_words = prompt_words[:3]  # Take first 3 meaningful words
                smart_name = "_".join(key_words) if key_words else "generated_image"
                file_name = f"{smart_name}.png"
            else:
                file_name = parameters.file_name or "generated_image.png"
                if not file_name.endswith((".png", ".jpg", ".jpeg", ".webp")):
                    file_name = f"{file_name}.png"
            file_name = f"{timestamp}_{file_name}"

            # Use the original image bytes for storage
            image_bytes = generated_image_data

            # Store the generated image
            self.__storage_utils.save_image(image_bytes, folder_path, file_name)
            logger.info(f"✅ Image saved: {file_name}")

            # Create simple prompt file
            prompt_file = (
                file_name.replace(".png", "_prompt.txt")
                .replace(".jpg", "_prompt.txt")
                .replace(".jpeg", "_prompt.txt")
                .replace(".webp", "_prompt.txt")
            )

            # Store only the prompt
            self.__storage_utils.save_text(parameters.prompt, folder_path, prompt_file)

            logger.info(f"✅ Image successfully generated and stored at: {folder_path}/{file_name}")

            return {
                "success": True,
                "message": f"🎨 Image generated! Files: {file_name} & {prompt_file}",
                "image_path": f"{folder_path}/{file_name}",
                "prompt_path": f"{folder_path}/{prompt_file}",
                "folder": f"{folder_path}",
                "files": [file_name, prompt_file],
                "timestamp": timestamp,
                "model": "imagen-4.0-generate-preview-06-06",
            }

        except Exception as e:
            logger.error(f"❌ Error generating image: {str(e)}")
            return {
                "success": False,
                "message": f"❌ Error generating image: {str(e)}",
                "error": str(e),
            }

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="gemini_generate_image",
                description="Generate an image from a text prompt using Google Imagen 4.0 Preview",
                func=lambda **kwargs: self.generate_image(ImageGenerationStorageWorkflowParameters(**kwargs)),
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
