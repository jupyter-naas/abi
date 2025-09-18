# AIA Module

## Overview

### Description

The AIA (AI Assistant) Module provides comprehensive integration with the NAAS AI platform for creating personalized AI assistants based on LinkedIn profiles. This module enables the generation of AI-powered personal agents by analyzing LinkedIn profile data and creating tailored AI assistants for individuals and organizations.

This module enables:
- Personal AI assistant creation from LinkedIn profiles
- LinkedIn profile data extraction and analysis
- AI agent personalization based on professional background
- Integration with the NAAS AI platform
- Automated personal agent generation workflows

### Requirements

API Key Setup:
1. Obtain a NAAS API key from [NAAS Platform](https://naas.ai)
2. Get LinkedIn authentication cookies (`li_at` and `JSESSIONID`)
3. Configure your environment variables in your .env file:
   - `NAAS_API_KEY`: Your NAAS platform API key
   - `li_at`: LinkedIn authentication cookie
   - `JSESSIONID`: LinkedIn session cookie
   - `OPENAI_API_KEY`: OpenAI API key for AI processing

### TL;DR

To get started with the AIA module:

1. Obtain the required API keys and LinkedIn authentication cookies
2. Configure your environment variables in your .env file
3. Use the integration to create personalized AI assistants from LinkedIn profiles

Start using the AIA integration:
```python
from src.core.modules.aia.integrations.AiaIntegration import AiaIntegration, AiaIntegrationConfiguration

config = AiaIntegrationConfiguration(
    api_key="your_naas_api_key",
    li_at="your_linkedin_li_at_cookie",
    JSESSIONID="your_linkedin_jsessionid_cookie"
)

integration = AiaIntegration(config)
result = integration.create_aia(["https://www.linkedin.com/in/username/"])
```

### Structure

```
src/core/aia/
├── integrations/                    
│   ├── AiaIntegration_test.py               
│   └── AiaIntegration.py          
├── __init__.py                     
└── README.md                       
```

## Core Components

The AIA module provides a streamlined integration for creating personalized AI assistants from LinkedIn profile data.

### Integrations

#### AIA Integration

The main integration component that handles communication with the NAAS AI platform to create personalized AI assistants.

**Capabilities:**
- LinkedIn profile analysis and data extraction
- AI assistant creation based on professional background
- Integration with NAAS AI platform APIs
- Personal agent generation and configuration

**Key Functions:**
- `create_aia(linkedin_urls)`: Creates AI assistants from LinkedIn profile URLs

##### Configuration

```python
from src.core.modules.aia.integrations.AiaIntegration import (
    AiaIntegration,
    AiaIntegrationConfiguration
)

# Create configuration
config = AiaIntegrationConfiguration(
    api_key="your_naas_api_key",
    li_at="your_linkedin_li_at_cookie",
    JSESSIONID="your_linkedin_jsessionid_cookie",
    base_url="https://naas-abi-space.default.space.naas.ai"  # Optional, uses default
)

# Initialize integration
integration = AiaIntegration(config)
```

##### Usage

```python
# Create AI assistant from LinkedIn profile
linkedin_urls = ["https://www.linkedin.com/in/username/"]
result = integration.create_aia(linkedin_urls)
```

##### As LangChain Tools

The integration can be used as LangChain tools for agent workflows:

```python
from src.core.modules.aia.integrations.AiaIntegration import as_tools

# Get tools for agent use
tools = as_tools(config)

# The available tool:
# - aia_create_personal_agent: Create AIA Personal Assistant/Agent based on LinkedIn URL
```

#### Testing

Run the integration tests to verify functionality:
```bash
uv run python -m pytest src/core/aia/integrations/AiaIntegration_test.py
```

**Test Coverage:**
- AIA integration configuration validation
- LinkedIn URL processing and validation
- API communication and response handling
- Personal agent creation workflow

## Dependencies

### Python Libraries
- `abi.integration`: Base integration framework for NAAS platform
- `pydantic`: Data validation and serialization
- `requests`: HTTP client for API communication
- `langchain_core`: Tool integration for AI agents
- `dataclasses`: Configuration data structures

### External Services
- **NAAS AI Platform**: Core platform for AI assistant creation
- **LinkedIn**: Profile data source for personalization
- **OpenAI**: AI processing and language model services

### Authentication Requirements
- **NAAS API Key**: Required for platform access
- **LinkedIn Cookies**: Required for profile data access (`li_at`, `JSESSIONID`)
- **OpenAI API Key**: Required for AI processing capabilities

## API Reference

### AiaIntegration Class

#### Methods

**`create_aia(linkedin_urls: List[str]) -> Dict`**
- Creates personalized AI assistants from LinkedIn profile URLs
- **Parameters:** 
  - `linkedin_urls`: List of LinkedIn profile URLs to process
- **Returns:** API response with assistant creation details
- **Raises:** `IntegrationConnectionError` for API communication failures

#### Configuration

**`AiaIntegrationConfiguration`**
- `api_key` (str): NAAS platform API key
- `li_at` (str): LinkedIn authentication cookie
- `JSESSIONID` (str): LinkedIn session cookie  
- `base_url` (str): API base URL (optional, defaults to NAAS platform)

## Error Handling

The integration includes comprehensive error handling:

- **`IntegrationConnectionError`**: Raised when API communication fails
- **Request validation**: LinkedIn URL format validation
- **Authentication errors**: Handles invalid or expired credentials
- **Rate limiting**: Graceful handling of API rate limits

## Security Considerations

- Store API keys and authentication cookies securely in environment variables
- LinkedIn cookies should be rotated regularly for security
- Use HTTPS for all API communications
- Validate all LinkedIn URLs before processing

## Limitations

- Requires valid LinkedIn authentication cookies
- LinkedIn profile access depends on privacy settings
- API rate limits may apply for bulk operations
- Processing time varies based on profile complexity

## Contributing

When contributing to the AIA module:

1. Follow the existing code structure and patterns
2. Add comprehensive tests for new functionality
3. Update documentation for any API changes
4. Ensure proper error handling and validation
5. Test with various LinkedIn profile formats

## License

This module is part of the NAAS ABI platform and follows the project's licensing terms.
