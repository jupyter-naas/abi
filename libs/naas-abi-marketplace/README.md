# naas-abi-marketplace

A comprehensive marketplace of pre-built modules, agents, integrations, and workflows for the ABI (Agentic Brain Infrastructure) framework. This package provides ready-to-use components organized into three main categories: AI agents, application integrations, and domain expert modules.

## Overview

`naas-abi-marketplace` is a collection of modular components that extend the ABI framework with:

- **AI Agent Modules**: Integration with major AI providers (ChatGPT, Claude, Gemini, Grok, Mistral, etc.)
- **Application Modules**: 50+ integrations with popular services and platforms
- **Domain Expert Modules**: Specialized agents for specific professional roles and tasks
- **Demo Applications**: Reference implementations and UI patterns

## Installation

```bash
pip install naas-abi-marketplace
```

### Optional Dependencies

Install specific module groups based on your needs:

```bash
# AI Agents
pip install naas-abi-marketplace[ai-chatgpt]
pip install naas-abi-marketplace[ai-claude]
pip install naas-abi-marketplace[ai-gemini]
pip install naas-abi-marketplace[ai-grok]
pip install naas-abi-marketplace[ai-mistral]
pip install naas-abi-marketplace[ai-perplexity]
pip install naas-abi-marketplace[ai-llama]
pip install naas-abi-marketplace[ai-qwen]
pip install naas-abi-marketplace[ai-deepseek]
pip install naas-abi-marketplace[ai-gemma]

# Application Integrations
pip install naas-abi-marketplace[applications-github]
pip install naas-abi-marketplace[applications-linkedin]
pip install naas-abi-marketplace[applications-postgres]
pip install naas-abi-marketplace[applications-powerpoint]
pip install naas-abi-marketplace[applications-arxiv]
pip install naas-abi-marketplace[applications-pubmed]
# ... and many more
```

## Module Categories

### AI Agent Modules

Pre-configured agents for major AI providers with optimized model configurations and capabilities.

#### Available AI Agents

1. **ChatGPT** (`ai.chatgpt`)
   - Models: GPT-4o, o3-pro, o3, GPT-4.1, GPT-4.1 mini
   - Features: Web search integration, advanced reasoning
   - Intelligence: 53-71 (depending on model)
   - Use cases: General purpose, code generation, research

2. **Claude** (`ai.claude`)
   - Models: Claude 4 Opus, Claude 4 Sonnet (with Thinking variants)
   - Features: Constitutional AI, advanced reasoning
   - Intelligence: 53-64
   - Use cases: Complex analysis, ethical considerations, nuanced understanding

3. **Gemini** (`ai.gemini`)
   - Models: Gemini Pro, Gemini Ultra
   - Features: Multimodal capabilities, creative tasks
   - Use cases: Image generation, creative content, multimodal analysis

4. **Grok** (`ai.grok`)
   - Models: Grok 4, Grok 3, Grok 3 mini Reasoning
   - Features: Highest intelligence scores globally, truth-seeking
   - Intelligence: 51-73 (highest globally)
   - Use cases: Truth-seeking, unbiased analysis, maximum capability tasks

5. **Mistral** (`ai.mistral`)
   - Models: Mistral Large, Mistral Medium
   - Features: Code and math excellence
   - Use cases: Programming assistance, mathematical reasoning

6. **Perplexity** (`ai.perplexity`)
   - Models: R1 1776
   - Features: AI-powered search, real-time information
   - Intelligence: 54
   - Use cases: Web search, current events, information discovery

7. **Llama** (`ai.llama`)
   - Models: Llama 3, Llama 3.1
   - Features: Open-source, local deployment
   - Use cases: Privacy-focused applications, local AI

8. **Qwen** (`ai.qwen`)
   - Models: Qwen 2.5, Qwen 2
   - Features: Multilingual support, efficient performance
   - Use cases: Multilingual tasks, cost-effective deployment

9. **DeepSeek** (`ai.deepseek`)
   - Models: DeepSeek V2, DeepSeek Coder
   - Features: Code-focused, high performance
   - Use cases: Software development, code analysis

10. **Gemma** (`ai.gemma`)
    - Models: Gemma 2, Gemma 3
    - Features: Lightweight, efficient
    - Use cases: Resource-constrained environments

**Usage Example:**

```python
from naas_abi_core.engine.Engine import Engine

engine = Engine()
engine.load(module_names=["naas_abi_marketplace.ai.chatgpt"])

# Access ChatGPT agent
from naas_abi_marketplace.ai.chatgpt.agents.ChatGPTAgent import create_agent

agent = create_agent()
response = agent.invoke("Explain quantum computing")
```

### Application Modules

50+ integrations with popular services, APIs, and platforms.

#### Available Applications

**Development & Code:**
- `applications.github` - GitHub integration (issues, PRs, repositories)
- `applications.git` - Git operations and repository management
- `applications.aws` - AWS services integration
- `applications.bodo` - Bodo platform integration

**Communication & Collaboration:**
- `applications.gmail` - Gmail integration
- `applications.slack` - Slack workspace integration
- `applications.whatsapp_business` - WhatsApp Business API
- `applications.sendgrid` - Email delivery service
- `applications.twilio` - SMS and voice communication

**Data & Analytics:**
- `applications.postgres` - PostgreSQL database integration
- `applications.google_analytics` - Google Analytics data
- `applications.google_sheets` - Google Sheets integration
- `applications.airtable` - Airtable database integration
- `applications.algolia` - Algolia search integration

**Research & Knowledge:**
- `applications.arxiv` - ArXiv scientific papers
- `applications.pubmed` - PubMed biomedical articles
- `applications.openalex` - OpenAlex academic data
- `applications.google_search` - Google Search integration
- `applications.newsapi` - News API integration

**Business & Finance:**
- `applications.yahoofinance` - Yahoo Finance data
- `applications.stripe` - Stripe payment processing
- `applications.qonto` - Qonto banking integration
- `applications.pennylane` - Pennylane accounting
- `applications.agicap` - Agicap financial management
- `applications.exchangeratesapi` - Currency exchange rates

**Productivity & Storage:**
- `applications.google_drive` - Google Drive integration
- `applications.google_calendar` - Google Calendar management
- `applications.notion` - Notion workspace integration
- `applications.sharepoint` - SharePoint integration
- `applications.powerpoint` - PowerPoint presentation generation

**Social & Media:**
- `applications.linkedin` - LinkedIn profile and company data
- `applications.youtube` - YouTube data and analytics
- `applications.instagram` - Instagram integration
- `applications.spotify` - Spotify music data

**Platforms & Services:**
- `applications.naas` - Naas.ai platform integration
- `applications.nebari` - Nebari platform integration
- `applications.salesforce` - Salesforce CRM integration
- `applications.hubspot` - HubSpot CRM integration
- `applications.zoho` - Zoho suite integration
- `applications.mercury` - Mercury platform integration
- `applications.sanax` - Sanax integration

**Data Sources:**
- `applications.datagouv` - French open data portal
- `applications.worldbank` - World Bank data
- `applications.openweathermap` - Weather data API
- `applications.openrouter` - OpenRouter API integration

**Usage Example:**

```python
from naas_abi_core.engine.Engine import Engine

engine = Engine()
engine.load(module_names=["naas_abi_marketplace.applications.github"])

# Access GitHub agent
from naas_abi_marketplace.applications.github.agents.GitHubAgent import create_agent

agent = create_agent()
response = agent.invoke("List open issues in repository jupyter-naas/abi")
```

### Domain Expert Modules

Specialized agents designed for specific professional roles and tasks.

#### Available Domain Experts

**Engineering & Development:**
- `domains.software-engineer` - Software engineering expertise
- `domains.devops-engineer` - DevOps and infrastructure
- `domains.data-engineer` - Data engineering and pipelines

**Business & Sales:**
- `domains.account-executive` - Account management
- `domains.business-development-representative` - Business development
- `domains.sales-development-representative` - Sales development
- `domains.inside-sales-representative` - Inside sales operations

**Marketing & Content:**
- `domains.content-creator` - Content creation
- `domains.content-strategist` - Content strategy
- `domains.content-analyst` - Content analysis
- `domains.campaign-manager` - Campaign management
- `domains.community-manager` - Community management

**Finance & Accounting:**
- `domains.accountant` - Accounting expertise
- `domains.financial-controller` - Financial control
- `domains.treasurer` - Treasury management

**Management & Operations:**
- `domains.project-manager` - Project management
- `domains.customer-success-manager` - Customer success
- `domains.human-resources-manager` - HR management

**Research & Investigation:**
- `domains.osint-researcher` - Open source intelligence
- `domains.private-investigator` - Investigation services

**Support:**
- `domains.support` - Technical support and issue management

**Usage Example:**

```python
from naas_abi_core.engine.Engine import Engine

engine = Engine()
engine.load(module_names=["naas_abi_marketplace.domains.software-engineer"])

# Access Software Engineer agent
from naas_abi_marketplace.domains.software_engineer.agents.SoftwareEngineerAgent import create_agent

agent = create_agent()
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
  
  - module: naas_abi_marketplace.ai.claude
    enabled: true
    config:
      anthropic_api_key: "${ANTHROPIC_API_KEY}"
  
  # Applications
  - module: naas_abi_marketplace.applications.github
    enabled: true
    config:
      github_token: "${GITHUB_TOKEN}"
  
  - module: naas_abi_marketplace.applications.linkedin
    enabled: true
    config:
      linkedin_api_key: "${LINKEDIN_API_KEY}"
  
  # Domain Experts
  - module: naas_abi_marketplace.domains.software-engineer
    enabled: true
  
  - module: naas_abi_marketplace.domains.support
    enabled: true
```

### Soft Dependencies

Many modules are marked as "soft" dependencies, meaning they're optional and won't cause failures if unavailable:

```python
# In naas_abi module dependencies
modules=[
    "naas_abi_marketplace.ai.claude#soft",  # Optional
    "naas_abi_marketplace.applications.github#soft",  # Optional
]
```

## Usage Patterns

### Loading Multiple Modules

```python
from naas_abi_core.engine.Engine import Engine

engine = Engine()
engine.load(module_names=[
    "naas_abi_marketplace.ai.chatgpt",
    "naas_abi_marketplace.ai.claude",
    "naas_abi_marketplace.applications.github",
    "naas_abi_marketplace.domains.software-engineer"
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

