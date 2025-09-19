# Google Search Module

## Description

The Google Search Module provides comprehensive integration with Google's search capabilities for web scraping and data extraction. This module enables:

- Performing Google searches and extracting URLs from search results
- Specialized LinkedIn profile and organization URL extraction
- Pattern-based URL filtering and extraction
- Integration with ontology systems for semantic data management
- LangChain tool integration for AI agent usage
- Pipeline-based processing for structured data workflows

## TL;DR

To get started with the Google Search module:

1. Use the integration classes for basic search functionality
2. Leverage the pipeline for ontology-based data management
3. Run the sandbox examples to test specific use cases

```bash
# Test LinkedIn profile search
uv run python src/custom/modules/google_search/sandbox/GoogleSearchIntegration_search_linkedin_profile_url.py

# Test LinkedIn organization search
uv run python src/custom/modules/google_search/sandbox/GoogleSearchIntegration_search_linkedin_organization_url.py

# Test general URL search
uv run python src/custom/modules/google_search/sandbox/GoogleSearchIntegration_search_url.py
```

## Overview

### Structure

```
src/custom/modules/google_search/
├── integrations/                    # Core integration classes
│   ├── GoogleSearchIntegration.py                    # Basic Google search integration
│   └── GoogleSearchIntegration_test.py               # Integration tests
├── pipelines/                       # Data processing pipelines
│   └── AddGoogleSearchPipeline.py                    # Ontology-based search pipeline
├── sandbox/                         # Example usage scripts
│   ├── GoogleSearchIntegration_search_linkedin_profile_url.py
│   ├── GoogleSearchIntegration_search_linkedin_organization_url.py
│   └── GoogleSearchIntegration_search_url.py
├── ontologies/                      # Semantic data models
│   └── GoogleSearchOntology.ttl                     # RDF ontology for Google search concepts
└── README.md                        # This documentation
```

### Integrations

#### GoogleSearchIntegration
Core integration class that provides:
- `search_google()`: Perform basic Google searches and return URLs
- `search_url()`: Search with pattern-based URL extraction
- `search_linkedin_organization_url()`: Extract LinkedIn company/organization URLs
- `search_linkedin_profile_url()`: Extract LinkedIn profile URLs
- Configurable search parameters (number of results, TLD, pause time)
- LangChain tool integration for AI agent usage

### Pipelines

#### AddGoogleSearchPipeline
Ontology-based pipeline that provides:
- Structured data management for Google search activities
- Integration with triple store services
- Semantic representation of search queries and results
- RDF-based data modeling for search acts and results

### Ontologies

#### GoogleSearchOntology.ttl
RDF ontology that defines:
- `ActofSearchinginGoogle`: Class representing Google search activities
- `hasGoogleSearchResult`: Object property linking searches to results
- `query`: Data property for search queries
- `pattern`: Data property for search patterns
- Semantic relationships between search acts and discovered entities

## Configuration

### Basic Setup

```python
from src.marketplace.applications.google_search.integrations.GoogleSearchIntegration import (
    GoogleSearchIntegration,
    GoogleSearchIntegrationConfiguration
)

# Create configuration
config = GoogleSearchIntegrationConfiguration()

# Initialize integration
integration = GoogleSearchIntegration(config)
```

### Pipeline Configuration

```python
from src.marketplace.applications.google_search.pipelines.AddGoogleSearchPipeline import (
    AddGoogleSearchPipeline,
    AddGoogleSearchPipelineConfiguration
)

# Create pipeline configuration
pipeline_config = AddGoogleSearchPipelineConfiguration(
    triple_store=triple_store_service,
    add_individual_pipeline_configuration=individual_pipeline_config
)

# Initialize pipeline
pipeline = AddGoogleSearchPipeline(pipeline_config)
```

## Usage Examples

### Basic Google Search

```python
# Perform a basic Google search
results = integration.search_google(
    query="Python programming tutorials",
    num=10,
    tld="com"
)

print(results)
```

### LinkedIn Profile Search

```python
# Search for a LinkedIn profile URL
profile_urls = integration.search_linkedin_profile_url(
    profile_name="Florent Ravenel"
)

print(profile_urls)
```

### LinkedIn Organization Search

```python
# Search for a LinkedIn organization URL
org_urls = integration.search_linkedin_organization_url(
    organization_name="Microsoft"
)

print(org_urls)
```

### Pattern-Based URL Search

```python
# Search with custom pattern extraction
urls = integration.search_url(
    query="Python tutorials site:github.com",
    pattern=r"https://github\.com/[^/]+/[^/]+"
)

print(urls)
```

### Using with LangChain Tools

```python
from src.marketplace.applications.google_search.integrations.GoogleSearchIntegration import as_tools

# Convert integration to LangChain tools
tools = as_tools(config)

# Use in LangChain agent
# The tools will be available as:
# - googlesearch_search
# - googlesearch_search_url
# - googlesearch_linkedin_organization
# - googlesearch_linkedin_profile
```

### Ontology Pipeline Usage

```python
# Add a Google search to the ontology
search_uri = pipeline.run(AddGoogleSearchPipelineParameters(
    label="Search for Python tutorials",
    query="Python programming tutorials",
    pattern=r"https://.*\.com",
    result_uri="http://ontology.naas.ai/abi/result_123"
))
```

## API Methods

### GoogleSearchIntegration Methods

#### search_google()
- **Purpose**: Perform basic Google searches
- **Parameters**:
  - `query` (str): Search query
  - `num` (int): Number of results (default: 10)
  - `stop` (int): Stop after N results (default: 10)
  - `tld` (str): Top-level domain (default: "com")
  - `pause` (int): Pause between requests (default: 2)
- **Returns**: Generator of search result URLs

#### search_url()
- **Purpose**: Search with pattern-based URL extraction
- **Parameters**:
  - `query` (str): Search query
  - `pattern` (str, optional): Regex pattern for URL extraction
- **Returns**: List of matching URLs

#### search_linkedin_organization_url()
- **Purpose**: Extract LinkedIn organization URLs
- **Parameters**:
  - `organization_name` (str): Name of the organization
- **Returns**: List of LinkedIn organization URLs

#### search_linkedin_profile_url()
- **Purpose**: Extract LinkedIn profile URLs
- **Parameters**:
  - `profile_name` (str): Name of the profile
- **Returns**: List of LinkedIn profile URLs

### Pipeline Methods

#### AddGoogleSearchPipeline.run()
- **Purpose**: Add search data to ontology
- **Parameters**:
  - `label` (str, optional): Search label
  - `individual_uri` (str, optional): Existing individual URI
  - `query` (str, optional): Search query
  - `pattern` (str, optional): Search pattern
  - `result_uri` (str, optional): Result entity URI
- **Returns**: URI of the created search act

## LangChain Tools

The module provides four LangChain tools:

1. **googlesearch_search**: Basic Google search functionality
2. **googlesearch_search_url**: Pattern-based URL search
3. **googlesearch_linkedin_organization**: LinkedIn organization search
4. **googlesearch_linkedin_profile**: LinkedIn profile search

## Ontology Concepts

### Classes
- **ActofSearchinginGoogle**: Represents a Google search activity as a planned act

### Object Properties
- **hasGoogleSearchResult**: Links a search act to its results
- **isGoogleSearchResultOf**: Inverse property linking results to search acts

### Data Properties
- **query**: The search query string
- **pattern**: The regex pattern used for extraction
- **datetime**: Timestamp of the search activity

## Testing

### Run Integration Tests

```bash
# Test Google Search integration
uv run python -m pytest src/custom/modules/google_search/integrations/GoogleSearchIntegration_test.py
```

### Test Sandbox Examples

```bash
# Test LinkedIn profile search
uv run python src/custom/modules/google_search/sandbox/GoogleSearchIntegration_search_linkedin_profile_url.py

# Test LinkedIn organization search
uv run python src/custom/modules/google_search/sandbox/GoogleSearchIntegration_search_linkedin_organization_url.py

# Test general URL search
uv run python src/custom/modules/google_search/sandbox/GoogleSearchIntegration_search_url.py
```

## Error Handling

The module includes comprehensive error handling:
- Network connection errors
- Invalid search queries
- Pattern matching failures
- Ontology validation errors
- Triple store operation failures

All errors are properly logged and handled gracefully to ensure robust operation.

## Rate Limits and Best Practices

- **Respectful Scraping**: The module includes configurable pause times between requests
- **Pattern Efficiency**: Use specific patterns to reduce unnecessary processing
- **Result Limiting**: Configure appropriate result limits to manage data volume
- **TLD Configuration**: Use appropriate top-level domains for regional searches

## Dependencies

- `googlesearch-python`: Google search functionality
- `pydantic`: Data validation and serialization
- `langchain_core`: Tool integration for AI agents
- `abi.integration`: Base integration framework
- `abi.pipeline`: Pipeline framework
- `rdflib`: RDF data processing
- `fastapi`: API router for pipeline endpoints

## Use Cases

- **LinkedIn Data Extraction**: Find and extract LinkedIn profile and organization URLs
- **Web Scraping**: Collect URLs from Google search results
- **Pattern-Based Extraction**: Extract specific types of URLs using regex patterns
- **Semantic Data Management**: Store and query search activities using ontologies
- **AI Agent Integration**: Provide search capabilities to AI agents via LangChain tools
- **Data Pipeline Processing**: Integrate search results into larger data workflows

## Limitations

- **Google's Terms of Service**: Ensure compliance with Google's usage policies
- **Rate Limiting**: Respect reasonable request rates to avoid blocking
- **Result Accuracy**: Search results may vary based on location, time, and Google's algorithms
- **Pattern Reliability**: Regex patterns may need updates as websites change

## Contributing

When contributing to this module:
1. Follow the existing code structure and patterns
2. Add appropriate tests for new functionality
3. Update the ontology when adding new concepts
4. Document new features in this README
5. Ensure all dependencies are properly declared

