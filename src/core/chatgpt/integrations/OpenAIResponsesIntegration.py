from lib.abi.integration.integration import Integration, IntegrationConfiguration
from dataclasses import dataclass
from pydantic import Field
from abi import logger
from typing import Any, Optional, Dict
from pydantic import BaseModel
import requests
import io
import pdfplumber

@dataclass
class OpenAIResponsesIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for OpenAIWebSearch workflow.
    
    Attributes:
        api_key (str): OpenAI API key
        model (str): OpenAI model
        base_url (str): OpenAI base URL
    """
    api_key: str
    model : str = "gpt-4.1-mini"
    base_url: str = "https://api.openai.com/v1/responses"


class OpenAIResponsesIntegration(Integration):
    """Workflow for performing web searches using OpenAI."""
    
    __configuration: OpenAIResponsesIntegrationConfiguration
    
    def __init__(self, configuration: OpenAIResponsesIntegrationConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.__configuration.api_key}"
        }

    def _make_request(self, method: str, endpoint: Optional[str] = None, params: dict = {}, json: dict = {}) -> Any:
        # Make request
        url = f"{self.__configuration.base_url}{endpoint}" if endpoint else self.__configuration.base_url
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                json=json,
                params=params
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error executing OpenAI web search: {str(e)}")
            return str(e)

    def search_web(
        self, 
        query: str, 
        search_context_size: str = "medium", 
        return_text: bool = False
    ) -> Dict | str:
        """Execute the web search workflow.
        
        Args:
            parameters (OpenAIWebSearchParameters): Search parameters
            
        Returns:
            str: Search results from OpenAI
        """        
        payload = {
            "model": self.__configuration.model,
            "tools": [
                {
                    "type": "web_search_preview",
                    "search_context_size": search_context_size
                }
            ],    
            "input": query
        }
        response = self._make_request(method="POST", json=payload)
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
                        
                    return text_content + annotation_text
                    
            # No valid content found
            logger.warning("No valid text content found in response")
            return ""
            
        return response
    
    def analyze_image(
        self, 
        image_urls: list[str],
        user_prompt: str = "Describe this image:",
        detail: str = "auto",
        return_text: bool = False
    ) -> Dict | str:
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
            "model": self.__configuration.model,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text", 
                            "text": user_prompt
                        },
                        *[{
                            "type": "input_image",
                            "image_url": url,
                            "detail": detail
                        } for url in image_urls],
                    ],
                },
            ],
        }
        response = self._make_request(method="POST", json=payload)

        if return_text:
            try:
                # Find first message with text content
                for item in response.get("output", []):
                    if item.get("type") == "message":
                        content = item.get("content", [])
                        if content and isinstance(content[0], dict):
                            text = content[0].get("text")
                            if text:
                                return text
                
                # If no valid text content found
                logger.warning("No valid text content found in response")
                return "No valid text content found in response"
            except Exception as e:
                logger.error(f"Error parsing response: {str(e)}")
                return str(e)
        return response
    
    def analyze_pdf(
        self, 
        pdf_url: str,
        user_prompt: str = "Describe this PDF document:",
        system_prompt: str = "You are a helpful assistant that can analyze and describe any aspect of PDF documents in detail. You can identify objects, people, scenes, colors, composition, lighting, emotions, actions, text, and other visual elements. Please provide clear and comprehensive descriptions based on what you observe in the PDF document.",
        return_text: bool = False
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
            messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        messages.append({
            "role": "user",
            "content": [
                {"type": "input_text", "text": user_prompt},
                {"type": "input_text", "text": pdf_text}
            ]
        })
        
        # Build payload
        payload = {
            "model": self.__configuration.model,
            "input": messages
        }

        response = self._make_request(method="POST", json=payload)
        
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
                        url = a.get('url', '')
                        if url not in seen_urls:
                            seen_urls.add(url)
                            unique_annotations.append(a)
                    
                    text += "\n\nAnnotations:\n" + "\n".join(
                        f"- [{a.get('title', '')}]({a.get('url', '')})"
                        for a in unique_annotations
                    )
                return text
            except Exception as e:
                logger.error(f"Error extracting text from output: {str(e)}")
                return str(e)
                
        return response
    
def as_tools(configuration: OpenAIResponsesIntegrationConfiguration):
    from langchain_core.tools import StructuredTool
    integration = OpenAIResponsesIntegration(configuration)

    class SearchWebSchema(BaseModel):
        query: str = Field(..., description="The query to search the web")

    class AnalyzeImageSchema(BaseModel):
        image_urls: list[str] = Field(..., description="The URLs of the images to analyze")
        user_prompt: str = Field(..., description="The user prompt to use")

    class AnalyzePdfSchema(BaseModel):
        pdf_url: str = Field(..., description="The URL of the PDF document to analyze")
        user_prompt: str = Field(..., description="The user prompt to use")

    return [
        StructuredTool(
            name="chatgpt_search_web",
            description="Search the web",
            func=lambda query: integration.search_web(query=query, search_context_size="medium", return_text=True),
            args_schema=SearchWebSchema,
            return_direct=True
        ),
        StructuredTool(
            name="chatgpt_analyze_image",
            description="Analyze an image from URL",
            func=lambda image_urls, user_prompt: integration.analyze_image(image_urls=image_urls, user_prompt=user_prompt, return_text=True),
            args_schema=AnalyzeImageSchema,
            return_direct=True
        ),
        StructuredTool(
            name="chatgpt_analyze_pdf",
            description="Analyze a PDF document from URL",
            func=lambda pdf_url, user_prompt: integration.analyze_pdf(pdf_url=pdf_url, user_prompt=user_prompt, return_text=True),
            args_schema=AnalyzePdfSchema,
            return_direct=True
        )
    ]
