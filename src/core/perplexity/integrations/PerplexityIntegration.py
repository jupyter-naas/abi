from typing import Optional, Dict, List
import requests
from dataclasses import dataclass
from pydantic import BaseModel, Field
from lib.abi.integration.integration import Integration, IntegrationConnectionError, IntegrationConfiguration
from typing import Annotated

@dataclass
class PerplexityIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for Perplexity integration.
    
    Attributes:
        api_key (str): Perplexity API key for authentication
        base_url (str): Base URL for Perplexity API
    """
    api_key: str
    base_url: str = "https://api.perplexity.ai"
    system_prompt: str = "Be precise and concise and answer the question with sources."

class PerplexityIntegration(Integration):
    """Perplexity API integration client.
    
    This integration provides methods to interact with Perplexity's API endpoints.
    """

    __configuration: PerplexityIntegrationConfiguration

    def __init__(self, configuration: PerplexityIntegrationConfiguration):
        """Initialize Perplexity client with API key."""
        super().__init__(configuration)
        self.__configuration = configuration
        
        self.headers = {
            "Authorization": f"Bearer {self.__configuration.api_key}",
            "Content-Type": "application/json"
        }

    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
        """Make HTTP request to Perplexity API."""
        url = f"{self.__configuration.base_url}{endpoint}"
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                json=data,
                timeout=120
            )
            response.raise_for_status()
            return response.json() if response.content else {}
        except requests.exceptions.RequestException as e:
            raise IntegrationConnectionError(f"Perplexity API request failed: {str(e)}")

    def search_web(
        self,
        question: str,
        system_prompt: str | None = None,
        model: str = "sonar-pro",
        reasoning_effort: str = "medium",
        frequency_penalty: float = 1,
        max_tokens: Optional[int] = None,
        presence_penalty: float = 0,
        temperature: float = 0.2,
        top_p: float = 0.9,
        top_k: int = 0,
        stream: bool = False,
        search_domain_filter: List[str] = [],
        search_recency_filter: str = "month",
        response_format: Optional[Dict] = None,
        return_images: bool = False,
        return_related_questions: bool = False,
        search_mode: str = "web",
        search_context_size: str = "medium",
        user_location: str = "FR",
    ) -> str:
        """Search the web for information."""
        if system_prompt is None:
            system_prompt = self.__configuration.system_prompt

        # Handble model name in case of OpenRouter model
        if self.__configuration.base_url.startswith("https://openrouter.ai/api/v1"):
            model = f"perplexity/{model}"

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": question
                }
            ],
            "search_mode": search_mode,
            "reasoning_effort": reasoning_effort,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "search_domain_filter": search_domain_filter,
            "return_images": return_images,
            "return_related_questions": return_related_questions,
            "search_recency_filter": search_recency_filter,
            "top_k": top_k,
            "stream": stream,
            "presence_penalty": presence_penalty,
            "frequency_penalty": frequency_penalty,
            "response_format": response_format,
            "web_search_options": {
                "search_context_size": search_context_size,
                "user_location": {"country": user_location}
            }
        }
        # Remove None values from payload
        payload = {k: v for k, v in payload.items() if v is not None and v != [] and v != {}}
        response = self._make_request("POST", "/chat/completions", payload)
        return response['choices'][0]['message']['content']


def as_tools(configuration: PerplexityIntegrationConfiguration):
    from langchain_core.tools import StructuredTool
    
    integration = PerplexityIntegration(configuration)

    class AskQuestionSchema(BaseModel):
        question: str = Field(..., description="The question to ask Perplexity AI")
        user_location: Annotated[str, Field(..., description="The user location to use for the search")] = "FR"
        search_context_size: Annotated[str, Field(..., description="The search context size to use for the search")] = "medium"

    return [
        StructuredTool(
            name="perplexity_quick_search",
            description="A lightweight, cost-effective search model optimized for quick, grounded answers with real-time web search.",
            func=lambda question, user_location, search_context_size: integration.search_web(question=question, user_location=user_location, search_context_size=search_context_size, model="sonar"),
            args_schema=AskQuestionSchema,
            return_direct=True
        ),
        StructuredTool(
            name="perplexity_search",
            description="Advanced search model designed for complex queries, delivering deeper content understanding with enhanced search result accuracy and 2x more search results than standard Sonar.",
            func=lambda question, user_location, search_context_size: integration.search_web(question=question, user_location=user_location, search_context_size=search_context_size, model="sonar-pro"),
            args_schema=AskQuestionSchema,
            return_direct=True
        ),
        StructuredTool(
            name="perplexity_advanced_search",
            description="Advanced search model designed for complex queries, delivering deeper content understanding with enhanced search result accuracy and 2x more search results than standard Sonar with high context size",
            func=lambda question, user_location, search_context_size: integration.search_web(question=question, user_location=user_location, search_context_size="high", model="sonar-pro-search"),
            args_schema=AskQuestionSchema,
            return_direct=True
        ),
    ]