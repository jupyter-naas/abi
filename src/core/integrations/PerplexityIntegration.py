from typing import Optional, Dict, List
import requests
from dataclasses import dataclass
from pydantic import BaseModel, Field
from abi import logger
from lib.abi.integration.integration import Integration, IntegrationConnectionError, IntegrationConfiguration

LOGO_URL = "https://logo.clearbit.com/perplexity.ai"

@dataclass
class PerplexityIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for Perplexity integration.
    
    Attributes:
        api_key (str): Perplexity API key for authentication
        base_url (str): Base URL for Perplexity API
    """
    api_key: str
    base_url: str = "https://api.perplexity.ai"

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

    def _make_request(self, method: str, endpoint: str, data: Dict = None) -> Dict:
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

    def ask_question(
        self,
        question: str,
        system_prompt: str = "Be precise and concise.",
        model: str = "sonar-pro",
        frequency_penalty: float = 1,
        max_tokens: Optional[int] = None,
        presence_penalty: float = 0,
        temperature: float = 0.2,
        top_p: float = 0.9,
        top_k: int = 0,
        stream: bool = False,
        search_domain_filter: List[str] = ["perplexity.ai"],
        search_recency_filter: str = "month",
        response_format: str = {},
        return_images: bool = False,
        return_related_questions: bool = False
    ) -> str:
        """Ask a question to Perplexity AI."""
        payload = {
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
            "model": model,
            "frequency_penalty": frequency_penalty,
            "response_format": response_format,
            "temperature": temperature,
            "top_p": top_p,
            "search_domain_filter": search_domain_filter,
            "return_images": return_images,
            "return_related_questions": return_related_questions,
            "search_recency_filter": search_recency_filter,
            "top_k": top_k,
            "stream": stream,
            "presence_penalty": presence_penalty,
            "max_tokens": max_tokens
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
        system_prompt: str = Field("Be precise and concise.", description="System prompt to guide the response")
        temperature: float = Field(0.2, description="Temperature for response generation (0.0 to 1.0)")
        max_tokens: Optional[int] = Field(None, description="Maximum tokens in response (optional)")

    return [
        StructuredTool(
            name="perplexity_ask_question",
            description="Ask a question to Perplexity AI to get external data/open data from web.",
            func=lambda **kwargs: integration.ask_question(**kwargs),
            args_schema=AskQuestionSchema
        )
    ]