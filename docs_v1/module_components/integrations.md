# Integrations

## Overview

Integrations in ABI are specialized classes that serve as technological bridges between ABI and third-party APIs, services, or technologies. They provide a standardized way to interact with external systems, making it easy to incorporate any technology or third-party service into the ABI ecosystem.

Integrations are the foundational building blocks of ABI's architecture, designed to be the smallest, most atomic resources that don't depend on other ABI components. They are like the "electrons" of the system - the fundamental particles that enable more complex structures to be built.

## Purpose and Benefits

Integrations serve several key purposes in the ABI ecosystem:

1. **Standardized Access**: They provide a consistent interface for accessing external services, abstracting away the complexities of different APIs and authentication methods.

2. **Reusability**: Once created, an integration can be used by multiple pipelines and workflows, promoting code reuse and maintainability.

3. **Separation of Concerns**: Integrations focus solely on communication with external services, while pipelines handle data transformation and workflows manage business logic.

4. **Tool Exposure**: Integrations can be exposed as tools for LLM agents, allowing them to interact directly with external services when needed.

## Architecture

Integrations fit into ABI's layered architecture as follows:

```
┌─────────────────┐
│    Workflows    │ ← Business logic layer
├─────────────────┤
│    Pipelines    │ ← Data transformation layer
├─────────────────┤
│  Integrations   │ ← External service communication layer
└─────────────────┘
```

- **Integrations** communicate with external services and provide raw data
- **Pipelines** use integrations to fetch data and transform it into ontological data (semantic layer)
- **Workflows** orchestrate pipelines and query the ontology directly

### Key Relationships

- An integration should never depend on pipelines or workflows
- Pipelines typically use integrations to fetch and transform data
- Workflows can use both pipelines and integrations, but typically use pipelines for data ingestion and may use integrations directly for specific operations

## Use Cases

### Integration as a Tool for LLM Agents

When an integration is exposed as a tool, it can be used directly by LLM agents to interact with external services. This is particularly useful when:

- You don't have a pipeline built yet to ingest data from a third-party into the ontology
- You need direct, real-time access to a third-party service
- You want to perform operations that don't require semantic transformation

For example, a GitHub integration could be used by an LLM agent to:
- List issues in a repository
- Create new issues
- List pull requests
- View contributors
- Any other operation supported by the GitHub API

### Integration as Part of a Pipeline

Integrations are primarily designed to be used by pipelines, which:
1. Use the integration to fetch raw data from external services
2. Transform that data into ontological (semantic) data
3. Store the transformed data in the ontology store

This pattern allows ABI to build a rich semantic layer on top of various data sources.

## Creating a New Integration

To create a new integration in ABI, follow these steps:

1. Create a new file in `src/custom/modules/<module_name>/integrations/YourIntegrationName.py` using the template below
2. Implement the necessary methods to interact with the external service
3. Add configuration parameters as needed
4. Implement the `as_tools()` function to expose the integration as tools for LLM agents

### Integration Template

```python
from lib.abi.integration.integration import Integration, IntegrationConfiguration
from dataclasses import dataclass

@dataclass
class YourIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for YourIntegration.
    
    Attributes:
        attribute_1 (str): Description of attribute_1
        attribute_2 (int): Description of attribute_2
    """
    attribute_1: str
    attribute_2: int

class YourIntegration(Integration):
    """YourIntegration class for interacting with YourService.
    
    This class provides methods to interact with YourService's API endpoints.
    It handles authentication and request management.
    
    Attributes:
        __configuration (YourIntegrationConfiguration): Configuration instance
            containing necessary credentials and settings.
    
    Example:
        >>> config = YourIntegrationConfiguration(
        ...     attribute_1="value1",
        ...     attribute_2=42
        ... )
        >>> integration = YourIntegration(config)
    """

    __configuration: YourIntegrationConfiguration

    def __init__(self, configuration: YourIntegrationConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        
    # Add methods to interact with the external service
    def _make_request(self, endpoint: str, method: str = "GET", params: dict = None, json: dict = None) -> dict:
        """Make HTTP request to YourService's API endpoint.
        
        Args:
            endpoint (str): The API endpoint to request.
            method (str): HTTP method to use (default: "GET").
            params (dict): Query parameters for the request.
            json (dict): JSON body for the request.
        
        Returns:
            dict: Response data from the API.
        """
        # Implementation details...
        pass
    
    def example_method(self, parameter: str) -> dict:
        """Example method description.
        
        Args:
            parameter (str): Description of parameter.
            
        Returns:
            dict: Description of return value.
            
        Example:
            >>> integration = YourIntegration(config)
            >>> result = integration.example_method("example")
        """
        return self._make_request(f"/endpoint/{parameter}")
```

### Exposing the Integration as Tools

To expose your integration as tools for LLM agents, implement the `as_tools()` function:

```python
def as_tools(configuration: YourIntegrationConfiguration):
    """Convert YourIntegration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field
    
    integration = YourIntegration(configuration)

    class ExampleToolSchema(BaseModel):
        parameter: str = Field(..., description="Description of parameter")

    return [
        StructuredTool(
            name="your_example_tool",
            description="Description of what this tool does",
            func=integration.example_method,
            args_schema=ExampleToolSchema
        )
    ]
```

## Best Practices

When creating integrations, follow these best practices:

1. **Single Responsibility**: An integration should focus solely on communicating with a specific external service.

2. **No Dependencies on Other ABI Components**: Integrations should not depend on pipelines, workflows, or other ABI-specific components.

3. **Comprehensive Documentation**: Document all methods, parameters, and return values thoroughly.

4. **Error Handling**: Implement proper error handling for API requests and other operations.

5. **Configuration Management**: Use the configuration class to manage credentials and other settings.

6. **Testing**: Create tests to verify that your integration works as expected.

7. **Security**: Handle sensitive information (like API keys) securely, using environment variables or secrets management.

## Conclusion

Integrations are the foundation of ABI's ability to connect with external services and data sources. By creating well-designed integrations, you enable the rest of the ABI ecosystem to leverage external services in a standardized, reusable way. Whether used directly by LLM agents as tools or as part of pipelines for data transformation, integrations play a crucial role in ABI's architecture.
