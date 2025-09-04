# LinkedIn Module

A comprehensive LinkedIn integration module that provides authenticated access to LinkedIn's professional networking platform through AI-powered agents and robust API integrations.

## Overview

The LinkedIn Module enables seamless extraction, analysis, and processing of LinkedIn data including organization information, professional profiles, post engagement metrics, and social media insights. Built with enterprise-grade security and caching mechanisms, it transforms raw LinkedIn data into LLM-friendly structured formats for AI-powered analysis.

### Key Capabilities

- **🏢 Organization Intelligence**: Extract comprehensive company information, metrics, and metadata from LinkedIn company pages
- **👤 Profile Analysis**: Access detailed profile information including experience, education, skills, and professional connections  
- **📊 Engagement Analytics**: Analyze post performance metrics, comments, reactions, and social engagement patterns
- **🔍 Smart Discovery**: Find LinkedIn profiles and organizations through intelligent Google search integration
- **🧹 Data Processing**: Transform raw LinkedIn data into clean, structured formats optimized for AI consumption
- **⚡ Caching & Performance**: Built-in caching system for optimized API efficiency and faster response times

## Quick Start

### Prerequisites

**Authentication Setup**: Obtain LinkedIn authentication cookies from your browser or Naas Chrome Extension.

Configure your environment variables in `.env`:
```bash
li_at=your_li_at_cookie_here
JSESSIONID=your_jsessionid_cookie_here
LINKEDIN_PROFILE_URL=https://www.linkedin.com/in/your-profile-id/
```

### Usage

Start an interactive chat session with the LinkedIn agent:
```bash
make chat agent=LinkedInAgent
```

Or use the integration directly in your code:
```python
from src.marketplace.modules.applications.linkedin.integrations.LinkedInIntegration import (
    LinkedInIntegration,
    LinkedInIntegrationConfiguration
)

# Initialize integration
config = LinkedInIntegrationConfiguration(
    li_at="your_li_at_cookie_here",
    JSESSIONID="your_jsessionid_cookie_here"
)
integration = LinkedInIntegration(config)

# Extract company information
company_data = integration.get_organization_info("https://www.linkedin.com/company/naas-ai/")
```

## Architecture

### Module Structure

```
src/marketplace/modules/applications/linkedin/
├── __init__.py                     # Module initialization and requirements
├── agents/                         # AI agents for LinkedIn interactions
│   ├── LinkedInAgent.py           # Main LinkedIn AI agent
│   └── LinkedInAgent_test.py      # Agent integration tests
├── integrations/                   # Core LinkedIn API integrations
│   ├── LinkedInIntegration.py     # Primary integration client
│   └── LinkedInIntegration_test.py # Integration tests
├── ontologies/                     # Semantic data models
│   └── LinkedInOntology.ttl       # LinkedIn ontology definitions
└── README.md                       # This documentation
```

## Core Components

### 🤖 LinkedIn Agent

An AI-powered conversational agent that provides natural language access to LinkedIn data through authenticated API calls.

**Primary Features:**
- Intelligent LinkedIn URL discovery via Google search
- Multi-modal data extraction (profiles, organizations, posts)
- Automated data cleaning and LLM optimization
- Real-time engagement analytics
- Professional networking insights

**Supported Operations:**
```bash
# Search for LinkedIn URLs
"Find Microsoft's LinkedIn page"
"Search for John Doe on LinkedIn"

# Profile analysis
"Analyze https://www.linkedin.com/in/florent-ravenel/"
"What are the skills of this profile?"

# Organization insights
"Get information about https://www.linkedin.com/company/naas-ai/"
"What does this company do?"

# Post analytics
"Analyze engagement for this LinkedIn post"
"Who commented on this post?"
```

#### Available Tools

| Tool | Description | Usage |
|------|-------------|-------|
| `linkedin_get_organization_info` | Extract comprehensive company data | Organization analysis, competitive research |
| `linkedin_get_profile_id` | Get LinkedIn unique profile ID (starts with AcoAA) | Profile identification, API calls |
| `linkedin_get_profile_view` | Retrieve detailed profile information | Professional background analysis |
| `linkedin_get_profile_skills` | Get profile skills and endorsements | Skills assessment, talent matching |
| `linkedin_get_profile_network_info` | Access network and connection data | Network analysis, relationship mapping |
| `linkedin_get_profile_posts_feed` | Fetch user's recent posts | Content analysis, thought leadership tracking |
| `linkedin_get_post_stats` | Extract post performance metrics | Engagement analysis, content optimization |
| `linkedin_get_post_comments` | Retrieve all post comments | Sentiment analysis, audience insights |
| `linkedin_get_post_reactions` | Get post reactions and likes | Engagement patterns, content resonance |
| `googlesearch_linkedin_organization` | Find company LinkedIn URLs (via Google Search) | Organization discovery |
| `googlesearch_linkedin_profile` | Find personal LinkedIn URLs (via Google Search) | Profile discovery |

#### Testing

Execute comprehensive agent tests:
```bash
uv run python -m pytest src/marketplace/modules/applications/linkedin/agents/LinkedInAgent_test.py -v
```

**Test Coverage:**
- LinkedIn URL discovery by name (person/organization)
- Profile view data extraction and validation
- Organization information retrieval
- Engagement metrics analysis and processing

### 🔧 LinkedIn Integration

Core integration providing authenticated access to LinkedIn's internal APIs through secure cookie-based authentication.

#### Key Methods

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `get_organization_info(linkedin_url)` | Company/school/showcase URL | Organization data | Comprehensive company information |
| `get_profile_id(linkedin_url)` | Profile URL | Profile ID string | LinkedIn unique profile ID (starts with AcoAA) |
| `get_profile_public_id(linkedin_url)` | Profile URL | Public ID string | LinkedIn public profile identifier |
| `get_profile_view(linkedin_url)` | Profile URL | Profile data | Detailed profile with experience/education |
| `get_profile_skills(linkedin_url)` | Profile URL | Skills data | Professional skills and endorsements |
| `get_profile_network_info(linkedin_url)` | Profile URL | Network data | Connection and network information |
| `get_profile_posts_feed(profile_id, count)` | Profile ID, post count | Posts data | Recent posts from profile |
| `get_post_stats(linkedin_url)` | Post URL | Analytics data | Post performance metrics |
| `get_post_comments(linkedin_url)` | Post URL | Comments data | All comments and replies |
| `get_post_reactions(linkedin_url)` | Post URL | Reactions data | Likes, celebrates, supports, etc. |
| `clean_json(data)` | Raw JSON data | Cleaned data | LLM-optimized data structure |

#### Configuration

```python
from src.marketplace.modules.applications.linkedin.integrations.LinkedInIntegration import (
    LinkedInIntegration,
    LinkedInIntegrationConfiguration
)

# Configure integration
config = LinkedInIntegrationConfiguration(
    li_at="your_li_at_cookie_here",
    JSESSIONID="your_jsessionid_cookie_here",
    base_url="https://www.linkedin.com/voyager/api",
    use_cache=True
)

# Initialize client
integration = LinkedInIntegration(config)

# Extract data
data = integration.get_organization_info("https://www.linkedin.com/company/microsoft/")
cleaned_data = integration.clean_json(data)
```

#### Testing

Run integration tests to verify API connectivity:
```bash
uv run python -m pytest src/marketplace/modules/applications/linkedin/integrations/LinkedInIntegration_test.py -v
```

**Test Coverage:**
- Organization information extraction
- Profile data retrieval (view, skills, network)
- Post analytics (stats, comments, reactions)
- Data cleaning and validation
- Authentication and error handling

### 🧠 Semantic Ontology

Comprehensive semantic model defining LinkedIn-specific concepts, relationships, and data structures for knowledge graph operations.

#### Core Classes

| Class | Description | Example |
|-------|-------------|---------|
| `linkedin:Page` | Base LinkedIn page representation | Any LinkedIn page |
| `linkedin:ProfilePage` | Personal LinkedIn profiles | Professional individual profiles |
| `linkedin:CompanyPage` | Organization pages | Company/business pages |
| `linkedin:SchoolPage` | Educational institution pages | Universities, schools |
| `linkedin:Profile` | Profile data container | User profile information |
| `linkedin:Position` | Job positions and roles | Work experience entries |
| `linkedin:Education` | Educational background | Degrees, certifications |
| `linkedin:Skill` | Professional skills | Technical and soft skills |
| `linkedin:FollowingInfo` | Social following data | Follower counts, relationships |

#### SPARQL Queries

Pre-built semantic queries for LinkedIn data analysis:

```sparql
# Search LinkedIn posts by topic
PREFIX abi: <http://ontology.naas.ai/abi/>
SELECT DISTINCT ?post ?title ?content ?published_date ?engagements
WHERE {
    ?post a abi:LinkedInPost ;
          abi:title ?title ;
          abi:content ?content ;
          abi:published_date ?published_date ;
          abi:engagements ?engagements .
    FILTER(CONTAINS(LCASE(?content), LCASE("AI")))
}
ORDER BY DESC(?published_date)
```

## Data Storage & Caching

LinkedIn data is automatically cached and organized in a structured hierarchy:

```
storage/datastore/linkedin/
├── cleaned_json/                   # Processed, LLM-ready data
│   └── {profile_id}/
│       └── {entity_type}.json
├── get_organization_info/          # Company data cache
│   └── {org_id}/
│       ├── {org_id}.json
│       ├── data/
│       └── included/
├── get_profile_view/               # Profile data cache
├── get_profile_skills/             # Skills data cache
├── get_profile_network_info/       # Network data cache
├── get_profile_posts_feed/         # Posts feed cache
├── get_post_stats/                 # Post analytics cache
├── get_post_comments/              # Comments data cache
└── get_post_reactions/             # Reactions data cache
```

### Cache Features

- **TTL Management**: 7-day default cache expiration
- **Automatic Cleanup**: Intelligent cache invalidation
- **Structured Storage**: Hierarchical organization by data type
- **Image Processing**: Automatic image URL extraction and storage
- **Compression**: Optimized storage for large datasets

## Security & Compliance

### Authentication
- **Cookie-based Security**: Uses `li_at` and `JSESSIONID` for secure API access
- **Session Management**: Automatic session validation and renewal
- **Credential Protection**: Secure storage of authentication tokens

### Rate Limiting & Ethics
- **Respectful Usage**: Implements appropriate delays between requests
- **LinkedIn ToS Compliance**: Adheres to LinkedIn's data usage policies
- **Professional Standards**: Maintains professional tone and respects privacy

### Data Protection
- **Local Storage**: All cached data stored locally with access controls
- **Privacy Respect**: Honors LinkedIn user privacy settings
- **GDPR Compliance**: Supports data deletion and privacy requests

## Dependencies & Requirements

### Core Dependencies
```python
# Integration framework
abi.integration                    # Base integration framework
abi.services.agent                # AI agent framework
abi.services.cache                # Caching system

# AI & Language Processing
langchain_core                    # Tool integration for AI agents
langchain_openai                  # OpenAI integration for NLP

# Web & API
fastapi                          # API router for agent endpoints
requests                         # HTTP client for LinkedIn API calls
urllib.parse                     # URL parsing and manipulation

# Data Processing
pydantic                         # Data validation and serialization
pydash                          # Data manipulation utilities
```

### External Modules
- `google_search` module: LinkedIn URL discovery through Google search integration
- `abi.services.cache`: Data persistence and caching layer
- `src.secret`: Secure credential management
- `src.utils.Storage`: File storage utilities for cached data

### AI Models
- **Primary Model**: GPT-4o for natural language processing
- **Temperature**: 0 (deterministic responses)
- **Use Case**: Data analysis, insight generation, conversational AI

## Use Cases & Applications

### 🏢 Enterprise Applications
- **Competitive Intelligence**: Monitor competitor activity and positioning
- **Lead Generation**: Identify and research potential customers
- **Talent Acquisition**: Source and evaluate candidates
- **Market Research**: Analyze industry trends and insights
- **Brand Monitoring**: Track company reputation and engagement

### 👤 Personal AI Applications
- **Network Analysis**: Understand professional connections and relationships
- **Content Strategy**: Optimize LinkedIn content for engagement
- **Career Development**: Track industry trends and skill requirements
- **Personal Branding**: Monitor personal profile performance
- **Opportunity Discovery**: Find relevant job opportunities and connections

### 📊 Analytics & Insights
- **Engagement Optimization**: Analyze post performance patterns
- **Audience Analysis**: Understand follower demographics and behavior
- **Content Intelligence**: Identify trending topics and content formats
- **Influence Mapping**: Track thought leadership and industry influence
- **Performance Benchmarking**: Compare metrics against industry standards

## Development & Contributing

### Development Environment

1. **Setup Development Environment**:
   ```bash
   # Install dependencies
   pip install -r requirements.txt
   
   # Configure environment
   cp .env.example .env
   # Edit .env with your LinkedIn credentials
   ```

2. **Run Tests**:
   ```bash
   # Run all tests
   uv run python -m pytest src/marketplace/modules/applications/linkedin/ -v
   
   # Run specific test suite
   uv run python -m pytest src/marketplace/modules/applications/linkedin/agents/ -v
   uv run python -m pytest src/marketplace/modules/applications/linkedin/integrations/ -v
   ```

### Contributing Guidelines

1. **Code Quality**: Follow PEP 8 style guidelines
2. **Testing**: Ensure comprehensive test coverage
3. **Documentation**: Update documentation for new features
4. **Security**: Respect LinkedIn's terms of service and user privacy

## Support & Resources

### Getting Help
- **Documentation**: Comprehensive inline code documentation
- **Issues**: Report bugs or request features via the issue tracker
- **Support**: Contact `support@naas.ai` for enterprise support

### Resources
- [LinkedIn API Documentation](https://docs.microsoft.com/en-us/linkedin/)
- [LangChain Documentation](https://python.langchain.com/)
- [Semantic Web Technologies](https://www.w3.org/standards/semanticweb/)

---

*Last Updated: December 2024*
*Module Version: 2.0*
*Compatibility: Python 3.8+*