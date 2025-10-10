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
│   └── SanaxAgent.py               # Main agent for LinkedIn Sales Navigator queries
├── pipelines/                     
│   ├── SanaxLinkedInSalesNavigatorExtractorPipeline_test.py          
│   └── SanaxLinkedInSalesNavigatorExtractorPipeline.py           # Data extraction pipeline
├── ontologies/                     
│   └── SanaxLinkedInSalesNavigatorSparqlQueries.ttl              # SPARQL query templates
├── __init__.py                     
└── README.md                       
```

## Core Components

### Agents

#### Sanax Agent
AI agent specialized in extracting and analyzing LinkedIn Sales Navigator data. The agent can:
- Search for people by position title, name, or location
- Look up LinkedIn profile URLs for individuals and companies
- Find company information and employee lists
- Analyze employment relationships and tenure data
- Answer questions about available LinkedIn Sales Navigator data

**Capabilities:**
- Person information queries ("what do you know about John Smith?")
- Company employee searches ("who works at Microsoft?")
- Role-based searches ("who is a Software Engineer?")
- Location-based queries ("who is in Singapore?")
- LinkedIn URL lookups for people and companies
- Employment history and tenure analysis

**Use Cases:**
- Sales prospecting and lead qualification
- Talent acquisition and recruitment
- Market research and competitive analysis
- Network mapping and relationship building

### Pipelines

#### Sanax LinkedIn Sales Navigator Extractor Pipeline
Pipeline for importing LinkedIn Sales Navigator data from Excel files into the triple store. This pipeline:

**Functions:**
- Reads Excel files exported from LinkedIn Sales Navigator
- Extracts person profiles, positions, companies, and locations
- Calculates employment start dates from tenure information
- Creates semantic relationships between entities
- Stores data in RDF triple store format

**Required Excel Columns:**
- `Name`: Person's full name
- `Job Title`: Current position/role
- `Company`: Organization name
- `Company URL`: LinkedIn company page URL
- `Location`: Geographic location
- `Time in Role`: Duration in current position
- `Time in Company`: Total tenure at company
- `LinkedIn URL`: LinkedIn profile URL

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
The agent supports both cloud and local AI models:
- **Cloud**: GPT-4 (default for cloud mode)
- **Local**: Qwen 3.8B (for local deployment)

### Ontologies

#### Sanax LinkedIn Sales Navigator SPARQL Queries

The ontology file (`SanaxLinkedInSalesNavigatorSparqlQueries.ttl`) contains 16 templatable SPARQL queries that enable comprehensive data analysis:

**Person Queries:**
- `get_person_info`: Get comprehensive information about a specific person
- `get_person_linkedin_url`: Get LinkedIn profile URL for a person
- `get_persons_by_name_prefix`: Find people whose names start with a prefix
- `fuzzy_person_search`: Find people with similar names using fuzzy matching
- `smart_person_search`: Smart search with exact and fuzzy fallback

**Company Queries:**
- `get_company_employees`: Find all people working for a specific company
- `get_company_linkedin_url`: Get LinkedIn company page URL
- `count_people_by_company`: Count employees at a specific company
- `fuzzy_company_search`: Find companies with similar names

**Role/Position Queries:**
- `get_role_holders`: Find all people who hold a specific position

**Location Queries:**
- `get_people_by_location`: Find people located in a specific location
- `count_people_by_location`: Count people in a specific location

**Employment Analysis:**
- `get_most_recent_job_starts`: Find people who started jobs most recently
- `get_oldest_job_starts`: Find people with earliest job start dates
- `get_longest_tenure`: Find people with longest employment tenure

Each query supports parameterized inputs and returns structured results for analysis.

## Dependencies

### Python Libraries
- `abi.pipeline`: Base pipeline framework for data processing
- `abi.services.agent`: Agent framework for AI interactions
- `abi.services.triple_store`: Triple store service for RDF data storage
- `langchain_core`: Tool integration for AI agents
- `fastapi`: API router for agent endpoints
- `pydantic`: Data validation and serialization
- `rdflib`: RDF graph manipulation and SPARQL queries
- `pandas`: Data manipulation and Excel file processing
- `uuid`: Unique identifier generation
- `datetime`: Date and time handling

### External Dependencies
- **Sanax Chrome Extension**: Required for exporting LinkedIn Sales Navigator data to Excel format
- **Triple Store Service**: Configured RDF database for storing semantic data
- **Excel Files**: LinkedIn Sales Navigator export files with required column structure

### Data Flow
1. **Export**: Use Sanax Chrome extension to export LinkedIn Sales Navigator search results to Excel
2. **Import**: Pipeline processes Excel files and extracts structured data
3. **Store**: Data is converted to RDF triples and stored in triple store
4. **Query**: Agent uses SPARQL templates to answer user questions about the data