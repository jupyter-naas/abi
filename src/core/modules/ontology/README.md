# Ontology Module

## Overview

### Description

The Ontology Module provides comprehensive support for ontology engineering, knowledge graph management, and semantic data processing based on the Basic Formal Ontology (BFO) framework.

This module enables:
- Named Entity Recognition (NER) with ontology mapping
- SPARQL query generation and execution
- Knowledge graph construction and management
- BFO-compliant ontology engineering
- Semantic data transformation and validation

### Requirements

Dependencies:
- Triple store service for RDF data management
- OpenAI API key for LLM-based entity recognition
- RDFLib for graph operations
- LangChain for agent framework integration

### TL;DR

To get started with the Ontology module:

1. Configure your `OPENAI_API_KEY` in your .env file
2. Set up your triple store service
3. Load base ontologies (BFO, CCO)

Start using ontology agents:
```bash
make chat agent=OntologyEngineerAgent
make chat agent=EntitytoSPARQLAgent
make chat agent=KnowledgeGraphBuilderAgent
```

### Structure

```
src/core/modules/ontology/

├── agents/                         
│   ├── OntologyEngineerAgent.py    # BFO expert agent for ontology engineering
│   ├── OntologyEngineerAgent_test.py               
│   ├── EntitytoSPARQLAgent.py      # Entity extraction to SPARQL conversion
│   ├── EntitytoSPARQLAgent_test.py          
│   ├── KnowledgeGraphBuilderAgent.py # Knowledge graph management
│   └── KnowledgeGraphBuilderAgent_test.py     
├── pipelines/                     
│   ├── InsertDataSPARQLPipeline.py    # SPARQL data insertion
│   ├── AddIndividualPipeline.py       # Individual entity addition
│   ├── MergeIndividualsPipeline.py    # Individual merging operations
│   ├── RemoveIndividualPipeline.py    # Individual removal operations
│   ├── UpdateDataPropertyPipeline.py # Data property updates
│   └── Update*Pipeline.py             # Specialized update pipelines           
├── ontologies/                     
│   ├── top-level/                     # Foundation ontologies (BFO, OWL)
│   ├── mid-level/                     # Middle-level ontologies
│   ├── domain-level/                  # Domain-specific ontologies
│   └── application-level/             # Application-specific ontologies          
├── workflows/                        
│   ├── GetObjectPropertiesFromClassWorkflow.py    # Object property extraction
│   ├── SearchIndividualWorkflow.py               # Individual search
│   ├── GetSubjectGraphWorkflow.py                # Subject graph retrieval
│   ├── ConvertOntologyGraphToYamlWorkflow.py     # Graph to YAML conversion
│   └── Export*Workflow.py                        # Data export workflows               
├── sandbox/                        
│   ├── sparql_insert_data.py          # SPARQL experimentation
│   ├── spacy_entity_extractor.py      # NLP entity extraction
│   └── ontology utilities/            # Development utilities                
├── mappings.py                     # Visual mappings and color schemes
├── triggers.py                     # Event triggers and handlers
└── README.md                       
```

Additional ontology services in `lib/abi/services/ontology/`:
```
lib/abi/services/ontology/
├── OntologyPorts.py                # Service interfaces
├── OntologyService.py              # Core ontology service
└── adaptors/                       
    └── secondary/
        └── OntologyService_SecondaryAdaptor_NERPort.py  # NER implementation
```

## Core Components

The ontology module provides comprehensive tools for semantic knowledge management and ontology engineering.

### Agents

#### Ontology Engineer Agent
Expert BFO (Basic Formal Ontology) specialist that helps users understand ontology concepts and transform natural language text into structured ontological representations.

**Capabilities:**
- Educational guidance on BFO 2.0 ontology principles
- Text-to-ontology transformation
- Entity disambiguation and mapping
- SPARQL INSERT DATA generation with BFO compliance

**Use Cases:**
- Learning ontology engineering concepts
- Converting unstructured text to semantic knowledge
- Building domain-specific ontologies
- Validating ontological representations

#### Entity to SPARQL Agent
Specialized agent for extracting entities from text and transforming them into SPARQL INSERT DATA statements using BFO framework.

**Capabilities:**
- Named Entity Recognition (NER) with ontology mapping
- BFO-compliant entity classification
- Relationship extraction and analysis
- SPARQL statement generation with annotations

**Use Cases:**
- Automated knowledge graph population
- Text mining for semantic data extraction
- Structured data generation from documents
- Entity relationship mapping

#### Knowledge Graph Builder Agent  
Comprehensive knowledge graph management agent for interacting with RDF triplestores and managing ontological instances.

**Capabilities:**
- Search and retrieve ontology classes and individuals
- Add, update, merge, and remove knowledge graph entities
- Execute SPARQL queries and data operations
- Validate and maintain graph integrity

**Use Cases:**
- Knowledge graph construction and maintenance
- Data curation and quality assurance
- Complex query operations
- Graph analytics and exploration

#### Testing
```bash
# Test Ontology Engineer Agent
uv run python -m pytest src/core/modules/ontology/agents/OntologyEngineerAgent_test.py

# Test Entity to SPARQL Agent
uv run python -m pytest src/core/modules/ontology/agents/EntitytoSPARQLAgent_test.py

# Test Knowledge Graph Builder Agent
uv run python -m pytest src/core/modules/ontology/agents/KnowledgeGraphBuilderAgent_test.py
```

### Ontologies

The module includes a comprehensive hierarchy of ontologies organized by abstraction level:

#### Top-Level Ontologies
- **bfo-core.ttl**: Basic Formal Ontology (BFO) 2.0 core concepts
- **owl.ttl**: Web Ontology Language (OWL) definitions

#### Mid-Level Ontologies  
- **AgentOntology.ttl**: Agent and organization concepts
- **EventOntology.ttl**: Temporal events and processes
- **QualityOntology.ttl**: Properties and qualities
- **InformationEntityOntology.ttl**: Information artifacts and content
- **GeospatialOntology.ttl**: Spatial and location concepts
- **TimeOntology.ttl**: Temporal intervals and dates
- **CurrencyUnitOntology.ttl**: Financial and currency units

#### Domain-Level Ontologies
- **PersonOntology.ttl**: Individual person concepts and properties
- **OrganizationOntology.ttl**: Business and institutional entities
- **OfferingOntology.ttl**: Products, services, and market offerings

#### Application-Level Ontologies  
- **FoundryOntology.ttl**: Application-specific foundry concepts
- **LinkedInOntology.ttl**: LinkedIn platform-specific entities
- **DataSourceOntology.ttl**: Data source and integration concepts
- **TemplatableSparqlQueries.ttl**: Reusable SPARQL query templates

### Pipelines

Pipelines provide reusable data processing workflows for knowledge graph operations:

#### Core Pipelines
- **InsertDataSPARQLPipeline**: Execute SPARQL INSERT DATA statements on triplestore
- **AddIndividualPipeline**: Add new individual entities with proper typing
- **MergeIndividualsPipeline**: Combine duplicate individuals while preserving relationships
- **RemoveIndividualPipeline**: Safely delete individuals and clean up references
- **UpdateDataPropertyPipeline**: Modify data properties of existing entities

#### Specialized Update Pipelines
- **UpdatePersonPipeline**: Person-specific property updates
- **UpdateCommercialOrganizationPipeline**: Business entity modifications
- **UpdateWebsitePipeline**: Web presence and URL management
- **UpdateLinkedInPagePipeline**: LinkedIn profile data management

#### Testing
```bash
# Test core pipelines
uv run python -m pytest src/core/modules/ontology/pipelines/InsertDataSPARQLPipeline_test.py
uv run python -m pytest src/core/modules/ontology/pipelines/AddIndividualPipeline_test.py
uv run python -m pytest src/core/modules/ontology/pipelines/MergeIndividualsPipeline_test.py
```

### Workflows

Workflows orchestrate complex multi-step operations across the knowledge graph:

#### Query and Retrieval Workflows
- **SearchIndividualWorkflow**: Advanced individual search with filtering
- **GetSubjectGraphWorkflow**: Comprehensive entity information retrieval  
- **GetObjectPropertiesFromClassWorkflow**: Extract object properties for ontology classes

#### Data Export and Conversion Workflows
- **ExportGraphInstancesToExcelWorkflow**: Generate Excel reports from graph data
- **ConvertOntologyGraphToYamlWorkflow**: Transform RDF graphs to YAML format
- **CreateClassOntologyYamlWorkflow**: Generate class-based YAML ontology representations
- **CreateIndividualOntologyYamlWorkflow**: Export individual-focused YAML structures

#### Testing  
```bash
# Test workflow operations
uv run python -m pytest src/core/modules/ontology/workflows/SearchIndividualWorkflow_test.py
uv run python -m pytest src/core/modules/ontology/workflows/GetSubjectGraphWorkflow_test.py
uv run python -m pytest src/core/modules/ontology/workflows/ExportGraphInstancesToExcelWorkflow_test.py
```

## Dependencies

### Python Libraries
- `abi.services.agent`: Agent framework for intelligent system orchestration
- `abi.services.triple_store`: RDF triplestore integration and management
- `abi.pipeline`: Reusable data processing pipeline framework
- `abi.workflow`: Complex workflow orchestration and execution
- `rdflib`: RDF graph manipulation and SPARQL query processing
- `langchain_core`: Core LangChain components for AI agent tools
- `langchain_openai`: OpenAI language model integration
- `fastapi`: REST API routing for agent endpoints
- `pydantic`: Data validation, serialization, and configuration management
- `pandas`: Data manipulation for export workflows
- `openpyxl`: Excel file generation and processing

### Internal Modules

- `abi.services.ontology`: Core ontology service providing NER capabilities
- `src.utils.SPARQL`: SPARQL utility functions and query helpers
- `src.secret`: Secure credential management for API keys