import io
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import pdfplumber
import requests
from naas_abi_core import logger
from naas_abi_core.integration.integration import Integration, IntegrationConfiguration
from naas_abi_core.models.Model import OPENROUTER_MODEL_MAPPING
from naas_abi_core.services.cache.CacheFactory import CacheFactory
from naas_abi_core.services.cache.CachePort import DataType
from naas_abi_core.utils.StorageUtils import StorageUtils
from naas_abi_marketplace.ai.chatgpt import ABIModule
from pydantic import BaseModel, Field

cache = CacheFactory.CacheFS_find_storage(subpath="openai_responses")


@dataclass
class OpenAIResponsesIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for OpenAIWebSearch workflow.

    Attributes:
        api_key (str): OpenAI API key
        model (str): OpenAI model
        base_url (str): OpenAI base URL
    """

    api_key: str
    model: str = "gpt-4.1-mini"
    base_url: str = "https://api.openai.com/v1/responses"
    datastore_path: str = field(
        default_factory=lambda: ABIModule.get_instance().configuration.datastore_path
    )


class OpenAIResponsesIntegration(Integration):
    """Workflow for performing web searches using OpenAI."""

    __configuration: OpenAIResponsesIntegrationConfiguration
    __storage_utils: StorageUtils

    def __init__(self, configuration: OpenAIResponsesIntegrationConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.__configuration.api_key}",
        }
        if self.__configuration.base_url.startswith("https://openrouter.ai/api/v1"):
            self.model = OPENROUTER_MODEL_MAPPING[self.__configuration.model]
        else:
            self.model = self.__configuration.model
        self.__storage_utils = StorageUtils(
            ABIModule.get_instance().engine.services.object_storage
        )

    @cache(
        lambda self, method, endpoint, params, json: (
            f"{method}_{endpoint}_{str(params)}_{str(json)}"
        ),
        cache_type=DataType.PICKLE,
        ttl=timedelta(days=1),
    )
    def _make_request(
        self,
        method: str,
        endpoint: Optional[str] = None,
        params: dict = {},
        json: dict = {},
    ) -> Any:
        # Make request
        url = (
            f"{self.__configuration.base_url}{endpoint}"
            if endpoint
            else self.__configuration.base_url
        )
        try:
            response = requests.request(
                method=method, url=url, headers=self.headers, json=json, params=params
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error executing OpenAI web search: {str(e)}")
            return {"error": str(e), "text": response.text if response else None}

    def search_web(
        self,
        query: str,
        search_context_size: str = "medium",
        return_text: bool = False,
    ) -> Dict:
        """Execute the web search workflow.

        Args:
            parameters (OpenAIWebSearchParameters): Search parameters

        Returns:
            str: Search results from OpenAI
        """
        payload = {
            "model": self.model,
            "tools": [
                {
                    "type": "web_search_preview",
                    "search_context_size": search_context_size,
                }
            ],
            "input": query,
        }
        response = self._make_request(method="POST", json=payload)
        output_dir = os.path.join(
            self.__configuration.datastore_path, "responses", "web_search", self.model
        )
        self.__storage_utils.save_json(
            response,
            output_dir,
            f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}_{self.model}_{search_context_size}.json",
            copy=False,
        )

        if return_text:
            # Extract text content and annotations from first message with valid content
            for item in response.get("output", []):
                if item.get("type") != "message":
                    continue

                for content_item in item.get("content", []):
                    if content_item.get("type") != "output_text":
                        continue

                    text_content = content_item.get("text", "")
                    annotations = content_item.get("annotations", [])

                    # Only process valid annotations
                    if not isinstance(annotations, list) or not annotations:
                        return text_content

                    # Format annotations section
                    annotation_text = ""
                    # if len(annotations) > 0:
                    #     annotation_text = "\n\n\n\n*Annotations:*\n"
                    #     for annotation in annotations:
                    #         if not isinstance(annotation, dict) or annotation.get("type") != "url_citation":
                    #             continue
                    #         title = annotation.get('title', '')
                    #         url = annotation.get('url', '')
                    #         annotation_text += f"- [{title}]({url})\n"

                    return {"content": text_content + annotation_text}

            # No valid content found
            logger.warning("No valid text content found in response")
            return {"content": "No valid text content found in response"}

        return response

    def analyze_image(
        self,
        image_urls: list[str],
        user_prompt: str = "Describe this image:",
        detail: str = "auto",
        return_text: bool = False,
    ) -> Dict:
        """Analyze an image using OpenAI Responses.

        Args:
            image_url (str): The URL of the image to analyze
            user_prompt (str): The user prompt to use
            detail (str): The detail level to use, high, low or auto
            return_text (bool): Whether to return the text content

        Returns:
            Dict: API response containing the completion
            str: Text content if return_text is True

        Image input requirements:
            Supported file types:
                - PNG (.png)
                - JPEG (.jpeg and .jpg)
                - WEBP (.webp)
                - Non-animated GIF (.gif)

            Size limits:
                - Up to 50 MB total payload size per request
                - Up to 500 individual image inputs per request

            Other requirements:
                - No watermarks or logos
                - No NSFW content
                - Clear enough for a human to understand

        More information: https://platform.openai.com/docs/guides/images-vision?api-mode=responses
        """

        # Prepare payload
        payload = {
            "model": self.model,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": user_prompt},
                        *[
                            {
                                "type": "input_image",
                                "image": {"url": url, "detail": detail},
                            }
                            for url in image_urls
                        ],
                    ],
                },
            ],
        }
        response = self._make_request(method="POST", json=payload)
        output_dir = os.path.join(
            self.__configuration.datastore_path,
            "responses",
            "analyze_image",
            self.model,
        )
        self.__storage_utils.save_json(
            response,
            output_dir,
            f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}_{self.model}_{detail}.json",
            copy=False,
        )

        if return_text:
            try:
                # Find first message with text content
                for item in response.get("output", []):
                    if item.get("type") == "message":
                        content = item.get("content", [])
                        if len(content) > 0 and isinstance(content[0], dict):
                            text = content[0].get("text")
                            if text:
                                return {"content": text}

                # If no valid text content found
                logger.warning("No valid text content found in response")
                return {"content": "No valid text content found in response"}
            except Exception as e:
                logger.error(f"Error parsing response: {str(e)}")
                return {"error": str(e), "content": None}
        return response

    def analyze_pdf(
        self,
        pdf_url: str,
        user_prompt: str = "Describe this PDF document:",
        system_prompt: str = "You are a helpful assistant that can analyze and describe any aspect of PDF documents in detail. You can identify objects, people, scenes, colors, composition, lighting, emotions, actions, text, and other visual elements. Please provide clear and comprehensive descriptions based on what you observe in the PDF document.",
        return_text: bool = False,
    ) -> Dict | str:
        # Download PDF and extract text
        pdf_text = ""
        try:
            pdf_bytes = requests.get(pdf_url).content
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                pdf_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        except Exception as e:
            logger.error(f"Error processing PDF: {str(e)}")
            return str(e)

        # Build messages
        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append(
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": user_prompt},
                    {"type": "input_text", "text": pdf_text},
                ],
            }
        )

        # Build payload
        payload = {"model": self.model, "input": messages}
        response = self._make_request(method="POST", json=payload)
        output_dir = os.path.join(
            self.__configuration.datastore_path, "responses", "analyze_pdf", self.model
        )
        self.__storage_utils.save_json(
            response,
            output_dir,
            f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}_{self.model}.json",
            copy=False,
        )

        # Extract text and annotations from output
        if return_text:
            text = ""
            annotations = []
            try:
                for item in response.get("output", []):
                    if item.get("type") == "message":
                        content = item.get("content", [])
                        for content_item in content:
                            if content_item.get("type") == "output_text":
                                text = content_item.get("text", "")
                            elif content_item.get("type") == "url_citation":
                                annotations.append(content_item)

                if not text:
                    logger.warning("No text content found in output")
                    return "No text content found in output"

                if annotations:
                    seen_urls = set()
                    unique_annotations = []
                    for a in annotations:
                        url = a.get("url", "")
                        if url not in seen_urls:
                            seen_urls.add(url)
                            unique_annotations.append(a)

                    text += "\n\nAnnotations:\n" + "\n".join(
                        f"- [{a.get('title', '')}]({a.get('url', '')})"
                        for a in unique_annotations
                    )
                return {"content": text}
            except Exception as e:
                logger.error(f"Error extracting text from output: {str(e)}")
                return {"error": str(e)}

        return response


def as_tools(configuration: OpenAIResponsesIntegrationConfiguration):
    from typing import Annotated

    from langchain_core.tools import StructuredTool

    integration = OpenAIResponsesIntegration(configuration)

    class SearchWebSchema(BaseModel):
        query: Annotated[str, Field(..., description="The query to search the web")]
        search_context_size: Annotated[
            str,
            Field(description="The search context size", pattern="^(low|medium|high)$"),
        ] = "medium"
        return_text: Annotated[
            bool, Field(default=True, description="Whether to return the text content")
        ] = True

    class AnalyzeImageSchema(BaseModel):
        image_urls: Annotated[
            list[str], Field(..., description="The URLs of the images to analyze")
        ]
        user_prompt: Annotated[str, Field(description="The user prompt to use")] = (
            "Describe this image:"
        )

    class AnalyzePdfSchema(BaseModel):
        pdf_url: Annotated[
            str, Field(..., description="The URL of the PDF document to analyze")
        ]
        user_prompt: Annotated[str, Field(description="The user prompt to use")] = (
            "Describe this PDF document:"
        )

    return [
        StructuredTool(
            name="chatgpt_search_web",
            description="Search the web",
            func=lambda **kwargs: integration.search_web(**kwargs),
            args_schema=SearchWebSchema,
            return_direct=True,
        ),
        StructuredTool(
            name="chatgpt_analyze_image",
            description="Analyze an image from URL",
            func=lambda **kwargs: integration.analyze_image(**kwargs),
            args_schema=AnalyzeImageSchema,
            return_direct=True,
        ),
        StructuredTool(
            name="chatgpt_analyze_pdf",
            description="Analyze a PDF document from URL",
            func=lambda **kwargs: integration.analyze_pdf(**kwargs),
            args_schema=AnalyzePdfSchema,
            return_direct=True,
        ),
    ]
