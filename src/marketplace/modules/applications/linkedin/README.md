# LinkedIn Module

## Overview

### Description

The LinkedIn Module provides comprehensive integration with LinkedIn's professional networking platform through authenticated API access. This module enables users to extract, analyze, and process LinkedIn data including organization information, professional profiles, posts engagement metrics, and social media insights.

This module enables:
- **Organization Data Extraction**: Retrieve comprehensive company information, metrics, and metadata from LinkedIn company pages
- **Profile Analysis**: Access detailed profile information including experience, education, and professional connections
- **Post Engagement Analytics**: Analyze post performance metrics, comments, reactions, and social engagement
- **Google Search Integration**: Find LinkedIn profiles and organizations through intelligent Google search
- **Data Cleaning & Processing**: Transform raw LinkedIn data into LLM-friendly structured formats

### Requirements

API Key Setup:
Obtain LinkedIn authentication cookies from your Naas Chrome Extension or Configure your environment variables in your `.env` file:
```bash
LINKEDIN_LI_AT=your_li_at_cookie_here
LINKEDIN_JSESSIONID=your_jsessionid_cookie_here
```

### TL;DR

To get started with the LinkedIn module:

1. Obtain LinkedIn authentication cookies from your browser
2. Configure your `LINKEDIN_LI_AT` and `LINKEDIN_JSESSIONID` in your `.env` file

Start chatting using this command:
```bash
make chat agent=LinkedInAgent
```

### Structure

```
src/marketplace/modules/applications/linkedin/
├── agents/                         
│   ├── LinkedInAgent_test.py               
│   └── LinkedInAgent.py          
├── integrations/                    
│   ├── LinkedInIntegration_test.py          
│   └── LinkedInIntegration.py     
├── ontologies/                     
│   └── LinkedInOntology.ttl          
└── README.md                       
```

## Core Components

### Agents

#### LinkedIn Agent
A specialized AI agent for LinkedIn data extraction, analysis, and professional networking insights. The agent provides natural language interface to LinkedIn's data through authenticated API access.

**Capabilities:**
- LinkedIn URL discovery through Google search
- Organization and profile data extraction
- Post analytics and engagement metrics analysis
- Data cleaning and transformation for LLM consumption
- Professional networking insights and business intelligence

**Command:**
```bash
make chat agent=LinkedInAgent
```

**Use Cases:**
- Company research and competitive analysis
- Professional profile analysis
- Social media engagement tracking
- Lead generation and prospect research
- Content performance analysis

#### Testing
Run comprehensive tests for LinkedIn agent functionality:
```bash
uv run python -m pytest src/marketplace/modules/applications/linkedin/agents/LinkedInAgent_test.py
```

Test descriptions:
- Search person LinkedIn URL by name
- Search organization LinkedIn URL by name
- Get LinkedIn profile view data
- Get LinkedIn organization information
- Extract and analyze engagement metrics

### Integrations

#### LinkedIn Integration
Core integration providing authenticated access to LinkedIn's internal APIs through cookie-based authentication.

**Functions:**
- `get_organization_info()`: Retrieve comprehensive company information
- `get_profile_view()`: Access detailed profile data including experience and education
- `get_profile_top_card()`: Get profile summary information
- `get_post_stats()`: Extract post performance metrics
- `get_post_comments()`: Retrieve all comments and replies for posts
- `get_post_reactions()`: Get reactions (likes, celebrates, supports, etc.)
- `clean_json()`: Transform raw LinkedIn data into LLM-friendly format

##### Configuration

```python
from src.marketplace.modules.applications.linkedin.integrations.LinkedInIntegration import (
    LinkedInIntegration,
    LinkedInIntegrationConfiguration
)

# Create configuration
config = LinkedInIntegrationConfiguration(
    li_at="your_li_at_cookie_here",
    JSESSIONID="your_jsessionid_cookie_here"
)

# Initialize integration
integration = LinkedInIntegration(config)
```

#### Run
Execute LinkedIn data extraction with the following parameters:
```bash
# Get organization information
integration.get_organization_info("https://www.linkedin.com/company/naas-ai/")

# Get profile view
integration.get_profile_view("https://www.linkedin.com/in/florent-ravenel/")

# Get post analytics
integration.get_post_stats("https://www.linkedin.com/feed/update/urn:li:activity:1234567890")
```

Required parameters:
- `linkedin_url`: Valid LinkedIn URL (organization, profile, or post)
- Authentication cookies: `li_at` and `JSESSIONID`

#### Testing
Run integration tests to verify API connectivity and data extraction:
```bash
uv run python -m pytest src/marketplace/modules/applications/linkedin/integrations/LinkedInIntegration_test.py
```

### Models
The LinkedIn module uses the following AI models:
- **GPT-4o**: Primary model for natural language processing and data analysis
- **Temperature**: 0 (deterministic responses for consistent data extraction)

### Ontologies

#### LinkedIn Ontology

Semantic ontology defining LinkedIn-specific concepts, relationships, and data structures used in the knowledge graph. The ontology extends the ABI core ontology with LinkedIn-specific classes and properties.

**Key Classes:**
- `linkedin:Page`: LinkedIn page representation
- `abi:SocialPage`: Generic social media page concept
- Organization and profile-specific classes
- Post and engagement entities

#### LinkedIn SPARQL Queries

Turtle file storing SPARQL queries for semantic data retrieval and knowledge graph operations:
- Profile relationship queries
- Organization hierarchy analysis
- Engagement pattern discovery
- Social network analysis queries

### Workflows
Integration with workflow orchestration system for automated LinkedIn data processing pipelines.

## Dependencies

### Python Libraries
- `abi.integration`: Base integration framework for external service communication
- `abi.services.agent`: Agent framework for AI-powered LinkedIn interactions
- `langchain_core`: Tool integration for AI agents and structured data processing
- `langchain_openai`: LangChain OpenAI integration for natural language processing
- `fastapi`: API router for agent endpoints and web service integration
- `pydantic`: Data validation and serialization for LinkedIn API responses
- `requests`: HTTP client for LinkedIn API calls and data retrieval
- `urllib.parse`: URL parsing and manipulation for LinkedIn URL processing
- `pydash`: Utility library for data manipulation and transformation

### Modules

- `google_search`: Integration for finding LinkedIn URLs through Google search
- `storage`: Data persistence and caching layer for LinkedIn data
- `cache`: Caching framework for optimizing API call efficiency

## Available Tools

The LinkedIn module provides the following LangChain tools:

1. **`linkedin_get_organization_info`**: Get comprehensive company information including details, metrics, and metadata
2. **`linkedin_get_profile_view`**: Get detailed profile view data including experience, education, and connections
3. **`linkedin_get_post_stats`**: Get post performance metrics (views, likes, shares, comments count)
4. **`linkedin_get_post_comments`**: Get all comments and replies for a specific post
5. **`linkedin_get_post_reactions`**: Get all reactions (likes, celebrates, supports, etc.) for a specific post
6. **`googlesearch_linkedin_organization`**: Search Google for a LinkedIn organization URL
7. **`googlesearch_linkedin_profile`**: Search Google for a LinkedIn profile URL

## Data Storage

LinkedIn data is automatically cached and stored in the following structure:
```
storage/datastore/linkedin/
├── cleaned_json/           # Processed, LLM-friendly data
├── get_profile_view/       # Profile data cache
├── get_organization_info/  # Organization data cache
├── get_post_stats/        # Post analytics cache
├── get_post_reactions/    # Reactions data cache
├── get_post_comments/     # Comments data cache
└── get_profile_top_card/  # Profile summary cache
```

## Security & Authentication

- **Cookie-based Authentication**: Uses `li_at` and `JSESSIONID` cookies for secure API access
- **Rate Limiting**: Respects LinkedIn's data usage policies and implements appropriate delays
- **Data Privacy**: Maintains professional tone and respects user privacy settings
- **Secure Storage**: Cached data is stored locally with appropriate access controls
