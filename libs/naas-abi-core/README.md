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
- **NATS mode** (3.0): the engine serves its kernel services on a NATS broker, the bus is JetStream, module jobs replace Dagster, and modules can run in their own process with `naas-abi-sdk`

Upgrading from 2.x: [Migrate from 2.x to 3.0](https://docs.naas.ai/user-guide/upgrade/migrate-to-3) and [Breaking changes in 3.0](https://docs.naas.ai/user-guide/upgrade/breaking-changes-3).

## Installation

```bash
pip install naas-abi-core
```

### Optional Dependencies

```bash
# NATS mode: naas-abi-proto, naas-abi-sdk, nats-py (needed by naas-abi)
pip install naas-abi-core[nats]

# OpenTelemetry tracing
pip install naas-abi-core[otel]

# Qdrant vector store, AWS S3 object storage, SSH tunnels, Redis, OpenRouter
pip install naas-abi-core[qdrant,aws,ssh,redis,openrouter]

# Every supported extra (nats and otel included)
pip install naas-abi-core[all]

# Legacy, for projects without NATS, removed in the next major: Dagster, RabbitMQ
pip install 'naas-abi-core[all,dagster,rabbitmq]'
```

`naas-abi-core[all]` does not include the legacy `dagster` and `rabbitmq`
extras. Without them, `DagsterOrchestration.New()`, the RabbitMQ bus adapter
and the Dagster app raise `MissingLegacyExtra`, which prints the install
command.

## NATS mode

A top-level `nats:` block in the config switches the engine to NATS mode:

```yaml
nats:
  nats_url: "nats://engine:{{ secret.NATS_ENGINE_PASSWORD }}@127.0.0.1:4222"
  auth_callout:
    nats_url: "nats://auth:{{ secret.NATS_AUTH_PASSWORD }}@127.0.0.1:4222"
    issuer_seed: "{{ secret.NATS_AUTH_CALLOUT_SEED }}"
  discovery:
    project: "my_project"
```

- Every kernel service is served on `abi.svc.<service>.v1.*` (protobuf
  contracts from `naas-abi-proto`), and modules reach services through NATS
  facades, even in one process.
- The bus is NATS JetStream; module jobs (`naas_abi_core.module.jobs`: `@job`,
  `Cron`, `Every`, `OnEvent`) run scheduled and event-driven work, and durable
  workflows (`naas_abi_core.module.workflows`: `@workflow`) add a typed input and
  output and checkpointed steps. See [Workflow](#workflow).
- One engine serves per NATS account (`nats.engine.role`, `ABI_ROLLOUT_ID` for
  handovers); discovery registers remote modules.
- Agent memory and the activity log live in the Document Service.

Architecture: [NATS and the Kernel Services](https://docs.naas.ai/developer-guide/architecture/nats),
[Remote Modules and Jobs](https://docs.naas.ai/developer-guide/architecture/remote-modules).

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
```

A module finds the `Pipeline` subclasses under its `pipelines/` folder and builds them in
`on_initialized` (`New()`, or an empty `<Name>PipelineConfiguration`). One with a live
`run()` that takes a parameters model gets `POST /pipelines/<slug>` on the REST API, and,
in NATS mode, is published as the durable workflow `pipeline.<slug>` (see
[Workflow](#workflow)): one attempt, since a retry would write the triples twice, and one
run at a time. `trigger(event, ontology_name, triple)` is an optional hook for code that
subscribes to triple-store events (`triple_store.subscribe`); nothing calls it by default.

A remote module writes the same class on `naas_abi_sdk.pipeline` (`naas-abi-sdk[workflows,rdf]`),
with an `async def run`: see the [SDK README](../naas-abi-sdk/README.md#workflows-pipelines-and-integrations).

### Workflow

Workflows leverage the ontological layer to implement business logic and provide data to
consumers: agents (as tools), other modules, scripts and schedules. A workflow takes one of
two forms.

**A class.** `Workflow[P]` under the module's `workflows/` folder, with a sync `run`:

```python
from naas_abi_core.workflow.workflow import Workflow, WorkflowConfiguration, WorkflowParameters

class MyWorkflowParameters(WorkflowParameters):
    input_data: str

class MyWorkflowConfiguration(WorkflowConfiguration):
    processing_option: str

class MyWorkflow(Workflow[MyWorkflowParameters]):
    """Processes input data: an agent reads this to decide when to call it."""

    def __init__(self, configuration: MyWorkflowConfiguration):
        super().__init__(configuration)

    def run(self, parameters: MyWorkflowParameters):
        # Query the knowledge graph, call integrations, return results
        return {"result": "processed"}
```

The module builds it in `on_initialized`. `as_tools()` gives agents its tools, and a live
`run()` that takes a parameters model gets `POST /workflows/<slug>` (the class name in snake
case). A remote module writes the same class on `naas_abi_sdk.workflow` (`naas-abi-sdk[workflows]`),
with an `async def run`; the kernel REST API does not mount it.

**A durable workflow.** A module method decorated with `@workflow`: a job with a typed input
and output whose steps are journaled, so a retried run skips the steps that finished. A sync
method runs in a worker thread with a `SyncFlowContext`; an `async` one gets the SDK's
`FlowContext`. NATS mode only.

```python
from naas_abi_core.module.jobs import Cron
from naas_abi_core.module.workflows import SyncFlowContext, workflow

class ABIModule(BaseModule):
    @workflow(max_attempts=3, triggers=(Cron("0 0 2 * * *", input={"table": "orders"}),))
    def report(self, ctx: SyncFlowContext, inp: ReportInput) -> ReportOutput:
        rows = ctx.step("load", self.load, inp.table)  # journaled: a retry skips it
        ctx.map_call("push", "acme.sink", "push", [{"row": r} for r in rows])
        return ReportOutput(count=len(rows))
```

- `ctx.step` (journaled), `ctx.map` (in-process fan-out), `ctx.call` / `ctx.map_call` (child
  runs of any module's workflows). Step keys are unique per run and stable across attempts; a
  step result is JSON, at most 256 KiB.
- An invalid input fails the run without a retry. A workflow that calls itself is refused
  (`SelfCall`). Delivery is at least once: a run must be safe to repeat.
- Triggers are `Cron` / `Every` (with `input=`) and `OnEvent`; limits are `max_attempts`,
  `max_concurrency` and `timeout`.
- Callers: `self.get_workflow(name)`, `self.engine.modules[id].get_workflow(name)`,
  `self.engine.get_workflow(module_id, name)` (any module, engine or remote, declared as a
  dependency). `.run(input)` returns the output; `.start(input, idempotency_key=)` a
  `WorkflowRun` (`status`, `wait`, `result`, `steps`, `cancel`). Both are coroutines.

**The bridge.** In NATS mode, with `nats.workflows.bridge` (default `true`), the engine
publishes every `Workflow` and `Pipeline` instance with a live typed sync `run()` as a one-step
durable workflow, `workflow.<slug>` / `pipeline.<slug>`, with `max_attempts=1` and
`max_concurrency=1`. A graph result becomes Turtle with its triple count; a result over
60 KiB is cut. The class, its agent tools and its REST route do not change.

Durable runs show in Nexus under System › Jobs (launch form, steps, child runs) and are
served to scripts at `/api/workflows`. The reference is
[`naas_abi_core/module/AGENTS.md`](naas_abi_core/module/AGENTS.md) (Workflows, Workflow/Pipeline
bridge); the guides are on docs.naas.ai: [Workflows](https://docs.naas.ai/capabilities/build/workflows/overview)
and [Write a durable workflow](https://docs.naas.ai/capabilities/build/workflows/write-a-durable-workflow).

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

FastAPI-based REST API that exposes the agents, workflows and pipelines of the engine's modules. A remote module's workflows and pipelines are not mounted: start them as durable workflows instead.

**Features:**
- OpenAPI/Swagger documentation
- OAuth2 authentication
- CORS support
- Endpoints generated from agents, and from workflows and pipelines with a live typed `run()`

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
- `POST /workflows/{slug}` - Run a workflow class in process (the class name in snake case)
- `POST /pipelines/{slug}` - Run a pipeline class in process; the graph comes back as Turtle

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

### Dagster (legacy)

`naas_abi_core.apps.dagster` runs Dagster orchestrations (`abi new orchestration`) for a
project without NATS. It is legacy, installed with the `dagster` extra, and removed in the
next major. In NATS mode, schedule with module jobs (`@job`) and durable workflows
(`@workflow`, or `job = JobSettings(...)` on a remote module's class).

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
  # /openapi.json, /docs and /redoc. Unset: on for local development
  # (ENV unset, local or dev), off for deployed stacks.
  docs_enabled: true

global_config:
  ai_mode: "cloud"  # or "local" or "airgap"

nats:
  nats_url: "nats://engine:{{ secret.NATS_ENGINE_PASSWORD }}@127.0.0.1:4222"
  auth_callout:
    nats_url: "nats://auth:{{ secret.NATS_AUTH_PASSWORD }}@127.0.0.1:4222"
    issuer_seed: "{{ secret.NATS_AUTH_CALLOUT_SEED }}"

services:
  triple_store:
    triple_store_adapter:
      adapter: "oxigraph"
      config:
        oxigraph_url: "http://localhost:7878"
  vector_store:
    vector_store_adapter:
      adapter: "qdrant"
      config:
        host: "localhost"
        port: 6333
  object_storage:
    object_storage_adapter:
      adapter: "fs"
      config:
        base_path: "storage/datastore"
  secret:
    secret_adapters:
      - adapter: "dotenv"
        config: {}

modules:
  - module: "naas_abi"
    enabled: true
  - path: "./src/my_module"
    enabled: true
    config:
      api_key: "{{ secret.MY_API_KEY }}"
```

The full reference, with every service and the `nats:`, `telemetry:` and
`dev:` blocks: [Configuration Reference](https://docs.naas.ai/user-guide/get-started/configuration).

## Key Dependencies

- **rdflib**: RDF and ontology management
- **langgraph**: Agent conversation management
- **langgraph-checkpoint-postgres**: Conversation persistence (NATS off)
- **naas-abi-sdk**, **naas-abi-proto**, **nats-py** (`[nats]` extra): NATS mode
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

### Running Pipelines

Pipelines can be run by:
- A direct call: code, an agent tool, or `POST /pipelines/<slug>`
- A durable start of `pipeline.<slug>` (NATS mode): System › Jobs, `/api/workflows`,
  `get_workflow(...)`, or `ctx.call` in another workflow
- A module job or a `@workflow` with `Cron`, `Every` or `OnEvent` triggers
- Your own triple-store subscription, through `trigger`

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

- [ABI Main README](https://github.com/jupyter-naas/abi/blob/main/README.md) - Complete ABI framework documentation
- [naas-abi-cli](https://github.com/jupyter-naas/abi/tree/main/libs/naas-abi-cli) - CLI tool for ABI projects
- [naas-abi-marketplace](https://github.com/jupyter-naas/abi/tree/main/libs/naas-abi-marketplace) - Marketplace modules and agents

## License

MIT License

## Documentation

- [Install and prerequisites](https://docs.naas.ai/user-guide/get-started/install)
- [Quickstart](https://docs.naas.ai/user-guide/get-started/quickstart)
- [Configuration](https://docs.naas.ai/user-guide/get-started/configuration)
- [Module jobs and scheduling](https://docs.naas.ai/user-guide/build/modules/module-jobs)
- [Workflows](https://docs.naas.ai/capabilities/build/workflows/overview) and [Pipelines](https://docs.naas.ai/capabilities/build/pipelines/overview)
- [Architecture](https://docs.naas.ai/developer-guide/architecture/nats)
- [Contribute to ABI](https://docs.naas.ai/developer-guide/contributing/overview)
- [Testing](https://docs.naas.ai/developer-guide/contributing/testing)
