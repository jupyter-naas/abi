# Sanax Module

## Overview

### Description

The Sanax Module provides comprehensive integration with LinkedIn Sales Navigator data extraction and analysis capabilities. It processes Excel files exported from LinkedIn Sales Navigator using the Sanax Chrome extension and stores the data in a semantic triple store for advanced querying.

This module enables:
- Import LinkedIn Sales Navigator data from Excel files
- Extract person profiles, job positions, and company information
- Store employment relationships and tenure data
- Query people by name, location, company, or position
- Analyze job start dates and employment duration
- Access LinkedIn profile and company page URLs
- Advanced semantic search and fuzzy matching capabilities

### Requirements

No API key required. This module works with:
1. Excel files exported from LinkedIn Sales Navigator using the [Sanax Chrome Extension](https://chromewebstore.google.com/detail/sanax-linkedin-sales-navi/mfagglhpdadnjghfbodblpdhgnekalad)
2. A configured triple store service for data storage

### TL;DR

To get started with the Sanax module:

1. Export LinkedIn Sales Navigator data using the Sanax Chrome extension
2. Save the Excel file to your datastore directory
3. Use the agent to import and query the data

Start chatting using this command:
```bash
make chat agent=SanaxAgent
```

### Structure

```
src/marketplace/applications/sanax/

├── agents/                         
│   ├── SanaxAgent.py               # Main agent for LinkedIn Sales Navigator queries
│   └── SanaxAgent_test.py          # Agent testing with conversational scenarios
├── pipelines/                     
│   ├── SanaxLinkedInSalesNavigatorExtractorPipeline_test.py          
│   └── SanaxLinkedInSalesNavigatorExtractorPipeline.py           # Data extraction pipeline
├── ontologies/                     
│   └── SanaxLinkedInSalesNavigatorSparqlQueries.ttl              # SPARQL query templates
├── models/                         
│   ├── gpt_4_1.py                  # GPT-4.1 cloud model configuration
│   └── qwen3_8b.py                 # Qwen3 8B local model configuration
├── sandbox/                        
│   └── SanaxLinkedInSalesNavigatorExtractorPipeline_run.py       # Example usage script
├── __init__.py                     
└── README.md                       
```

## Core Components

### Agents

#### Sanax Agent
AI agent specialized in extracting and analyzing LinkedIn Sales Navigator data. The agent leverages 12 templatable SPARQL tools for comprehensive data querying and analysis.

**Core Capabilities:**
- **Person Information**: Comprehensive person profiles with employment history
- **Company Analysis**: Employee lists, company information, and LinkedIn URLs
- **Role-Based Search**: Find people by position titles with fuzzy matching
- **Location Queries**: Geographic-based people searches
- **Employment Analysis**: Job start dates, tenure analysis, and career progression
- **Quantitative Analysis**: Count operations for statistical insights

**Available Tools (13 SPARQL Templates + 1 Count Tool):**
1. `sanax_get_information_about_person` - Complete person profiles
2. `sanax_get_company_employees` - Company employee listings
3. `sanax_get_people_holding_position` - Role-based searches
4. `sanax_search_persons_by_name` - Fuzzy name matching
5. `sanax_search_companies_by_name` - Company name searches
6. `sanax_get_persons_by_name_prefix` - Name prefix searches
7. `sanax_get_people_located_in_location` - Location-based queries
8. `sanax_search_locations_by_name` - Location name searches
9. `sanax_list_persons` - Browse all persons (paginated)
10. `sanax_list_companies` - Browse all companies (paginated)
11. `sanax_list_locations` - Browse all locations (paginated)
12. `sanax_get_people_with_most_recent_job_starts` - Recent hires
13. `sanax_get_people_with_oldest_job_starts` - Longest-tenured employees
14. `sanax_get_people_with_longest_tenure` - Tenure analysis
15. `count_items` - Count results from any other tool

**Intent Mapping (32 Natural Language Intents):**
- Person queries: "what do you know about John Smith?", "tell me about {person}"
- Company searches: "who works at Microsoft?", "show me employees at {company}"
- Position searches: "who has the position of CEO?", "find people who are {position}"
- Location queries: "who are the people in Singapore?", "show me people located in {location}"
- Employment analysis: "who started their job most recently?", "show me people with longest tenure"

**Model Support:**
- **Cloud Mode**: GPT-4.1 (1M token context, OpenAI API)
- **Local Mode**: Qwen3 8B (32K context, Ollama local deployment)

**Use Cases:**
- Sales prospecting and lead qualification
- Talent acquisition and recruitment
- Market research and competitive analysis
- Network mapping and relationship building
- Employment trend analysis
- Geographic talent mapping

### Pipelines

#### Sanax LinkedIn Sales Navigator Extractor Pipeline
Advanced pipeline for importing LinkedIn Sales Navigator data from Excel files into a semantic triple store. The pipeline implements sophisticated data processing with temporal analysis and relationship mapping.

**Core Functions:**
- **Excel Processing**: Reads and validates LinkedIn Sales Navigator export files
- **Data Extraction**: Extracts person profiles, positions, companies, and locations
- **Temporal Analysis**: Calculates employment start dates from tenure information
- **Semantic Modeling**: Creates RDF relationships between entities using BFO/CCO ontologies
- **Triple Store Integration**: Stores structured data for advanced querying
- **Data Validation**: Ensures data integrity and handles missing information gracefully

**Required Excel Columns:**
- `Name`: Person's full name (required)
- `Job Title`: Current position/role (required)
- `Company`: Organization name (required)
- `Company URL`: LinkedIn company page URL (optional)
- `Location`: Geographic location (optional)
- `Time in Role`: Duration in current position (e.g., "2 years 3 months")
- `Time in Company`: Total tenure at company (e.g., "5 years")
- `LinkedIn URL`: LinkedIn profile URL (required)

**Advanced Features:**
- **Duration Parsing**: Converts "X years Y months" strings to precise start dates
- **LinkedIn ID Extraction**: Extracts LinkedIn IDs from Sales Navigator URLs
- **Duplicate Prevention**: Uses hash-based deduplication for entities
- **Backing Data Sources**: Tracks data provenance and extraction metadata
- **Employment Relationships**: Creates dual-level employment associations (role-specific and company-level)
- **Error Handling**: Graceful handling of malformed data and missing fields

**Data Model:**
- **Persons**: CCO Person entities with LinkedIn profile associations
- **Organizations**: CCO Organization entities with company page URLs
- **Positions**: BFO Position entities for job titles
- **Locations**: Custom LinkedIn Location entities
- **Employment**: BFO Act of Association entities with temporal data
- **LinkedIn Pages**: Separate entities for profile and company pages

#### Configuration

```python
from src.marketplace.applications.sanax.pipelines.SanaxLinkedInSalesNavigatorExtractorPipeline import (
    SanaxLinkedInSalesNavigatorExtractorPipeline,
    SanaxLinkedInSalesNavigatorExtractorPipelineConfiguration,
    SanaxLinkedInSalesNavigatorExtractorPipelineParameters
)
from src import services

# Create configuration
config = SanaxLinkedInSalesNavigatorExtractorPipelineConfiguration(
    triple_store=services.triple_store_service
)

# Initialize pipeline
pipeline = SanaxLinkedInSalesNavigatorExtractorPipeline(config)
```

#### Run
```bash
# Import Excel file through agent conversation
make chat agent=SanaxAgent
# Then use: "Import LinkedIn data from [file_path]"
```

#### Testing
```bash
uv run python -m pytest src/marketplace/applications/sanax/pipelines/SanaxLinkedInSalesNavigatorExtractorPipeline_test.py
```

### Models

The Sanax agent supports both cloud and local AI models with automatic selection based on configuration:

#### Cloud Model (GPT-4.1)
- **Model**: GPT-4.1 via OpenAI API
- **Context Window**: 1,047,576 tokens (1M+)
- **Features**: Instruction following, tool calling, broad domain knowledge
- **Latency**: Low latency without reasoning step
- **Configuration**: `AI_MODE=cloud` (default)

#### Local Model (Qwen3 8B)
- **Model**: Qwen3 8B via Ollama
- **Context Window**: 32,768 tokens
- **Features**: Privacy-focused, local deployment
- **Temperature**: 0.7 (optimized for stability)
- **Configuration**: `AI_MODE=local`

**Model Selection Logic:**
```python
# Automatic model selection based on AI_MODE
ai_mode = secret.get("AI_MODE")  # Default to cloud if not set
if ai_mode == "cloud":
    selected_model = gpt_4_1.model
else:
    selected_model = qwen3_8b.model
```

### Ontologies

#### Sanax LinkedIn Sales Navigator SPARQL Queries

The ontology file (`SanaxLinkedInSalesNavigatorSparqlQueries.ttl`) contains 14 comprehensive templatable SPARQL queries that enable advanced data analysis with fuzzy matching and similarity scoring:

**Person Queries (4 queries):**
- `sanax_get_information_about_person`: Complete person profiles with employment history
- `sanax_search_persons_by_name`: Fuzzy name matching with similarity scoring (0.0-1.0)
- `sanax_get_persons_by_name_prefix`: Name prefix searches for autocomplete functionality
- `sanax_list_persons`: Browse all persons with pagination (50 limit)

**Company Queries (3 queries):**
- `sanax_get_company_employees`: Employee listings for specific companies
- `sanax_search_companies_by_name`: Fuzzy company name matching with similarity scoring
- `sanax_list_companies`: Browse all companies with pagination (50 limit)

**Role/Position Queries (1 query):**
- `sanax_get_people_holding_position`: Position-based searches with perfect/partial matching

**Location Queries (3 queries):**
- `sanax_get_people_located_in_location`: Location-based people searches
- `sanax_search_locations_by_name`: Location name fuzzy matching
- `sanax_list_locations`: Browse all locations (50 limit)

**Employment Analysis Queries (3 queries):**
- `sanax_get_people_with_most_recent_job_starts`: Recent hires with optional company/location filters
- `sanax_get_people_with_oldest_job_starts`: Longest-tenured employees with filters
- `sanax_get_people_with_longest_tenure`: Tenure analysis with company/location filtering

**Advanced Features:**
- **Fuzzy Matching**: Similarity scoring for names, companies, and locations
- **Parameterized Queries**: Template-based queries with argument validation
- **Filtering Support**: Optional company and location filters for employment queries
- **Pagination**: Built-in limits for large result sets
- **Temporal Analysis**: Start date ordering and tenure calculations
- **LinkedIn Integration**: Automatic URL extraction and profile linking

**Query Arguments:**
- `name_prefix`: Name prefix for autocomplete (e.g., "John")
- `person_name`: Full person name with validation pattern
- `position_title`: Job title/position name
- `company_name`: Company name (optional for filtering)
- `location_name`: Location name (optional for filtering)
- `search_term`: General search term for fuzzy matching
- `limit`: Result count limit (integer validation)

## Dependencies

### Python Libraries
- `abi.pipeline`: Base pipeline framework for data processing
- `abi.services.agent`: Agent framework for AI interactions
- `abi.services.triple_store`: Triple store service for RDF data storage
- `langchain_core`: Tool integration for AI agents
- `langchain_openai`: OpenAI GPT-4.1 integration
- `langchain_ollama`: Ollama local model integration
- `fastapi`: API router for agent endpoints
- `pydantic`: Data validation and serialization
- `rdflib`: RDF graph manipulation and SPARQL queries
- `pandas`: Data manipulation and Excel file processing
- `uuid`: Unique identifier generation
- `datetime`: Date and time handling
- `pytest`: Testing framework

### External Dependencies
- **Sanax Chrome Extension**: Required for exporting LinkedIn Sales Navigator data to Excel format
- **Triple Store Service**: Configured RDF database for storing semantic data
- **Excel Files**: LinkedIn Sales Navigator export files with required column structure
- **OpenAI API**: For cloud model access (GPT-4.1)
- **Ollama**: For local model deployment (Qwen3 8B)

### Data Flow
1. **Export**: Use Sanax Chrome extension to export LinkedIn Sales Navigator search results to Excel
2. **Import**: Pipeline processes Excel files and extracts structured data
3. **Store**: Data is converted to RDF triples and stored in triple store
4. **Query**: Agent uses SPARQL templates to answer user questions about the data

## Testing

### Agent Testing
The module includes comprehensive agent testing with realistic conversational scenarios:

```bash
# Run agent tests
uv run python -m pytest src/marketplace/applications/sanax/agents/SanaxAgent_test.py
```

**Agent Test Coverage:**
- **Person Listing**: "List all people in the database" - validates all 10 test profiles
- **Location Queries**: "Where is Emma Wilson located?" - tests location retrieval
- **Company Queries**: "Where does Maria Garcia work?" - tests employment relationships
- **Role Queries**: "What is Emma Wilson's role?" - tests position information
- **Person Details**: "Tell me about Maria Garcia" - tests comprehensive person profiles

**Test Scenarios:**
- **Location Testing**: Validates Berlin, Germany and San Francisco locations
- **Company Testing**: Tests Global Ventures, Tech Solutions company associations
- **Role Testing**: Validates Product Manager, Solutions Architect positions
- **Comprehensive Profiles**: Tests complete person information retrieval

**Test Data Integration:**
- Agent tests automatically run pipeline tests first to populate test data
- Uses the same 10 realistic LinkedIn profiles as pipeline tests
- Validates end-to-end functionality from data import to agent querying

### Pipeline Testing
The module includes comprehensive test coverage with realistic test data:

```bash
# Run pipeline tests
uv run python -m pytest src/marketplace/applications/sanax/pipelines/SanaxLinkedInSalesNavigatorExtractorPipeline_test.py
```

**Test Coverage:**
- **Data Validation**: Required column validation and error handling
- **Excel Processing**: File reading from both storage and local paths
- **Entity Creation**: Person, company, position, and location entity generation
- **Relationship Mapping**: Employment associations and LinkedIn page linking
- **Temporal Analysis**: Duration parsing and start date calculations
- **Graph Generation**: RDF triple creation and validation

**Test Data:**
- 10 realistic LinkedIn profiles with diverse roles and companies
- Various tenure patterns (1-7 years)
- Multiple locations (US, UK, Singapore, Canada, Germany, South Korea, Australia, Spain)
- Mixed company URL availability
- Different job titles (CEO, CTO, VP, Director, Manager, Developer, etc.)

### Sandbox Examples
The `sandbox/` directory contains example usage scripts for development and testing:

```python
# Example: SanaxLinkedInSalesNavigatorExtractorPipeline_run.py
# Demonstrates basic pipeline usage with sample data
```

## Architecture

### Agent Architecture
- **IntentAgent Base**: Inherits from ABI's IntentAgent framework
- **Tool Integration**: 12 templatable SPARQL tools + 1 count tool
- **Intent Mapping**: 32 natural language intents for conversational queries
- **Model Abstraction**: Automatic cloud/local model selection
- **Memory Management**: Thread-based conversation state

### Pipeline Architecture
- **Configuration-Driven**: Flexible configuration with triple store integration
- **Data Validation**: Multi-layer validation (file existence, column structure, data integrity)
- **Entity Deduplication**: Hash-based unique identifier system
- **Provenance Tracking**: Complete data lineage and extraction metadata
- **Error Resilience**: Graceful handling of malformed data and missing fields

### Data Model Architecture
- **Ontology-Based**: Uses BFO (Basic Formal Ontology) and CCO (Common Core Ontologies)
- **Semantic Relationships**: Rich relationship modeling between entities
- **Temporal Modeling**: Precise employment timeline tracking
- **LinkedIn Integration**: Separate entities for profile and company pages
- **Extensible Design**: Easy addition of new entity types and relationships