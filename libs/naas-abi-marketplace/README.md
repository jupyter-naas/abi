# naas-abi-marketplace

A comprehensive marketplace of pre-built modules, agents, integrations, and workflows for the ABI (Agentic Brain Infrastructure) framework. This package provides ready-to-use components organized into three main categories: AI agents, application integrations, and domain expert modules.

## Overview

`naas-abi-marketplace` is a collection of modular components that extend the ABI framework with:

- **AI Agent Modules**: Integration with major AI providers (ChatGPT, Claude, Gemini, Grok, Mistral, etc.)
- **Application Modules**: four application modules run in-engine (listed below)
- **Domain Expert Modules**: specialized agents for professional roles (listed below)

### Application Modules

Four application modules run in-engine:

- `applications.git` - Git operations and repository management (runs in the CLI's working directory)
- `applications.bodo` - Bodo platform integration
- `applications.naas` - ontology YAML publishing to a Naas workspace (for `ontology_engineer`)
- `applications.x` - X (Twitter) recent-tweets ingestion and the Recent Tweets app

The other applications (GitHub, LinkedIn, Google Search, PostgreSQL, PowerPoint,
Pennylane, Agicap, ArXiv, PubMed, Sanax, SEC EDGAR, ...) are **remote modules**:
each runs in its own process and reaches the engine over NATS. They live in
[`libs/naas-abi-marketplace-modules`](../naas-abi-marketplace-modules/README.md)
(jupyter-naas/abi#1423). Their in-engine versions were removed: a configuration
that still loads one (e.g. `naas_abi_marketplace.applications.github`) fails at
load. OpenRouter models come from `naas_abi_marketplace.ai.openrouter`.

**Usage Example:**

```python
from naas_abi_core.engine.Engine import Engine

engine = Engine()
engine.load(module_names=["naas_abi_marketplace.applications.git"])

# Access the Git agent
from naas_abi_marketplace.applications.git.agents.GitAgent import GitAgent

agent = GitAgent.New()
response = agent.invoke("Summarize the staged changes")
```

### Domain Expert Modules

Specialized agents designed for specific professional roles and tasks.

#### Available Domain Experts

**Engineering & Development:**
**Engineering & Data:**
- `domains.signals` — includes `SoftwareEngineerAgent`, `DevOpsEngineerAgent`, `DataEngineerAgent`

**Business & Sales:**
- `domains.account-executive` - Account management
- `domains.business-development-representative` - Business development
- `domains.sales-development-representative` - Sales development
- `domains.inside-sales-representative` - Inside sales operations

**Marketing & Content:**
- `domains.external` — includes `ContentCreatorAgent`, `CommunityManagerAgent`
- `domains.plans` — includes `ContentStrategistAgent` (content strategy)
- `domains.operations` — includes `ContentAnalystAgent`, `CampaignManagerAgent`

**Finance & Accounting:**
- `domains.finance` — includes `AccountantAgent`, `FinancialControllerAgent`, `TreasurerAgent`

**Management & Operations:**
- `domains.project-manager` - Project management
- `domains.customer-success-manager` - Customer success
- `domains.personnel` - HR management

**Research & Investigation:**
- `domains.intelligence` — includes `OSINTResearcherAgent`, `PrivateInvestigatorAgent`

**Support:**
- `domains.operations.modules.support` - Technical support and issue management

**Usage Example:**

```python
from naas_abi_core.engine.Engine import Engine

engine = Engine()
engine.load(module_names=["naas_abi_marketplace.domains.signals"])

# Access Software Engineer agent
from naas_abi_marketplace.domains.signals.agents.SoftwareEngineerAgent import (
    SoftwareEngineerAgent,
)

agent = SoftwareEngineerAgent.New()
response = agent.invoke("Design a microservices architecture for an e-commerce platform")
```

## Module Structure

Each marketplace module follows a consistent structure:

```
module_name/
├── __init__.py              # Module definition and configuration
├── agents/                   # AI agents
│   └── *Agent.py            # Agent implementations
├── integrations/             # External service integrations
│   └── *Integration.py      # Integration implementations
├── workflows/                # Business logic workflows
│   └── *Workflow.py         # Workflow implementations
├── pipelines/               # Data processing pipelines
│   └── *Pipeline.py         # Pipeline implementations
├── ontologies/              # Semantic ontologies
│   └── *.ttl                # RDF/Turtle ontology files
├── orchestrations/          # Dagster orchestration (optional)
│   └── definitions.py      # Dagster definitions
└── README.md                # Module documentation
```

## Configuration

### Enabling Modules

Modules are configured in your `config.yaml`:

```yaml
modules:
  # AI Agents
  - module: naas_abi_marketplace.ai.chatgpt
    enabled: true
    config:
      openai_api_key: "${OPENAI_API_KEY}"
  
  - module: naas_abi_marketplace.ai.anthropic
    enabled: true
    config:
      anthropic_api_key: "${ANTHROPIC_API_KEY}"
  
  # Applications (in-engine; the others run as remote modules)
  - module: naas_abi_marketplace.applications.git
    enabled: true
  
  # Domain Experts
  - module: naas_abi_marketplace.domains.signals
    enabled: true
  
  - module: naas_abi_marketplace.domains.operations
    enabled: true
```

### Soft Dependencies

Many modules are marked as "soft" dependencies, meaning they're optional and won't cause failures if unavailable:

```python
# In naas_abi module dependencies
modules=[
    "naas_abi_marketplace.ai.anthropic#soft",  # Optional
    "naas_abi_marketplace.applications.git#soft",  # Optional
]
```

## Usage Patterns

### Loading Multiple Modules

```python
from naas_abi_core.engine.Engine import Engine

engine = Engine()
engine.load(module_names=[
    "naas_abi_marketplace.ai.chatgpt",
    "naas_abi_marketplace.ai.anthropic",
    "naas_abi_marketplace.applications.git",
    "naas_abi_marketplace.domains.signals"
])
```

### Accessing Module Components

```python
# Access agents
for module_name, module in engine.modules.items():
    for agent_class in module.agents:
        print(f"{module_name}: {agent_class.__name__}")

# Access workflows
for module_name, module in engine.modules.items():
    for workflow in module.workflows:
        print(f"{module_name}: {workflow.__class__.__name__}")

# Access integrations
for module_name, module in engine.modules.items():
    for integration in module.integrations:
        print(f"{module_name}: {integration.__class__.__name__}")
```

## Demo Applications

The marketplace includes demo applications and UI patterns in `__demo__/apps/`:

- **Dashboard**: Central control hub
- **Chat Interface**: Multi-agent chat interface
- **Table Mode**: Advanced data table interface
- **Kanban Mode**: Project management with kanban boards
- **Ontology Mode**: Knowledge graph visualization
- **Calendar Mode**: Scheduling interface
- **Gallery Mode**: Media management
- **And more...**

## Marketplace UI

A Streamlit-based marketplace interface (`marketplace.py`) provides:

- **Module Discovery**: Browse available modules by category
- **Status Monitoring**: Check which modules are running
- **One-Click Launch**: Start applications and modules
- **Search**: Find modules by name or description

**Run the marketplace:**

```bash
streamlit run marketplace.py
```

## Key Features

### 🔌 **Extensive Integrations**
50+ pre-built integrations with popular services and platforms

### 🤖 **Multiple AI Providers**
Support for 10+ major AI providers with optimized configurations

### 👥 **Domain Expertise**
20+ specialized agents for professional roles and tasks

### 🧩 **Modular Architecture**
Pick and choose only the modules you need

### ⚡ **Optional Dependencies**
Modules can be installed individually to minimize dependencies

### 📚 **Comprehensive Documentation**
Each module includes detailed README and usage examples

### 🔄 **Consistent Interface**
All modules follow the same structure and patterns

## Dependencies

- `naas-abi-core>=1.0.0`: Core ABI framework

Optional dependencies are listed in `pyproject.toml` under `[project.optional-dependencies]` and can be installed per module as needed.

## Contributing

To add a new module to the marketplace:

1. Create a new directory under `ai/`, `applications/`, or `domains/`
2. Follow the standard module structure
3. Implement required components (agents, integrations, etc.)
4. Add module configuration in `__init__.py`
5. Create a README.md with documentation
6. Add optional dependencies to `pyproject.toml` if needed

## See Also

- [ABI Main README](../../README.md) - Complete ABI framework documentation
- [naas-abi-core](../naas-abi-core/) - Core engine documentation
- [naas-abi](../naas-abi/) - Main ABI module documentation
- [naas-abi-cli](../naas-abi-cli/) - CLI tool documentation

## License

MIT License

## Documentation

- [Install a marketplace module](https://docs.naas.ai/user-guide/build/modules/marketplace/marketplace-install)
- [Marketplace overview](https://docs.naas.ai/user-guide/build/modules/marketplace/marketplace-overview)
- [Publish a module](https://docs.naas.ai/user-guide/build/modules/marketplace/marketplace-publish)
- [Quickstart](https://docs.naas.ai/user-guide/get-started/quickstart)
