# Perplexity Module

## Description

The Perplexity Module provides comprehensive integration with Perplexity AI's search and question-answering capabilities. This module enables:

- Performing web searches using Perplexity's AI-powered search engine
- Getting accurate, trusted, and real-time answers to questions
- Accessing external data and open data from the web
- Using Perplexity as an AI agent with specialized search capabilities
- Caching responses to improve performance and reduce API calls

## TL;DR

To get started with the Perplexity module:

1. Obtain an API key from [Perplexity AI](https://www.perplexity.ai/)
2. Configure your `PERPLEXITY_API_KEY` in your secrets configuration file
3. Update the parameters in the example scripts below to match your use case
4. Run the scripts to test the integration

```bash
# Test basic Perplexity integration
uv run python src/custom/modules/perplexity/integrations/PerplexityIntegration.py
```

To chat with the Perplexity agent with search capabilities, run:
```bash
make chat agent=PerplexityAgent
```

## Overview

### Structure

```
src/custom/modules/perplexity/
├── integrations/                    # Core integration classes
│   ├── PerplexityIntegration.py                    # Basic Perplexity API integration
│   └── PerplexityIntegration_test.py               # Integration tests
├── agents/                         # AI agent implementations
│   ├── PerplexityAgent.py          # Perplexity agent with search capabilities
│   └── PerplexityAgent_test.py     # Agent tests
└── README.md                       # This documentation
```

### Integrations

#### PerplexityIntegration
Core integration class that provides:
- `search_web()`: Perform web searches using Perplexity AI
- Configurable search parameters (model, reasoning effort, temperature, etc.)
- Support for various search modes and filters
- Automatic datetime context for time-sensitive queries
- LangChain tool integration for AI agent usage

### Agents

#### PerplexityAgent
Specialized agent that provides:
- Direct access to Perplexity AI with web search capabilities
- Automatic datetime context for time-sensitive queries
- Structured response formatting with source citations
- Professional search and analysis capabilities
- Integration with current datetime tool for Paris timezone

## Configuration

### API Key Setup

1. Get an API key from [Perplexity AI](https://www.perplexity.ai/)
2. Add your API key to your secrets configuration:
   ```python
   # In your secrets configuration
   PERPLEXITY_API_KEY = "your_api_key_here"
   ```

### Integration Configuration

```python
from src.custom.modules.perplexity.integrations.PerplexityIntegration import (
    PerplexityIntegration,
    PerplexityIntegrationConfiguration
)

# Create configuration
config = PerplexityIntegrationConfiguration(
    api_key="your_api_key_here"
)

# Initialize integration
integration = PerplexityIntegration(config)
```

## Usage Examples

### Basic Web Search

```python
# Create a simple web search
response = integration.search_web(
    question="What is the capital of France?",
    system_prompt="Be precise and concise and answer the question with sources.",
    model="sonar-pro",
    search_mode="web"
)

print(response)
```

### Advanced Search with Filters

```python
# Search with specific filters and parameters
response = integration.search_web(
    question="Latest developments in renewable energy",
    model="sonar-pro",
    reasoning_effort="high",
    temperature=0.1,
    search_recency_filter="week",
    search_domain_filter=["techcrunch.com", "wired.com"],
    return_related_questions=True,
    search_context_size="high"
)
```

### Using with LangChain Tools

```python
from src.custom.modules.perplexity.integrations.PerplexityIntegration import as_tools

# Convert integration to LangChain tools
tools = as_tools(config)

# Use in LangChain agent
# The tools will be available as:
# - perplexity_search_web
```

### Perplexity Agent

```python
from src.custom.modules.perplexity.agents.PerplexityAgent import create_agent

# Create Perplexity agent with search capabilities
agent = create_agent()

# The agent automatically includes:
# - Web search functionality via Perplexity AI
# - Current datetime context in Paris timezone
# - Structured response formatting
# - Source citation requirements
# - Professional search capabilities
```

## API Endpoints

The module supports the following Perplexity API endpoints:

- **Chat Completions API**: Search the web and get AI-powered answers
- **Web Search**: Direct web search capabilities with various filters
- **Real-time Data**: Access to current and up-to-date information

## Search Parameters

The `search_web` method supports various parameters:

### Core Parameters
- `question` (str): The question to search for
- `system_prompt` (str): System prompt for the AI (default: "Be precise and concise and answer the question with sources.")
- `model` (str): Perplexity model to use (default: "sonar-pro")

### Search Configuration
- `search_mode` (str): Search mode - "web", "scholar", etc.
- `search_context_size` (str): Context size - "low", "medium", "high"
- `search_recency_filter` (str): Time filter - "day", "week", "month", "year"
- `search_domain_filter` (List[str]): Specific domains to search

### AI Parameters
- `reasoning_effort` (str): AI reasoning level - "low", "medium", "high"
- `temperature` (float): Response creativity (0.0-1.0)
- `max_tokens` (int): Maximum response length
- `top_p` (float): Nucleus sampling parameter
- `frequency_penalty` (float): Frequency penalty for repetition

### Additional Features
- `return_images` (bool): Include images in response
- `return_related_questions` (bool): Include related questions
- `user_location` (str): User location for localized results

## Agent Features

The PerplexityAgent provides:

### Automatic Context
- Gets current datetime in Paris timezone
- Includes datetime context in queries when relevant
- Example: "le gagnant de la dernière ligue des champions masculin" becomes "Current datetime: 2025-06-25 10:00:00 : le gagnant de la dernière ligue des champions masculin"

### Response Formatting
- Starts responses with "> Perplexity Agent" + 2 blank lines
- Always includes at least 1 source
- Formats sources at the end of response:
```
**Sources:**
- [Source Name](source_url)
```

### Professional Capabilities
- Expert knowledge of Perplexity AI
- Accurate and comprehensive information retrieval
- Trusted and real-time answers
- Source citation requirements

## Testing

### Run Integration Tests

```bash
# Test basic Perplexity integration
uv run python -m pytest src/custom/modules/perplexity/integrations/PerplexityIntegration_test.py

# Test Perplexity agent
uv run python -m pytest src/custom/modules/perplexity/agents/PerplexityAgent_test.py
```

### Test Integrations Directly

```bash
# Test web search with example query
uv run python src/custom/modules/perplexity/integrations/PerplexityIntegration.py
```

## Error Handling

The module includes comprehensive error handling:
- Network connection errors
- API authentication failures
- Invalid request parameters
- Rate limiting responses
- Search result processing errors

All errors are properly logged and handled gracefully to ensure robust operation.

## Rate Limits

Please refer to your Perplexity AI subscription plan for rate limits:
- Different models may have different rate limits
- Web search features may have additional constraints
- The caching mechanism helps minimize API calls and stay within rate limits

## Dependencies

- `requests`: HTTP client for API calls
- `pydantic`: Data validation and serialization
- `langchain_core`: Tool integration for AI agents
- `langchain_openai`: LangChain OpenAI integration
- `abi.integration`: Base integration framework
- `abi.services.agent`: Agent framework
- `fastapi`: API router for agent endpoints

## Models Supported

- **sonar-pro**: Primary Perplexity model for web search and Q&A
- **Other Perplexity models**: All models available through the Perplexity API

## Search Modes

- **web**: Standard web search
- **scholar**: Academic research search
- **news**: News-focused search
- **youtube**: YouTube content search
- **reddit**: Reddit content search

## Use Cases

- **Research**: Academic and professional research
- **News**: Current events and breaking news
- **Fact-checking**: Verify information with sources
- **Market research**: Industry and market analysis
- **Technical queries**: Programming and technical questions
- **General knowledge**: Educational and informational queries

