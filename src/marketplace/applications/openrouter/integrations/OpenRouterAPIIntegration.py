from typing import Optional, Dict
import requests
from dataclasses import dataclass
from abi.integration.integration import Integration, IntegrationConfiguration, IntegrationConnectionError


@dataclass
class OpenRouterAPIIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for OpenRouter API Integration.
    
    Attributes:
        api_key (str): OpenRouter API key for authentication
        base_url (str): Base URL for OpenRouter API
        datastore_path (str): Path to the datastore
    """
    api_key: str
    base_url: str = "https://openrouter.ai/api/v1"
    datastore_path: str = "datastore/__openrouterapis__"


class OpenRouterAPIIntegration(Integration):
    """OpenRouter API Integration class for interacting with OpenRouter API.
    
    This class provides methods to interact with OpenRouter's API endpoints.
    It handles authentication and request management.
    
    Attributes:
        __configuration (OpenRouterAPIIntegrationConfiguration): Configuration instance
            containing necessary credentials and settings.
    
    Example:
        >>> config = OpenRouterAPIIntegrationConfiguration(
        ...     api_key="your_api_key"
        ... )
        >>> integration = OpenRouterAPIIntegration(config)
    """

    __configuration: OpenRouterAPIIntegrationConfiguration

    def __init__(self, configuration: OpenRouterAPIIntegrationConfiguration):
        """Initialize OpenRouter API client with API key."""
        super().__init__(configuration)
        self.__configuration = configuration
        
        self.headers = {
            "Authorization": f"Bearer {self.__configuration.api_key}",
            "Content-Type": "application/json"
        }

    def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict] = None, 
        params: Optional[Dict] = None
    ) -> Dict:
        """Make HTTP request to OpenRouter API endpoint.
        
        Args:
            method (str): HTTP method to use (GET, POST, PATCH, DELETE).
            endpoint (str): The API endpoint to request.
            data (dict, optional): JSON body for the request.
            params (dict, optional): Query parameters for the request.
        
        Returns:
            dict: Response data from the API.
            
        Raises:
            IntegrationConnectionError: If the request fails.
        """
        url = f"{self.__configuration.base_url}{endpoint}"
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                json=data,
                params=params
            )
            response.raise_for_status()
            return response.json() if response.content else {}
        except requests.exceptions.RequestException as e:
            raise IntegrationConnectionError(f"OpenRouter API request failed: {str(e)}")
    
    # Beta Responses
    def create_response(self, data: Dict) -> Dict:
        """Create a response (beta endpoint).
        
        Args:
            data (dict): Request body for creating the response.
            
        Returns:
            dict: Response data from the API.
        """
        return self._make_request("POST", "/beta/responses", data=data)
    
    # Analytics
    def get_user_activity(self, params: Optional[Dict] = None) -> Dict:
        """Get user activity grouped by endpoint.
        
        Args:
            params (dict, optional): Query parameters (e.g., date filters).
            
        Returns:
            dict: User activity data grouped by endpoint.
        """
        return self._make_request("GET", "/analytics", params=params)
    
    # Credits
    def get_remaining_credits(self) -> Dict:
        """Get remaining credits.
        
        Returns:
            dict: Information about remaining credits.
        """
        return self._make_request("GET", "/credits")
    
    def create_coinbase_charge(self, data: Dict) -> Dict:
        """Create a Coinbase charge for crypto payment.
        
        Args:
            data (dict): Payment information for Coinbase charge.
            
        Returns:
            dict: Coinbase charge creation response.
        """
        return self._make_request("POST", "/credits", data=data)
    
    # Generations
    def get_generation_metadata(self, generation_id: str) -> Dict:
        """Get request & usage metadata for a generation.
        
        Args:
            generation_id (str): The generation ID to get metadata for.
            
        Returns:
            dict: Generation metadata including request and usage information.
        """
        return self._make_request("GET", f"/generations/{generation_id}")
    
    # Models
    def get_total_models_count(self) -> Dict:
        """Get total count of available models.
        
        Returns:
            dict: Total count of available models.
        """
        return self._make_request("GET", "/models/count")
    
    def list_all_models(self, params: Optional[Dict] = None) -> Dict:
        """List all models and their properties.
        
        Args:
            params (dict, optional): Query parameters for filtering models.
            
        Returns:
            dict: List of all models with their properties.
        """
        return self._make_request("GET", "/models", params=params)
    
    def list_models_by_preferences(self, params: Optional[Dict] = None) -> Dict:
        """List models filtered by user provider preferences.
        
        Args:
            params (dict, optional): Query parameters for filtering.
            
        Returns:
            dict: List of models filtered by user provider preferences.
        """
        return self._make_request("GET", "/models/preferences", params=params)
    
    # Endpoints
    def list_model_endpoints(self, model_id: str) -> Dict:
        """List all endpoints for a model.
        
        Args:
            model_id (str): The model ID to get endpoints for.
            
        Returns:
            dict: List of all endpoints for the specified model.
        """
        return self._make_request("GET", f"/models/{model_id}/endpoints")
    
    def preview_zdr_impact(self, model_id: str) -> Dict:
        """Preview the impact of ZDR (Zero Data Retention) on the available endpoints.
        
        Args:
            model_id (str): The model ID to preview ZDR impact for.
            
        Returns:
            dict: Preview of ZDR impact on available endpoints.
        """
        return self._make_request("GET", f"/models/{model_id}/endpoints/preview-zdr")
    
    # Parameters
    def get_model_parameters(self, model_id: str) -> Dict:
        """Get a model's supported parameters and data about which are most popular.
        
        Args:
            model_id (str): The model ID to get parameters for.
            
        Returns:
            dict: Model parameters and popularity data.
        """
        return self._make_request("GET", f"/models/{model_id}/parameters")
    
    # Providers
    def list_providers(self) -> Dict:
        """List all providers.
        
        Returns:
            dict: List of all providers with their information.
        """
        return self._make_request("GET", "/providers")
    
    # API Keys
    def list_api_keys(self) -> Dict:
        """List API keys.
        
        Returns:
            dict: List of all API keys.
        """
        return self._make_request("GET", "/api-keys")
    
    def create_api_key(self, data: Dict) -> Dict:
        """Create a new API key.
        
        Args:
            data (dict): API key creation data (name, permissions, etc.).
            
        Returns:
            dict: Created API key information.
        """
        return self._make_request("POST", "/api-keys", data=data)
    
    def get_api_key(self, key_id: str) -> Dict:
        """Get a single API key.
        
        Args:
            key_id (str): The API key ID to retrieve.
            
        Returns:
            dict: API key information.
        """
        return self._make_request("GET", f"/api-keys/{key_id}")
    
    def delete_api_key(self, key_id: str) -> Dict:
        """Delete an API key.
        
        Args:
            key_id (str): The API key ID to delete.
            
        Returns:
            dict: Deletion confirmation.
        """
        return self._make_request("DELETE", f"/api-keys/{key_id}")
    
    def update_api_key(self, key_id: str, data: Dict) -> Dict:
        """Update an API key.
        
        Args:
            key_id (str): The API key ID to update.
            data (dict): Update data for the API key.
            
        Returns:
            dict: Updated API key information.
        """
        return self._make_request("PATCH", f"/api-keys/{key_id}", data=data)
    
    def get_current_api_key(self) -> Dict:
        """Get current API key.
        
        Returns:
            dict: Current API key information.
        """
        return self._make_request("GET", "/api-keys/current")
    
    # OAuth
    def exchange_auth_code(self, data: Dict) -> Dict:
        """Exchange authorization code for API key.
        
        Args:
            data (dict): Authorization code and related data.
            
        Returns:
            dict: API key from authorization code exchange.
        """
        return self._make_request("POST", "/oauth/token", data=data)
    
    def create_auth_code(self, data: Dict) -> Dict:
        """Create authorization code.
        
        Args:
            data (dict): Data for creating authorization code.
            
        Returns:
            dict: Authorization code information.
        """
        return self._make_request("POST", "/oauth/authorize", data=data)
    
    # Chat
    def create_chat_completion(self, data: Dict) -> Dict:
        """Create a chat completion.
        
        Args:
            data (dict): Chat completion request data (model, messages, etc.).
            
        Returns:
            dict: Chat completion response.
        """
        return self._make_request("POST", "/chat/completions", data=data)
    
    # Completions
    def create_completion(self, data: Dict) -> Dict:
        """Create a completion.
        
        Args:
            data (dict): Completion request data (model, prompt, etc.).
            
        Returns:
            dict: Completion response.
        """
        return self._make_request("POST", "/completions", data=data)


def as_tools(configuration: OpenRouterAPIIntegrationConfiguration):
    """Convert OpenRouterAPIIntegration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field
    
    integration = OpenRouterAPIIntegration(configuration)

    class CreateChatCompletionSchema(BaseModel):
        model: str = Field(..., description="The model to use for chat completion")
        messages: list = Field(..., description="List of messages for the chat")

    class ListModelsSchema(BaseModel):
        provider: Optional[str] = Field(None, description="Filter models by provider")

    class EmptySchema(BaseModel):
        pass

    return [
        StructuredTool(
            name="openrouter_create_chat_completion",
            description="Create a chat completion using OpenRouter API",
            func=lambda data: integration.create_chat_completion(data),
            args_schema=CreateChatCompletionSchema
        ),
        StructuredTool(
            name="openrouter_list_models",
            description="List all available models from OpenRouter",
            func=lambda **kwargs: integration.list_all_models(**kwargs),
            args_schema=ListModelsSchema
        ),
        StructuredTool(
            name="openrouter_list_providers",
            description="List all providers from OpenRouter",
            func=lambda: integration.list_providers(),
            args_schema=EmptySchema
        ),
    ]