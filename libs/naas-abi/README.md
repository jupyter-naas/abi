# naas-abi

Multi-agent orchestrator and knowledge graph management system for AI orchestration, providing comprehensive coordination of specialized AI agents and semantic data management capabilities.

## Overview

`naas-abi` is the central coordination hub for the ABI (Agentic Brain Infrastructure) ecosystem. It provides:

- **Multi-Agent Orchestration**: Central coordinator managing specialized AI agents (ChatGPT, Claude, Mistral, Gemini, Grok, Llama, Perplexity, Qwen, DeepSeek, Gemma)
- **Knowledge Graph Operations**: Complete CRUD operations for semantic data management
- **Ontology Engineering**: BFO-compliant entity extraction and SPARQL generation
- **Intelligent Routing**: Weighted decision hierarchy with context preservation
- **Multilingual Support**: Native French/English interactions with cultural awareness
- **Production Integration**: Event-driven triggers and YAML ontology publishing

## Installation

```bash
pip install naas-abi
```

## Core Components

### ABIModule

The `ABIModule` is the main module that orchestrates the entire ABI system. It automatically loads marketplace modules (AI agents, applications, domain experts) and provides the core infrastructure.

**Configuration:**

```yaml
modules:
  - module: naas_abi
    enabled: true
    config:
      datastore_path: "abi"
      workspace_id: "{{ secret.WORKSPACE_ID }}"
      storage_name: "{{ secret.STORAGE_NAME }}"
```

**Dependencies:**

The module automatically loads marketplace modules as soft dependencies (optional):
- AI Agents: ChatGPT, Claude, Mistral, Gemini, Grok, Llama, Perplexity, Qwen, DeepSeek, Gemma
- Applications: GitHub, LinkedIn, Google services, and 50+ other integrations
- Domain Experts: Support, Software Engineering, Data Analysis, and more

**Required Services:**
- `Secret`: For credential management
- `TripleStoreService`: For knowledge graph operations
- `ObjectStorageService`: For file storage

### Agents

#### AbiAgent

The main multi-agent orchestrator that coordinates specialized agents.

**Features:**
- Intelligent routing based on request type and context
- Context preservation across conversations
- Multilingual support (French/English)
- Weighted decision hierarchy for optimal agent selection
- Strategic advisory capabilities

**Usage:**

```python
from naas_abi.agents.AbiAgent import create_agent

agent = create_agent()
response = agent.invoke("Route this to the best AI for code generation")
```

**Routing Priorities:**
- Context Preservation (0.99): Maintains active conversations
- Identity/Strategic (0.95): Direct Abi responses
- Web Search (0.90): Routes to Perplexity/ChatGPT
- Creative/Multimodal (0.85): Routes to Gemini
- Truth Seeking (0.80): Routes to Grok
- Advanced Reasoning (0.75): Routes to Claude
- Code & Math (0.70): Routes to Mistral
- Knowledge Graph (0.68): Opens KG Explorer
- Internal Knowledge (0.65): Uses ontology agent
- Platform Operations (0.45): Routes to Naas agent
- Issue Management (0.25): Routes to Support agent

#### EntitytoSPARQLAgent

Extracts entities from natural language and generates SPARQL queries.

**Capabilities:**
- BFO-compliant entity extraction
- Automatic SPARQL query generation
- Entity relationship mapping
- Ontology-aware query construction

**Usage:**

```python
from naas_abi.agents.EntitytoSPARQLAgent import create_agent

agent = create_agent()
response = agent.invoke(
    "Extract entities from: 'John works at Microsoft as a software engineer'"
)
```

#### KnowledgeGraphBuilderAgent

Provides complete CRUD operations for the knowledge graph.

**Capabilities:**
- Add individuals (entities) to the knowledge graph
- Update properties and relationships
- Remove individuals
- Merge duplicate entities
- Query and explore the graph

**Usage:**

```python
from naas_abi.agents.KnowledgeGraphBuilderAgent import create_agent

agent = create_agent()
response = agent.invoke(
    "Add a new organization called 'NaasAI' to the knowledge graph"
)
```

#### OntologyEngineerAgent

Specialized agent for BFO ontology engineering and management.

**Capabilities:**
- Ontology creation and modification
- BFO-compliant structure validation
- Class and property definition
- Ontology publishing to YAML

**Usage:**

```python
from naas_abi.agents.OntologyEngineerAgent import create_agent

agent = create_agent()
response = agent.invoke(
    "Create a new ontology class for 'SoftwareProject' with properties"
)
```

### Workflows

#### AgentRecommendationWorkflow

Recommends the best AI agent for a given intent using SPARQL queries.

**Features:**
- Intent-to-query matching
- SPARQL template parameterization
- Weighted recommendation scoring
- Provider preference support

**Usage:**

```python
from naas_abi.workflows.AgentRecommendationWorkflow import (
    AgentRecommendationWorkflow,
    AgentRecommendationConfiguration,
    AgentRecommendationParameters
)

workflow = AgentRecommendationWorkflow(
    AgentRecommendationConfiguration(queries_file_path="path/to/queries.ttl")
)

result = workflow.run(AgentRecommendationParameters(
    intent_description="I need help with code generation",
    provider_preference="openai"
))
```

#### ArtificialAnalysisWorkflow

Fetches and stores AI model data from the Artificial Analysis API.

**Features:**
- Fetches model performance data
- Filters for modules with active agents
- Saves timestamped JSON files
- Supports multiple endpoints (models, providers, categories)

**Usage:**

```python
from naas_abi.workflows.ArtificialAnalysisWorkflow import (
    ArtificialAnalysisWorkflow,
    ArtificialAnalysisWorkflowConfiguration,
    ArtificialAnalysisWorkflowParameters
)

workflow = ArtificialAnalysisWorkflow(
    ArtificialAnalysisWorkflowConfiguration(
        api_key="your_api_key",
        base_url="https://artificialanalysis.ai/api/v2"
    )
)

result = workflow.run(ArtificialAnalysisWorkflowParameters(
    endpoint="models",
    validate_agents_only=True
))
```

#### SearchIndividualWorkflow

Searches for individuals (entities) in the knowledge graph.

**Features:**
- Semantic search across entities
- Fuzzy matching support
- Property-based filtering
- Result ranking

#### GetSubjectGraphWorkflow

Retrieves the graph structure for a specific subject (entity).

**Features:**
- Entity relationship exploration
- Configurable depth traversal
- Graph visualization data
- Property and relationship extraction

#### GetObjectPropertiesFromClassWorkflow

Retrieves object properties for a given ontology class.

**Features:**
- Class property discovery
- BFO-compliant property extraction
- Relationship type identification
- Ontology hierarchy traversal

### Pipelines

#### AddIndividualPipeline

Adds new individuals (entities) to the knowledge graph.

**Features:**
- Duplicate detection
- Automatic URI generation
- Property assignment
- Relationship creation

#### AIAgentOntologyGenerationPipeline

Generates AI agent ontologies from Artificial Analysis data.

**Features:**
- BFO-structured ontology generation
- Model-to-agent mapping
- Timestamped audit trails
- Automatic deployment to module folders

**Execution Steps:**
1. Loads Artificial Analysis data
2. Groups models by AI agent
3. Generates ontologies in timestamped folders
4. Deploys current versions to module folders
5. Creates audit trail and summary

#### InsertDataSPARQLPipeline

Inserts data into the knowledge graph using SPARQL INSERT queries.

**Features:**
- SPARQL query execution
- Batch insert operations
- Validation and error handling
- Transaction support

#### MergeIndividualsPipeline

Merges duplicate individuals in the knowledge graph.

**Features:**
- Duplicate detection
- Property merging
- Relationship consolidation
- Audit logging

#### RemoveIndividualPipeline

Removes individuals from the knowledge graph.

**Features:**
- Safe deletion with validation
- Relationship cleanup
- Audit trail creation
- Backup generation

#### Update Pipelines

Specialized pipelines for updating specific entity types:
- `UpdateDataPropertyPipeline`: Updates data properties
- `UpdatePersonPipeline`: Updates person entities
- `UpdateCommercialOrganizationPipeline`: Updates organization entities
- `UpdateSkillPipeline`: Updates skill entities
- `UpdateLinkedInPagePipeline`: Updates LinkedIn page data
- `UpdateTickerPipeline`: Updates stock ticker information
- `UpdateWebsitePipeline`: Updates website information
- `UpdateLegalNamePipeline`: Updates legal names

### Ontologies

The module includes a comprehensive ontology structure organized in a 4-level hierarchy:

1. **Top-level**: BFO foundational ontologies
2. **Mid-level**: Common Core Ontologies (CCO)
3. **Domain-level**: Domain-specific ontologies
4. **Application-level**: Use-case specific ontologies

**Location:** `naas_abi/ontologies/`

### Models

The module supports multiple AI model configurations:

#### Cloud Mode (Default)
- **Model**: `gpt-4.1-mini`
- **Provider**: OpenAI
- **Temperature**: 0 (precise orchestration)
- **Requires**: `OPENAI_API_KEY`

#### Airgap Mode
- **Qwen3** (default): Temperature 0.7, 8K context
- **Gemma3** (alternative): Temperature 0.2, 8K context
- **Requires**: Docker Model Runner on `localhost:12434`

**Configuration:**

```python
# Set environment variable
AI_MODE=cloud  # or "airgap" or "local"
```

## CLI Tools

The module provides CLI commands for creating new components:

```bash
# Create a new module
python -m naas_abi.cli create-module

# Create a new agent
python -m naas_abi.cli create-agent

# Create a new integration
python -m naas_abi.cli create-integration

# Create a new workflow
python -m naas_abi.cli create-workflow

# Create a new pipeline
python -m naas_abi.cli create-pipeline

# Create a new ontology
python -m naas_abi.cli create-ontology
```

Each command provides an interactive wizard to guide you through the creation process.

## Usage Examples

### Basic Agent Interaction

```python
from naas_abi_core.engine.Engine import Engine

# Initialize engine
engine = Engine()
engine.load(module_names=["naas_abi"])

# Get AbiAgent
from naas_abi.agents.AbiAgent import create_agent

agent = create_agent()

# Interact with agent
response = agent.invoke("What agents are available?")
print(response)
```

### Knowledge Graph Operations

```python
from naas_abi.agents.KnowledgeGraphBuilderAgent import create_agent

kg_agent = create_agent()

# Add an organization
kg_agent.invoke("Add organization 'NaasAI' with website 'https://naas.ai'")

# Search for entities
from naas_abi.workflows.SearchIndividualWorkflow import (
    SearchIndividualWorkflow,
    SearchIndividualWorkflowConfiguration,
    SearchIndividualWorkflowParameters
)

workflow = SearchIndividualWorkflow(
    SearchIndividualWorkflowConfiguration(
        triple_store=engine.services.triple_store
    )
)

results = workflow.run(SearchIndividualWorkflowParameters(
    search_term="NaasAI"
))
```

### Workflow Execution

```python
from naas_abi.workflows.AgentRecommendationWorkflow import (
    AgentRecommendationWorkflow,
    AgentRecommendationConfiguration,
    AgentRecommendationParameters
)

workflow = AgentRecommendationWorkflow(
    AgentRecommendationConfiguration(
        queries_file_path="path/to/queries.ttl"
    )
)

recommendations = workflow.run(AgentRecommendationParameters(
    intent_description="I need help with data analysis",
    provider_preference="anthropic"
))
```

### Pipeline Execution

```python
from naas_abi.pipelines.AddIndividualPipeline import (
    AddIndividualPipeline,
    AddIndividualPipelineConfiguration,
    AddIndividualPipelineParameters
)

pipeline = AddIndividualPipeline(
    AddIndividualPipelineConfiguration(
        triple_store=engine.services.triple_store,
        search_individual_configuration=SearchIndividualWorkflowConfiguration(
            triple_store=engine.services.triple_store
        )
    )
)

graph = pipeline.run(AddIndividualPipelineParameters(
    individual_label="New Company",
    individual_type="CommercialOrganization"
))
```

## Configuration

### Environment Variables

| Variable | Values | Default | Description |
|----------|--------|---------|-------------|
| `AI_MODE` | `cloud` \| `airgap` \| `local` | `cloud` | Model deployment mode |
| `OPENAI_API_KEY` | API key | Required (cloud) | For cloud models |
| `NAAS_API_KEY` | API key | Optional | For production triggers |
| `ENV` | `dev` \| `prod` | `dev` | Environment mode |

### Module Configuration

```yaml
modules:
  - module: naas_abi
    enabled: true
    config:
      datastore_path: "abi"
      workspace_id: "{{ secret.WORKSPACE_ID }}"
      storage_name: "{{ secret.STORAGE_NAME }}"
```

## Key Features

### 🔄 Context-Aware Orchestration
Preserves active conversations while enabling intelligent agent transitions.

### 🌍 Multilingual Support
Native French/English code-switching with cultural awareness.

### 🎯 Weighted Decision Routing
Sophisticated hierarchy for optimal agent selection based on request type.

### 🔍 Knowledge Graph Integration
Direct access to SPARQL querying and semantic data exploration.

### 🔒 Deployment Flexibility
Choice between cloud (OpenAI) and airgap (Docker Model Runner) models.

### 📊 Strategic Advisory
Direct consultation capabilities for business and technical guidance.

### 🛡️ Production Ready
Event-driven triggers, comprehensive testing, and error resilience.

## Dependencies

- `naas-abi-core>=1.0.0`: Core ABI framework
- `naas-abi-marketplace>=1.0.0`: Marketplace modules and agents
- `thefuzz>=0.22.1`: Fuzzy string matching

## Architecture

### Module Structure

```
naas_abi/
├── agents/              # Agent implementations
│   ├── AbiAgent.py
│   ├── EntitytoSPARQLAgent.py
│   ├── KnowledgeGraphBuilderAgent.py
│   └── OntologyEngineerAgent.py
├── workflows/           # Business logic workflows
│   ├── AgentRecommendationWorkflow.py
│   ├── ArtificialAnalysisWorkflow.py
│   ├── SearchIndividualWorkflow.py
│   ├── GetSubjectGraphWorkflow.py
│   └── GetObjectPropertiesFromClassWorkflow.py
├── pipelines/           # Data processing pipelines
│   ├── AddIndividualPipeline.py
│   ├── AIAgentOntologyGenerationPipeline.py
│   ├── InsertDataSPARQLPipeline.py
│   ├── MergeIndividualsPipeline.py
│   └── Update*Pipeline.py
├── ontologies/          # Ontology definitions
├── models/              # Model configurations
├── cli.py               # CLI commands
└── __init__.py          # Module initialization
```

## Testing

```bash
# Run all tests
pytest naas_abi/ -v

# Test specific agent
pytest naas_abi/agents/AbiAgent_test.py -v

# Test workflows
pytest naas_abi/workflows/ -v

# Test pipelines
pytest naas_abi/pipelines/ -v
```

## See Also

- [ABI Main README](../../README.md) - Complete ABI framework documentation
- [naas-abi-core](../naas-abi-core/) - Core engine documentation
- [naas-abi-cli](../naas-abi-cli/) - CLI tool documentation
- [naas-abi-marketplace](../naas-abi-marketplace/) - Marketplace modules

## License

MIT License

