from typing import Optional, Dict, List
import requests
from dataclasses import dataclass
import json
import os
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from lib.abi.integration.integration import Integration, IntegrationConnectionError, IntegrationConfiguration

# Load environment variables
load_dotenv()

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
    __configuration: PerplexityIntegrationConfiguration

    def __init__(self, configuration: PerplexityIntegrationConfiguration):
        """Initialize Perplexity client with API key."""
        super().__init__(configuration)
        self.__configuration = configuration
        
        self.headers = {
            "Authorization": f"Bearer {self.__configuration.api_key}",
            "Content-Type": "application/json"
        }
        
        # # Test connection
        # try:
        #     self._make_request("POST", "/chat/completions", {
        #         "model": "llama-3.1-sonar-small-128k-online",
        #         "messages": [{"role": "user", "content": "test"}]
        #     })
        # except Exception as e:
        #     raise IntegrationConnectionError(f"Failed to connect to Perplexity: {str(e)}")

    def _make_request(self, method: str, endpoint: str, data: Dict = None) -> Dict:
        """Make HTTP request to Perplexity API."""
        url = f"{self.__configuration.base_url}{endpoint}"
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                json=data,
                timeout=30
            )
            response.raise_for_status()
            return response.json() if response.content else {}
        except requests.exceptions.RequestException as e:
            raise IntegrationConnectionError(f"Perplexity API request failed: {str(e)}")

    def ask_question(
        self,
        question: str,
        system_prompt: str = "Be precise and concise.",
        temperature: float = 0.2,
        max_tokens: Optional[int] = None
    ) -> str:
        """Ask a question to Perplexity AI."""
        payload = {
            "model": "llama-3.1-sonar-small-128k-online",
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
            "temperature": temperature,
            "top_p": 0.9,
            "search_domain_filter": ["perplexity.ai"],
            "return_images": False,
            "return_related_questions": False,
            "search_recency_filter": "month",
            "top_k": 0,
            "stream": False,
            "presence_penalty": 0,
            "frequency_penalty": 1
        }
        
        if max_tokens:
            payload["max_tokens"] = max_tokens

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
            name="ask_perplexity",
            description="OpenData: Ask a question to Perplexity AI to get external data from internet",
            func=lambda question, system_prompt="Be precise and concise.", temperature=0.2, max_tokens=None: 
                integration.ask_question(question, system_prompt, temperature, max_tokens),
            args_schema=AskQuestionSchema
        )
    ]

# Direct testing
if __name__ == "__main__":
    print("\nTesting Perplexity API:")
    try:
        api_key = os.getenv("PERPLEXITY_API_KEY")
        if not api_key:
            raise ValueError("PERPLEXITY_API_KEY environment variable not set")
            
        config = PerplexityIntegrationConfiguration(api_key=api_key)
        integration = PerplexityIntegration(config)
        result = integration.ask_question("Who won the US presidential election in 2024?")
        print(f"Success: {result}")
    except Exception as e:
        print(f"Test failed: {str(e)}") 