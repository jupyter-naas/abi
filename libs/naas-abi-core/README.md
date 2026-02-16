# naas-abi-core

The core implementation library for ABI (Agentic Brain Infrastructure), providing the fundamental building blocks for building unified AI systems. This library implements the core concepts, services, and architecture patterns that enable ontology-driven AI applications.

## Overview

The ABI Library is the core implementation of ABI's concepts, designed to build a unified AI system. This library provides the fundamental building blocks for connecting, processing, and utilizing data across different AI components.

`naas-abi-core` is the foundational library that powers the ABI framework. It provides:

- **Engine**: Central orchestration system that loads and coordinates modules, services, and ontologies
- **Services**: Hexagonal architecture-based services for storage, secrets, and AI capabilities
- **Modules**: Modular system for organizing agents, integrations, pipelines, and workflows
- **Agents**: LangGraph-based AI agents with tool binding and conversation management
- **Applications**: Ready-to-use interfaces (REST API, Terminal, MCP Protocol)

## Installation

```bash
pip install naas-abi-core
```

### Optional Dependencies

```bash
# For Qdrant vector store support
pip install naas-abi-core[qdrant]

# For AWS S3 object storage support
pip install naas-abi-core[aws]

# For SSH tunnel support
pip install naas-abi-core[ssh]

# For OpenRouter integration
pip install naas-abi-core[openrouter]

# Install all optional dependencies
pip install naas-abi-core[all]
```

## Core Architecture

### Engine

The `Engine` is the central orchestrator that:

1. **Loads Configuration**: Reads and validates YAML configuration files
2. **Initializes Services**: Sets up storage, vector, triple store, and secret services based on module dependencies
3. **Loads Modules**: Discovers and loads modules with their agents, integrations, pipelines, and workflows
4. **Loads Ontologies**: Loads RDF ontologies into the triple store for semantic reasoning
5. **Initializes Components**: Calls `on_initialized()` on all modules after everything is loaded

**Example Usage:**

```python
from naas_abi_core.engine.Engine import Engine

# Initialize engine with default configuration (config.yaml)
engine = Engine()

# Load all modules
engine.load()

# Or load specific modules
engine.load(module_names=["naas_abi", "my_custom_module"])

# Access loaded modules
for module_name, module in engine.modules.items():
    print(f"Module: {module_name}")
    print(f"Agents: {[agent.__name__ for agent in module.agents]}")

# Access services
triple_store = engine.services.triple_store
vector_store = engine.services.vector_store
object_storage = engine.services.object_storage
secret_service = engine.services.secret
```

### Modules

Modules are the primary organizational unit in ABI. Each module can contain:

- **Agents**: AI agents that can be used for conversations and task execution
- **Integrations**: Connections to third-party services and APIs
- **Pipelines**: Data transformation processes that convert raw data into semantic representations
- **Workflows**: Business logic that can be exposed as tools, API endpoints, or scheduled jobs
- **Ontologies**: RDF/Turtle files that define semantic knowledge structures

**Module Structure:**

```python
from naas_abi_core.module.Module import BaseModule, ModuleConfiguration
from naas_abi_core.engine.EngineProxy import EngineProxy

class MyModule(BaseModule):
    class Configuration(ModuleConfiguration):
        # Module-specific configuration
        api_key: str
    
    dependencies = ModuleDependencies(
        modules=[],  # Other modules this module depends on
        services=[TripleStoreService, VectorStoreService]  # Required services
    )
    
    def on_load(self):
        # Called when module is loaded
        # Load ontologies, agents, etc.
        super().on_load()
    
    def on_initialized(self):
        # Called after all modules and services are initialized
        # Safe to access other modules and services here
        pass
```

### Services

Services form the foundational layer of ABI, implementing the Hexagonal Architecture (Ports & Adapters) pattern to provide flexible and system-agnostic interfaces. This architectural approach allows ABI to seamlessly integrate with existing systems while maintaining clean separation of concerns.

Each service defines a primary port (interface) that specifies its capabilities, while multiple secondary adapters can implement this interface for different backend systems. This means you can:

- Easily swap implementations without changing business logic
- Add new integrations by implementing new adapters
- Test components in isolation using mock adapters

For example, the Secret Service could connect to various backend systems through different adapters:
- Hashicorp Vault
- AWS Secrets Manager
- Azure Key Vault
- Environment Variables
- Local File System
- Google Cloud Secret Manager
- Kubernetes Secrets

This modular approach ensures that ABI can be deployed in any environment while maintaining consistent interfaces and behavior across different infrastructure choices.

#### Triple Store Service

Manages RDF knowledge graphs for semantic reasoning and ontology storage.

**Supported Backends:**
- Oxigraph (default)
- SPARQL endpoints
- Custom adapters

**Example:**

```python
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService

triple_store = engine.services.triple_store

# Query the knowledge graph
results = triple_store.query("""
    SELECT ?subject ?predicate ?object
    WHERE {
        ?subject ?predicate ?object
    }
    LIMIT 10
""")
```

#### Vector Store Service

Manages vector embeddings for semantic search and similarity matching.

**Supported Backends:**
- Qdrant (optional, requires `[qdrant]` extra)
- Custom adapters

**Example:**

```python
from naas_abi_core.services.vector_store.VectorStoreService import VectorStoreService

vector_store = engine.services.vector_store

# Store embeddings
vector_store.upsert(
    collection_name="intents",
    vectors=[embedding],
    ids=["intent_1"],
    payloads=[{"text": "user query"}]
)

# Search similar vectors
results = vector_store.search(
    collection_name="intents",
    query_vector=query_embedding,
    limit=5
)
```

#### Object Storage Service

Manages file storage for documents, reports, and generated content.

**Supported Backends:**
- AWS S3 (optional, requires `[aws]` extra)
- MinIO
- Local file system
- Custom adapters

**Example:**

```python
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService

object_storage = engine.services.object_storage

# Upload a file
object_storage.upload(
    bucket="my-bucket",
    key="documents/report.pdf",
    file_path="/path/to/report.pdf"
)

# Download a file
object_storage.download(
    bucket="my-bucket",
    key="documents/report.pdf",
    file_path="/path/to/downloaded.pdf"
)
```

#### Secret Service

Manages secrets and credentials securely across different storage systems.

**Supported Backends:**
- Environment variables
- Naas Secret Manager
- Hashicorp Vault
- AWS Secrets Manager
- Azure Key Vault
- Google Cloud Secret Manager
- Kubernetes Secrets
- Local file system
- Custom adapters

**Example:**

```python
from naas_abi_core.services.secret.Secret import Secret

secret_service = engine.services.secret

# Get a secret
api_key = secret_service.get("OPENAI_API_KEY")

# List all secrets
all_secrets = secret_service.list()
```

#### Cache Service

Provides intelligent caching for API calls, tool results, and model responses to optimize performance and manage rate limits.

**Example:**

```python
from naas_abi_core.services.cache.CacheService import CacheService

cache = CacheService()

# Cache a function result
@cache.cache(ttl=3600)
def expensive_api_call(param: str):
    # Expensive operation
    return result

# Force refresh
result = expensive_api_call(param, force_refresh=True)
```

## Core Concepts

### Integration

Integrations provide standardized connections to third-party services and data sources. They handle:
- Authentication and authorization
- API communication
- Data format standardization
- Error handling and retries

**Example:**

```python
from naas_abi_core.integration.integration import Integration, IntegrationConfiguration

class MyAPIConfiguration(IntegrationConfiguration):
    api_key: str
    base_url: str

class MyAPIIntegration(Integration):
    def __init__(self, configuration: MyAPIConfiguration):
        super().__init__(configuration)
        # Initialize connection
    
    def fetch_data(self):
        # Implement API call
        pass
```

### Pipeline

Pipelines are responsible for data ingestion and transformation into the ontological layer. They:
- Utilize integrations to fetch data
- Transform raw data into semantic representations
- Maintain data consistency and quality
- Map external data models to ABI's ontology

**Example:**

```python
from naas_abi_core.pipeline.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from rdflib import Graph

class MyPipelineConfiguration(PipelineConfiguration):
    integration_config: dict

class MyPipelineParameters(PipelineParameters):
    source: str

class MyPipeline(Pipeline):
    def __init__(self, configuration: MyPipelineConfiguration):
        super().__init__(configuration)
    
    def run(self, parameters: MyPipelineParameters) -> Graph:
        # Fetch data from integration
        # Transform to RDF
        # Return Graph
        graph = Graph()
        # ... add triples to graph
        return graph
    
    def trigger(self, event, ontology_name, triple) -> Graph:
        # Event-driven pipeline execution
        return self.run(MyPipelineParameters(source="event"))
```

### Workflow

Workflows leverage the ontological layer to implement business logic and provide data to consumers. They can be used by:
- Large Language Models (LLMs)
- Remote APIs and services
- Other automated processes

**Example:**

```python
from naas_abi_core.workflow.workflow import Workflow, WorkflowConfiguration, WorkflowParameters
from pydantic import BaseModel

class MyWorkflowParameters(WorkflowParameters):
    input_data: str

class MyWorkflowConfiguration(WorkflowConfiguration):
    processing_option: str

class MyWorkflow(Workflow[MyWorkflowParameters]):
    def __init__(self, configuration: MyWorkflowConfiguration):
        super().__init__(configuration)
    
    def run(self, parameters: MyWorkflowParameters):
        # Implement business logic
        # Query knowledge graph
        # Process data
        # Return results
        return {"result": "processed"}
```

### Agent

Agents are AI-powered assistants that can have conversations, use tools, and delegate to sub-agents.

**Features:**
- LangGraph-based conversation management
- Tool binding and execution
- Sub-agent delegation
- Intent-based routing
- Conversation persistence (PostgreSQL checkpointing)
- Event streaming for real-time updates

**Example:**

```python
from naas_abi_core.services.agent.Agent import Agent
from langchain_openai import ChatOpenAI

class MyAgent(Agent):
    def __init__(self):
        super().__init__(
            name="MyAgent",
            description="An agent that helps with specific tasks",
            system_prompt="You are a helpful assistant...",
            chat_model=ChatOpenAI(model="gpt-4"),
            tools=[my_tool, my_workflow],
            agents=[sub_agent]  # Optional sub-agents
        )
```

## Applications

### REST API

FastAPI-based REST API that automatically exposes all agents, workflows, and pipelines.

**Features:**
- OpenAPI/Swagger documentation
- OAuth2 authentication
- CORS support
- Automatic endpoint generation from agents/workflows/pipelines

**Usage:**

```python
from naas_abi_core.apps.api.api import api

# Run the API server
api()
```

**Endpoints:**
- `GET /` - API landing page
- `GET /docs` - Swagger UI documentation
- `GET /redoc` - ReDoc documentation
- `POST /agents/{agent_name}/completion` - Agent completion endpoint
- `POST /workflows/{workflow_name}/run` - Workflow execution endpoint
- `POST /pipelines/{pipeline_name}/run` - Pipeline execution endpoint

### Terminal Agent

Interactive terminal interface for chatting with agents.

**Usage:**

```python
from naas_abi_core.apps.terminal_agent.main import run_agent
from naas_abi_core.services.agent.Agent import Agent

agent = MyAgent()
run_agent(agent)
```

### MCP Server

Model Context Protocol (MCP) server for integration with Claude Desktop and VS Code.

**Features:**
- Dynamic agent discovery from OpenAPI spec
- HTTP and stdio transport modes
- Automatic tool registration

**Usage:**

```bash
# Start MCP server
python -m naas_abi_core.apps.mcp.mcp_server

# Or with HTTP transport
MCP_TRANSPORT=http python -m naas_abi_core.apps.mcp.mcp_server
```

## Configuration

ABI uses YAML configuration files (typically `config.yaml`) to configure:

- **Services**: Storage backends, connection details
- **Modules**: Which modules to load and their configurations
- **API**: API title, description, CORS settings
- **Global Config**: AI mode (cloud, local, airgap)

**Example Configuration:**

```yaml
api:
  title: "My ABI API"
  description: "API for my AI system"
  cors_origins:
    - "http://localhost:9879"

global_config:
  ai_mode: "cloud"  # or "local" or "airgap"

services:
  triple_store:
    type: "oxigraph"
    url: "http://localhost:7878"
  
  vector_store:
    type: "qdrant"
    url: "http://localhost:6333"
  
  object_storage:
    type: "minio"
    endpoint: "http://localhost:9000"
  
  secret:
    type: "env"

modules:
  - module: "naas_abi"
    enabled: true
  - path: "./src/my_module"
    enabled: true
    config:
      api_key: "${MY_API_KEY}"
```

## Key Dependencies

- **rdflib**: RDF and ontology management
- **langgraph**: Agent conversation management
- **langgraph-checkpoint-postgres**: Conversation persistence
- **fastapi**: REST API framework
- **sparqlwrapper**: SPARQL query execution
- **pydantic**: Data validation and configuration
- **loguru**: Logging
- **langchain-openai**: OpenAI integration

## Architecture Patterns

### Hexagonal Architecture (Ports & Adapters)

All services follow the Hexagonal Architecture pattern:

- **Primary Port**: Interface defining service capabilities
- **Secondary Adapters**: Implementations for different backends
- **Benefits**: Easy swapping of implementations, testability, system-agnostic design

### Module System

- **Dependency Resolution**: Automatic dependency resolution and ordering
- **Lazy Loading**: Services loaded only when needed by modules
- **Lifecycle Hooks**: `on_load()` and `on_initialized()` for setup
- **Isolation**: Modules can be developed and tested independently

### Event-Driven Pipelines

Pipelines can be triggered by:
- Manual execution via API or code
- Ontology events (triple insertions/updates)
- Scheduled jobs
- Workflow triggers

## Development

### Running Tests

```bash
pytest
```

### Type Checking

```bash
mypy naas_abi_core
```

### Building

```bash
uv build
```

## See Also

- [ABI Main README](../../README.md) - Complete ABI framework documentation
- [naas-abi-cli](../naas-abi-cli/) - CLI tool for ABI projects
- [naas-abi-marketplace](../naas-abi-marketplace/) - Marketplace modules and agents

## License

MIT License

