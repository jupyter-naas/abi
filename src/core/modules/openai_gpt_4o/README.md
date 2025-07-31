# OpenAI Module

## Description

The OpenAI Module provides comprehensive integration with OpenAI's API services, including chat completions, web search capabilities, and deep research workflows. This module enables:

- Creating chat completions with various OpenAI models
- Performing web searches using OpenAI's web search tools
- Conducting deep research with structured analysis and data interpretation
- Managing OpenAI agents with specialized capabilities
- Caching responses to improve performance and reduce API calls

## TL;DR

To get started with the OpenAI module:

1. Obtain an API key from [OpenAI's platform](https://platform.openai.com/)
2. Configure your `OPENAI_API_KEY` in your secrets configuration file
3. Update the parameters in the example scripts below to match your use case
4. Run the scripts to test the integration

```bash
# Test basic OpenAI integration
uv run python src/custom/modules/openai/integrations/OpenAIIntegration.py

# Test deep research capabilities
uv run python src/custom/modules/openai/integrations/OpenAIDeepResearchIntegration.py
```

To chat with the ChatGPT agent with web search capabilities, run:
```bash
make chat agent=ChatGPT
```

## Overview

### Structure

```
src/custom/modules/openai/
├── integrations/                    # Core integration classes
│   ├── OpenAIIntegration.py                    # Basic OpenAI API integration
│   ├── OpenAIIntegration_test.py               # Integration tests
│   ├── OpenAIDeepResearchIntegration.py        # Deep research workflow
│   ├── OpenAIDeepResearchIntegration_test.py   # Deep research tests
│   ├── OpenAIWebSearchIntegration.py           # Web search integration
│   └── OpenAIWebSearchIntegration_test.py      # Web search tests
├── agents/                         # AI agent implementations
│   ├── ChatGPTAgent.py             # ChatGPT agent with web search
│   └── ChatGPTAgent_test.py        # Agent tests
└── README.md                       # This documentation
```

### Integrations

#### OpenAIIntegration
Core integration class that provides:
- `list_models()`: Get all available OpenAI models
- `retrieve_model(model_id)`: Get details of a specific model
- `create_chat_completion()`: Create chat completions with various parameters
- `create_chat_completion_beta()`: Create structured output completions
- Automatic caching of model information and responses
- LangChain tool integration for AI agent usage

#### OpenAIDeepResearchIntegration
Advanced research workflow that provides:
- `run(query)`: Execute deep research with web search and code interpretation
- Support for different research models (o4-mini-deep-research, o3-deep-research)
- Structured system prompts for professional research reports
- Integration with web search and code interpreter tools
- Caching of research results

#### OpenAIWebSearchIntegration
Web search capabilities:
- `search_web(query, search_context_size)`: Perform web searches
- Configurable search context sizes (low, medium, high)
- Caching of search results
- LangChain tool integration

### Agents

#### ChatGPTAgent
Specialized agent that provides:
- Direct access to GPT-4o with web search capabilities
- Automatic datetime context for time-sensitive queries
- Structured response formatting with source citations
- Professional research and analysis capabilities

## Configuration

### API Key Setup

1. Get an API key from [OpenAI Platform](https://platform.openai.com/)
2. Add your API key to your secrets configuration:
   ```python
   # In your secrets configuration
   OPENAI_API_KEY = "your_api_key_here"
   ```

### Integration Configuration

```python
from src.custom.modules.openai.integrations.OpenAIIntegration import (
    OpenAIIntegration,
    OpenAIIntegrationConfiguration
)

# Create configuration
config = OpenAIIntegrationConfiguration(
    api_key="your_api_key_here"
)

# Initialize integration
integration = OpenAIIntegration(config)
```

## Usage Examples

### Basic Chat Completion

```python
# Create a simple chat completion
response = integration.create_chat_completion(
    prompt="What is the capital of France?",
    system_prompt="You are a helpful assistant.",
    model="gpt-4o",
    temperature=0.7
)

# Use with message list
messages = [
    {"role": "user", "content": "Hello, how are you?"},
    {"role": "assistant", "content": "I'm doing well, thank you!"}
]
response = integration.create_chat_completion(
    messages=messages,
    model="gpt-4o"
)
```

### Deep Research

```python
from src.custom.modules.openai.integrations.OpenAIDeepResearchIntegration import (
    OpenAIDeepResearchIntegration,
    OpenAIDeepResearchIntegrationConfiguration,
    DeepResearchModel
)

# Configure deep research
config = OpenAIDeepResearchIntegrationConfiguration(
    openai_api_key="your_api_key_here",
    model=DeepResearchModel.o3_deep_research
)

# Initialize and run research
research = OpenAIDeepResearchIntegration(config)
results = research.run("Analyze the current state of renewable energy markets")
```

### Web Search

```python
from src.custom.modules.openai.integrations.OpenAIWebSearchIntegration import (
    OpenAIWebSearchIntegration,
    OpenAIWebSearchIntegrationConfiguration
)

# Configure web search
config = OpenAIWebSearchIntegrationConfiguration(
    api_key="your_api_key_here",
    model="gpt-4o"
)

# Initialize and search
search = OpenAIWebSearchIntegration(config)
results = search.search_web(
    query="Latest developments in AI technology",
    search_context_size="medium"
)
```

### Using with LangChain Tools

```python
from src.custom.modules.openai.integrations.OpenAIIntegration import as_tools

# Convert integration to LangChain tools
tools = as_tools(config)

# Use in LangChain agent
# The tools will be available as:
# - openai_list_models
# - openai_retrieve_model
# - openai_create_chat_completion
# - openai_create_chat_completion_beta
```

### ChatGPT Agent

```python
from src.custom.modules.openai.agents.ChatGPTAgent import create_agent

# Create ChatGPT agent with web search capabilities
agent = create_agent()

# The agent automatically includes:
# - Web search functionality
# - Current datetime context
# - Structured response formatting
# - Source citation requirements
```

## API Endpoints

The module supports the following OpenAI API endpoints:

- **Models API**: List and retrieve model information
- **Chat Completions API**: Create chat completions with various models
- **Responses API**: Advanced responses with tools (web search, code interpreter)
- **Web Search**: Direct web search capabilities

## Caching

The module implements intelligent caching to:
- Reduce API calls and improve performance
- Cache responses based on request parameters
- Store data in appropriate formats (JSON, PICKLE)

Cache keys are automatically generated based on:
- Model ID for model information
- Query and context size for web searches
- Query and model configuration for deep research
- Request parameters for chat completions

## Testing

### Run Integration Tests

```bash
# Test basic OpenAI integration
uv run python -m pytest src/custom/modules/openai/integrations/OpenAIIntegration_test.py

# Test deep research integration
uv run python -m pytest src/custom/modules/openai/integrations/OpenAIDeepResearchIntegration_test.py

# Test web search integration
uv run python -m pytest src/custom/modules/openai/integrations/OpenAIWebSearchIntegration_test.py

# Test ChatGPT agent
uv run python -m pytest src/custom/modules/openai/agents/ChatGPTAgent_test.py
```

### Test Integrations Directly

```bash
# Test deep research with example query
uv run python src/custom/modules/openai/integrations/OpenAIDeepResearchIntegration.py
```

## Error Handling

The module includes comprehensive error handling:
- Network connection errors
- API authentication failures
- Invalid request parameters
- Rate limiting responses
- Model availability issues

All errors are properly logged and handled gracefully to ensure robust operation.

## Rate Limits

Please refer to your OpenAI subscription plan for rate limits:
- Different models have different rate limits
- Web search and deep research features may have additional constraints
- The caching mechanism helps minimize API calls and stay within rate limits

## Dependencies

- `openai`: Official OpenAI Python client
- `requests`: HTTP client for API calls
- `pydantic`: Data validation and serialization
- `langchain_core`: Tool integration for AI agents
- `langchain_openai`: LangChain OpenAI integration
- `abi.integration`: Base integration framework
- `abi.services.cache`: Caching functionality
- `abi.services.agent`: Agent framework

## Models Supported

- **GPT-4o**: Latest GPT-4 model with improved performance
- **GPT-4o-mini**: Faster, more efficient GPT-4 variant
- **o3-deep-research**: Specialized model for deep research workflows
- **o4-mini-deep-research**: Fast research model with good accuracy
- **Other OpenAI models**: All models available through the OpenAI API

