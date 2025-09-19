# Get Started

**Table of Contents**

- [Get Started](#get-started)
  - [Introduction](#introduction)
    - [What is ABI?](#what-is-abi)
    - [Why ABI?](#why-abi)
    - [Key Features](#key-features)
    - [Key Capabilities](#key-capabilities)
  - [Installation](#installation)
    - [Pre-requisites](#pre-requisites)
    - [Installation Options](#installation-options)
    - [Automated Setup](#automated-setup)
    - [Manual Configuration (Advanced)](#manual-configuration-advanced)
  - [Quickstart](#quickstart)
    - [One-Command Start](#one-command-start)
    - [Alternative Agents](#alternative-agents)
    - [AI Mode Selection](#ai-mode-selection)
    - [Quick Commands Reference](#quick-commands-reference)
    - [Troubleshooting](#troubleshooting)
  - [Advanced Usage](#advanced-usage)
    - [Development \& API](#development--api)
    - [Data Management](#data-management)
    - [Orchestration \& Monitoring](#orchestration--monitoring)
    - [Testing \& Quality Assurance](#testing--quality-assurance)
    - [Package Management](#package-management)
    - [Documentation \& Publishing](#documentation--publishing)
    - [Environment URLs](#environment-urls)
    - [Module System](#module-system)
  - [Help \& Support](#help--support)

## Introduction

### What is ABI?

The **ABI** (Agent Based Intelligence) project is a Python-based backend framework designed to serve as the core infrastructure for building an Agentic AI Ontology Engine. This system empowers organizations to integrate, manage, and scale AI-driven operations with a focus on ontology, agent-driven workflows, and analytics. Designed for flexibility and scalability, ABI provides a customizable framework suitable for organizations aiming to create intelligent, automated systems tailored to their needs.

### Why ABI?
The **ABI** project aims to provide a open alternative to Palantir by offering a flexible and scalable framework for building intelligent systems using ontology. Unlike Palantir, which is often seen as a monolithic solution, ABI emphasizes modularity and customization, allowing organizations to tailor their AI-driven operations to specific needs. Combined with the Naas.ai ecosystem, ABI can be used to build the brain of your organization's agentic AI applications.

### Key Features

- **Agents**: Configurable AI agents (also named agents) to handle specific organizational tasks and interact with users.
- **Flexible Tools**: Agents with custom tools to interact with external services and data sources (Integrations, Pipelines, Workflows, Analytics)
- **Ontology Based**: Ontologies are used to convert data into knowledge to create a flexible and scalable system.
- **Storage**: Storage system is managing unstructured data in datastore, knowledge graph in triple_store and vector data in vectorstore. It is also designed to manage local and remote data storage seamlessly.
- **Customizable API**: All components can be deployed in an API and use externally by other applications.

### Key Capabilities

- **Event-Driven**: Actions can be triggered by events logged in the triple store.
- **Deterministic Queries**: Deterministic SPARQL queries can be added to the ontology to used by the agents as tools without having to create any python code.
- **Scheduling Tasks**: Tasks can be pre-processed and scheduled to avoid latency.
- **Multi-models**: This project is model agnostic with built-in support for major LLM providers including OpenAI, Anthropic, Google, Meta, and Mistral. You can use any LLM you want in your agents or workflows.

## Installation

Get started with ABI - Install, configure and chat with your first agent.

### Pre-requisites

- **Install [Docker Desktop](https://www.docker.com/products/docker-desktop/)** - Required for running Oxigraph and other services
- **Install [uv](https://docs.astral.sh/uv/getting-started/installation/)** - Python package manager
- **Create your account on [NAAS](https://naas.ai)** (Optional, only if you want to use the storage system in production)

### Installation Options

Choose one of the following options:

1. **Clone the Repository**
```bash
git clone https://github.com/jupyter-naas/abi.git
cd abi
```

2. **Fork the Repository**
```bash
# 1. Fork via GitHub UI
# 2. Clone your fork
git clone https://github.com/YOUR-USERNAME/abi.git
cd abi
```

3. **Create a Private Fork**
```bash
# 1. Create private repository via GitHub UI
# 2. Clone your private repository
git clone https://github.com/YOUR-USERNAME/abi-private.git
cd abi-private
git remote add upstream https://github.com/jupyter-naas/abi.git
git pull --rebase upstream main
git push
```

### Automated Setup

ABI now features an **automated setup process** that guides you through the initial configuration. Simply run:

```bash
make
```

This will:
1. **Install Dependencies** - Automatically set up uv, Python 3.10, and all required packages
2. **Interactive Setup** - Guide you through personal information and preferences
3. **AI Mode Selection** - Choose between local (privacy-focused) or cloud (more powerful) AI
4. **Service Configuration** - Automatically start local services (Oxigraph, PostgreSQL, Dagster)
5. **Module Configuration** - Scan available modules and configure API keys as needed
6. **Start ABI Agent** - Launch the main conversational AI interface

The setup process is interactive and will ask you for:
- **Personal Information**: Your name and email for personalization
- **AI Mode**: Choose local (privacy) or cloud (performance) AI processing
- **API Keys**: Optional keys for enhanced features and modules
- **Module Preferences**: Enable/disable specific functionality modules

### Manual Configuration (Advanced)

If you prefer manual configuration, you can still use the traditional approach:

1. **Environment Setup**
```bash
cp .env.example .env
# Edit .env with your credentials
```

2. **YAML Configuration**
```bash
cp config.yaml.example config.yaml
# Edit config.yaml with your settings
```

**Available AI Models**: ABI supports multiple LLM providers. Configure the API keys for the models you want to use:
- `OPENAI_API_KEY` - For GPT-4o and other OpenAI models
- `ANTHROPIC_API_KEY` - For Claude 3.5 Sonnet model
- `GOOGLE_API_KEY` - For Gemini models
- `MISTRAL_API_KEY` - For Mistral models

**Configuration Parameters**:
- `workspace_id`: Naas Platform workspace ID for storage and publishing
- `github_repository`: Your repository name (e.g. "jupyter-naas/abi")
- `github_project_id`: GitHub project number for issue management
- `triple_store_path`: Path to the ontology store (e.g. "storage/triplestore")
- `api_title`: API title displayed in documentation
- `api_description`: API description for documentation
- `logo_path`: Path to logo for API documentation
- `favicon_path`: Path to favicon for API documentation

## Quickstart

### One-Command Start

The simplest way to get started is with the automated setup:

```bash
make
```

This single command handles everything: dependencies, configuration, services, and starts the ABI agent.

### Alternative Agents

After initial setup, you can start different specialized agents:

**Main Agents:**
```bash
make                        # Default ABI agent (automated setup)
make chat-abi-agent        # Main ABI agent (direct start)
make chat-naas-agent       # Naas platform integration agent
make chat-support-agent    # Customer support specialized agent
```

**Local AI Agents (Privacy-focused):**
```bash
make chat-qwen-agent       # Qwen3 8B - Multilingual coding assistant
make chat-deepseek-agent   # DeepSeek R1 8B - Advanced reasoning
make chat-gemma-agent      # Gemma3 4B - Lightweight and fast
```

### AI Mode Selection

During setup, you'll choose between two AI processing modes:

**🔒 Local Mode (Privacy-focused)**
- All AI processing happens on your machine
- Requires [Ollama](https://ollama.com/download) installation
- Uses models like Qwen3 8B, DeepSeek R1, Gemma3
- Complete data privacy and offline capabilities
- Slower processing but fully autonomous

**☁️ Cloud Mode (Performance-focused)**
- Uses cloud AI providers (OpenAI, Anthropic, Google, etc.)
- Requires API keys for chosen providers
- Faster and more powerful AI capabilities
- Data is sent to third-party services
- Better for complex reasoning and analysis

### Quick Commands Reference

**Start Services:**
```bash
make local-up              # Start all local services
make local-down            # Stop all local services
make local-logs            # View service logs
```

**Development Tools:**
```bash
make api                   # Start API server (port 9879)
make mcp                   # Start MCP server for Claude Desktop
make sparql-terminal       # Interactive SPARQL query terminal
make oxigraph-explorer     # Open Knowledge Graph web interface
```

**Testing & Quality:**
```bash
make test                  # Run all tests
make check                 # Run code quality checks
make help                  # Show all available commands
```

### Troubleshooting

If you encounter issues during startup:

1. **Docker Issues:**
```bash
make docker-cleanup        # Clean up Docker conflicts
make local-up              # Restart services
```

2. **Service Connection Issues:**
```bash
make oxigraph-status       # Check Oxigraph status
make local-logs            # View service logs
```

3. **Local AI Setup (Ollama):**
```bash
# Install Ollama: https://ollama.com/download
ollama run qwen3:8b        # Pull and run local AI model
```

The first startup may take a few minutes as it downloads Docker containers and AI models.

## Advanced Usage

### Development & API

**API Server:**
```bash
make api                   # Local development API (port 9879)
make api-prod              # Production API in Docker
make api-local             # Local API with Docker volume mounting
```

**MCP (Model Context Protocol):**
```bash
make mcp                   # STDIO mode for Claude Desktop integration
make mcp-http              # HTTP mode on port 8000
make mcp-test              # Run MCP validation tests
```

### Data Management

**Knowledge Graph Operations:**
```bash
make sparql-terminal       # Interactive SPARQL query interface
make oxigraph-admin        # Oxigraph database administration
make oxigraph-explorer     # Web-based knowledge graph explorer
```

**Data Synchronization:**
```bash
make datastore-pull        # Pull datastore from remote
make datastore-push        # Push local changes to remote
make storage-pull          # Pull storage data
make storage-push          # Push storage changes
```

**Triplestore Operations:**
```bash
make triplestore-export-excel    # Export to Excel format
make triplestore-export-turtle   # Export to Turtle/RDF format
make triplestore-prod-pull       # Pull from production environment
make triplestore-prod-override   # Override production with local data
```

### Orchestration & Monitoring

**Dagster (Data Orchestration):**
```bash
make dagster-dev           # Start Dagster development server
make dagster-up            # Start Dagster in background
make dagster-down          # Stop Dagster service
make dagster-ui            # Open Dagster web interface
make dagster-status        # Check asset status
make dagster-materialize   # Execute all assets
```

**Service Management:**
```bash
make local-up              # Start all services (Oxigraph, PostgreSQL, Dagster)
make local-down            # Stop and remove all services
make local-stop            # Stop services without removing
make local-logs            # View all service logs
make oxigraph-up           # Start only Oxigraph
make oxigraph-down         # Stop only Oxigraph
```

### Testing & Quality Assurance

**Testing:**
```bash
make test                  # Run all tests
make test-abi              # Test abi library specifically
make test-api              # Test API functionality
make ftest                 # Interactive test selector with fuzzy finder
```

**Code Quality:**
```bash
make check                 # Run all quality checks
make check-core            # Check core modules
make check-custom          # Check custom modules
make check-marketplace     # Check marketplace modules
make fmt                   # Format code with ruff
make bandit                # Security scanning
```

### Package Management

**Dependencies:**
```bash
make add dep=package-name  # Add dependency to main project
make abi-add dep=package   # Add dependency to abi library
make lock                  # Update dependency lock files
```

**Docker:**
```bash
make build                 # Build Docker image
make local-build           # Build all containers
make trivy-container-scan  # Security scan containers
```

### Documentation & Publishing

**Documentation:**
```bash
make docs-ontology         # Generate ontology documentation
make help                  # Show comprehensive help
```

**Publishing:**
```bash
make publish-remote-agents # Publish agents to workspace
make publish-remote-agents-dry-run # Preview publishing
make pull-request-description      # Generate PR description with AI
```

### Environment URLs

When services are running, access them at:

- **Oxigraph (Knowledge Graph)**: http://localhost:7878
- **YasGUI (SPARQL Editor)**: http://localhost:3000  
- **PostgreSQL (Agent Memory)**: localhost:5432
- **Dagster (Orchestration)**: http://localhost:3001
- **API Server**: http://localhost:9879
- **MCP HTTP Server**: http://localhost:8000

### Module System

ABI uses a modular architecture with components in:
- `src/core/` - Core ABI functionality
- `src/custom/` - Custom organizational modules
- `src/marketplace/` - Community and third-party modules

Each module can contain:
- **Agents** - Conversational AI interfaces
- **Integrations** - External service connections
- **Pipelines** - Data processing workflows
- **Workflows** - Business logic automation
- **Ontologies** - Knowledge graph schemas

Modules are automatically discovered and can be enabled/disabled during setup based on available API keys and requirements.

## Help & Support
For any questions or support requests, please create an issue on this repository or reach out via [support@naas.ai](mailto:support@naas.ai).


