# Building Integrations

This guide explains how to build custom integrations in the ABI framework to connect with external systems and data sources.

## Prerequisites

Before creating an integration, you should have:

- A working ABI installation
- Understanding of the [ABI architecture](../concepts/architecture.md)
- Familiarity with the [integration concept](../concepts/integrations.md)
- Knowledge of the external system's API or interface
- Appropriate credentials for the external system

## Integration Structure

A typical ABI integration consists of these components:

1. **Configuration Class**: Defines parameters needed to connect to the external system
2. **Integration Class**: Implements the connection and interaction logic
3. **Authentication Logic**: Handles credentials and authentication flows
4. **API Methods**: Specific methods for interacting with the external system
5. **Response Parsers**: Convert external system data to internal formats

## Steps to Build an Integration

### 1. Define the Integration Configuration

Create a configuration class that extends `IntegrationConfiguration`:

```python
from lib.abi.integration.integration import Integration, IntegrationConfiguration
from dataclasses import dataclass

@dataclass
class SlackIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for Slack integration.
    
    Attributes:
        bot_token (str): Slack bot token for API access
        app_token (str): Slack app-level token
        default_channel (str): Default channel to post messages to
        retry_attempts (int): Number of retry attempts for failed API calls
    """
    bot_token: str
    app_token: str
    default_channel: str = "general"
    retry_attempts: int = 3
```

### 2. Create the Integration Class

Implement the core integration class that extends the `Integration` base class:

```python
import requests
from typing import Dict, List, Optional

class SlackIntegration(Integration):
    """Integration for interacting with Slack's API.
    
    This class provides methods to interact with Slack workspaces,
    including messaging, user management, and channel operations.
    
    Attributes:
        __configuration (SlackIntegrationConfiguration): Configuration
            instance containing necessary credentials and settings.
    """
    
    __configuration: SlackIntegrationConfiguration
    
    def __init__(self, configuration: SlackIntegrationConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__session = requests.Session()
        self.__session.headers.update({
            "Authorization": f"Bearer {configuration.bot_token}",
            "Content-Type": "application/json; charset=utf-8"
        })
        self.__base_url = "https://slack.com/api"
```

### 3. Implement Authentication Logic

Handle authentication with the external system:

```python
def _verify_auth(self) -> bool:
    """Verify authentication with Slack.
    
    Returns:
        bool: True if authentication is valid, False otherwise
    """
    response = self.__session.get(f"{self.__base_url}/auth.test")
    
    if response.status_code == 200:
        data = response.json()
        if data.get("ok", False):
            self.__team_id = data.get("team_id")
            self.__bot_id = data.get("user_id")
            return True
            
    return False

def _refresh_token(self) -> bool:
    """Refresh authentication token if possible.
    
    Returns:
        bool: True if token refresh succeeded, False otherwise
    """
    # Implementation depends on the specific authentication flow
    # For Slack, might need to use the app token to get a new bot token
    # or a refresh token flow
    
    # This is a placeholder implementation
    return False
```

### 4. Add API Methods

Implement methods for specific API interactions:

```python
def send_message(self, message: str, channel: Optional[str] = None) -> Dict:
    """Send a message to a Slack channel.
    
    Args:
        message (str): Message text to send
        channel (Optional[str]): Channel to send to, defaults to the
            configured default_channel if not specified
    
    Returns:
        Dict: API response from Slack
    """
    target_channel = channel or self.__configuration.default_channel
    
    payload = {
        "channel": target_channel,
        "text": message
    }
    
    for attempt in range(self.__configuration.retry_attempts):
        response = self.__session.post(
            f"{self.__base_url}/chat.postMessage",
            json=payload
        )
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            # Authentication issue, try to refresh
            if self._refresh_token():
                continue
        
        # Wait before retry
        time.sleep(1 * (attempt + 1))
    
    # All attempts failed
    raise IntegrationError(f"Failed to send message after {self.__configuration.retry_attempts} attempts")

def list_channels(self) -> List[Dict]:
    """List all channels in the workspace.
    
    Returns:
        List[Dict]: List of channel information dictionaries
    """
    response = self.__session.get(f"{self.__base_url}/conversations.list")
    
    if response.status_code == 200:
        data = response.json()
        if data.get("ok", False):
            return data.get("channels", [])
    
    raise IntegrationError("Failed to list channels")
```

### 5. Implement Error Handling

Add proper error handling for API calls:

```python
class IntegrationError(Exception):
    """Exception raised for integration errors."""
    pass

def _handle_error_response(self, response) -> None:
    """Handle error responses from the API.
    
    Args:
        response: The API response to handle
        
    Raises:
        IntegrationError: with appropriate error message
    """
    if response.status_code == 429:
        # Rate limiting
        retry_after = int(response.headers.get("Retry-After", 1))
        raise IntegrationError(f"Rate limited. Retry after {retry_after} seconds")
    elif response.status_code == 401:
        raise IntegrationError("Authentication failed. Check credentials")
    elif response.status_code == 403:
        raise IntegrationError("Permission denied for this operation")
    else:
        # Generic error
        try:
            error_data = response.json()
            error_message = error_data.get("error", "Unknown error")
        except:
            error_message = f"HTTP error {response.status_code}"
        
        raise IntegrationError(f"API error: {error_message}")
```

### 6. Add Utility Methods

Implement helper methods for common operations:

```python
def get_user_info(self, user_id: str) -> Dict:
    """Get information about a Slack user.
    
    Args:
        user_id (str): The Slack user ID
    
    Returns:
        Dict: User information
    """
    response = self.__session.get(
        f"{self.__base_url}/users.info",
        params={"user": user_id}
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get("ok", False):
            return data.get("user", {})
    
    self._handle_error_response(response)

def upload_file(self, file_path: str, channels: str, title: Optional[str] = None) -> Dict:
    """Upload a file to Slack channels.
    
    Args:
        file_path (str): Path to the file to upload
        channels (str): Comma-separated list of channel IDs
        title (Optional[str]): Title for the upload
    
    Returns:
        Dict: API response
    """
    with open(file_path, 'rb') as file:
        response = self.__session.post(
            f"{self.__base_url}/files.upload",
            data={
                "channels": channels,
                "title": title or os.path.basename(file_path)
            },
            files={"file": file}
        )
    
    if response.status_code == 200:
        return response.json()
    
    self._handle_error_response(response)
```

### 7. Testing Your Integration

Create tests for your integration:

```python
import unittest
from unittest.mock import patch, MagicMock

class TestSlackIntegration(unittest.TestCase):
    """Tests for the Slack integration."""
    
    def setUp(self):
        """Set up test environment."""
        self.config = SlackIntegrationConfiguration(
            bot_token="xoxb-test-token",
            app_token="xapp-test-token",
            default_channel="test-channel"
        )
        self.integration = SlackIntegration(self.config)
    
    @patch('requests.Session.post')
    def test_send_message(self, mock_post):
        """Test sending a message to Slack."""
        # Setup mock
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True, "message": {"text": "Test message"}}
        mock_post.return_value = mock_response
        
        # Call method
        result = self.integration.send_message("Test message")
        
        # Assertions
        self.assertTrue(result["ok"])
        mock_post.assert_called_once()
        call_args = mock_post.call_args[1]
        self.assertEqual(call_args["json"]["text"], "Test message")
        self.assertEqual(call_args["json"]["channel"], "test-channel")
```

### 8. Integration with Pipelines

Example of using your integration in a pipeline:

```python
class SlackMessagePipeline(Pipeline):
    """Pipeline for processing Slack messages and storing in ontology."""
    
    __configuration: SlackMessagePipelineConfiguration
    
    def __init__(self, configuration: SlackMessagePipelineConfiguration):
        self.__configuration = configuration
        self.__slack = configuration.slack_integration
    
    def run(self, parameters: SlackMessagePipelineParameters) -> Graph:
        """Run the pipeline to extract message data.
        
        Args:
            parameters: Pipeline parameters
            
        Returns:
            Graph containing message data
        """
        # Create graph
        graph = ABIGraph()
        
        # Get channel history
        channel_messages = self.__slack.get_channel_history(
            parameters.channel_id,
            oldest=parameters.start_timestamp,
            latest=parameters.end_timestamp
        )
        
        # Process each message
        for message in channel_messages:
            # Extract data and add to graph
            message_uri = graph.create_entity(
                "Message",
                {
                    "id": message.get("ts"),
                    "text": message.get("text"),
                    "timestamp": message.get("ts"),
                    "channel": parameters.channel_id
                }
            )
            
            # Get user info if available
            if "user" in message:
                user_info = self.__slack.get_user_info(message["user"])
                user_uri = graph.create_entity(
                    "Person",
                    {
                        "id": user_info.get("id"),
                        "name": user_info.get("real_name"),
                        "email": user_info.get("profile", {}).get("email", "")
                    }
                )
                
                # Link message to user
                graph.create_relationship(
                    message_uri,
                    "sentBy",
                    user_uri
                )
        
        # Store in ontology
        self.__configuration.ontology_store.insert(
            self.__configuration.ontology_store_name,
            graph
        )
        
        return graph
```

## Best Practices

### Configuration Management

- Keep sensitive information (tokens, passwords) in environment variables or a secure vault
- Use defaults for non-sensitive, common configuration values
- Document each configuration parameter with clear descriptions

### Error Handling

- Always handle API errors gracefully
- Implement proper retry mechanisms with exponential backoff
- Log detailed error information for debugging
- Provide clear error messages to calling code

### Performance Considerations

- Implement request batching where appropriate
- Use connection pooling for efficiency
- Cache responses when appropriate
- Be mindful of rate limits

### Security Best Practices

- Never hardcode credentials in your integration code
- Validate and sanitize all inputs to API calls
- Use the principle of least privilege for API tokens
- Implement proper token refresh and rotation

### Code Organization

- Use clean, consistent code structure
- Separate concerns: authentication, request building, error handling
- Use meaningful method names that reflect API terminology
- Document classes and methods thoroughly

## Advanced Integration Features

### Webhooks and Event Listeners

For systems that support webhooks:

```python
def register_webhook(self, event_type: str, callback_url: str) -> Dict:
    """Register a webhook for event notifications.
    
    Args:
        event_type: The type of event to listen for
        callback_url: URL to call when event occurs
        
    Returns:
        Dict: Webhook registration response
    """
    payload = {
        "event_type": event_type,
        "callback_url": callback_url
    }
    
    response = self.__session.post(
        f"{self.__base_url}/webhooks.register",
        json=payload
    )
    
    if response.status_code == 200:
        return response.json()
    
    self._handle_error_response(response)
```

### Batch Operations

For efficient bulk operations:

```python
def send_batch_messages(self, messages: List[Dict]) -> List[Dict]:
    """Send multiple messages in a batch.
    
    Args:
        messages: List of message dictionaries, each containing
                 text and channel keys
                 
    Returns:
        List[Dict]: List of API responses
    """
    if not messages:
        return []
    
    # Some APIs support true batch operations
    if self.__supports_native_batch:
        response = self.__session.post(
            f"{self.__base_url}/chat.postBatchMessages",
            json={"messages": messages}
        )
        
        if response.status_code == 200:
            return response.json().get("responses", [])
        self._handle_error_response(response)
    
    # Fallback: Sequential processing with rate limiting
    responses = []
    for message in messages:
        responses.append(self.send_message(
            message["text"], 
            message.get("channel", self.__configuration.default_channel)
        ))
        time.sleep(0.5)  # Rate limiting
    
    return responses
```

### Pagination Handling

For APIs with paginated results:

```python
def list_all_users(self) -> List[Dict]:
    """List all users in the workspace, handling pagination.
    
    Returns:
        List[Dict]: Complete list of users
    """
    all_users = []
    cursor = None
    
    while True:
        params = {"limit": 100}
        if cursor:
            params["cursor"] = cursor
        
        response = self.__session.get(
            f"{self.__base_url}/users.list",
            params=params
        )
        
        if response.status_code != 200:
            self._handle_error_response(response)
            
        data = response.json()
        if not data.get("ok", False):
            break
            
        all_users.extend(data.get("members", []))
        
        # Check if there are more pages
        cursor = data.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    
    return all_users
```

## Next Steps

- Learn about [Developing Pipelines](developing-pipelines.md) to process data from your integration
- Explore [Writing Workflows](writing-workflows.md) to build business processes using your integration
- Review [Managing Ontologies](managing-ontologies.md) to understand how integration data maps to your knowledge graph 