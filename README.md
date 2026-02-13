<div align="center">
<img src="libs/naas-abi/naas_abi/apps/nexus/apps/web/public/abi-logo-rounded.png" alt="ABI Logo" width="128" height="128">

# ABI
*Agentic Brain Infrastructure*
</div>

<div align="center">

[![Version](https://img.shields.io/badge/version-ABI--OS1%20Beta-red.svg)](https://github.com/jupyter-naas/abi/releases)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-00a393.svg)](https://fastapi.tiangolo.com/)


[![GitHub Stars](https://img.shields.io/github/stars/jupyter-naas/abi?style=social)](https://github.com/jupyter-naas/abi/stargazers)
[![GitHub Forks](https://img.shields.io/github/forks/jupyter-naas/abi?style=social)](https://github.com/jupyter-naas/abi/network/members)
[![Contributors](https://img.shields.io/github/contributors/jupyter-naas/abi.svg)](https://github.com/jupyter-naas/abi/graphs/contributors)

</div>

> Multi-agent AI Operating System with semantic knowledge graphs, ontology-driven reasoning, and intelligent workflow automation.

⭐ **Star and follow to stay updated!**

## Quick Start

### Prerequisites
```bash
# Install uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install Docker Desktop (for local services)
# https://www.docker.com/products/docker-desktop
```

### Local Development
```bash
# Clone repository
git clone https://github.com/jupyter-naas/abi.git
cd abi

# Install dependencies
uv sync --all-extras

# Create local config
cp config.yaml.example config.yaml
# Edit config.yaml with your API keys

# Start platform
uv run abi stack start
```

**Platform will launch at:**
- 🌐 **Nexus UI**: http://localhost:3000
- 📊 **Nexus API**: http://localhost:9879
- 🤖 **Agent API**: http://localhost:8001
- 🗄️ **Fuseki**: http://localhost:3030

### CLI Commands
```bash
uv run abi stack start         # Start all services
uv run abi stack stop          # Stop all services
uv run abi stack status        # Show service health
uv run abi stack logs [svc]    # Stream BFO logs (api|web|core|all)
uv run abi seed-jena           # Populate graph database
uv run abi chat                # Interactive agent chat
```

### Configuration

**Minimal config (loads AbiAgent only):**
```yaml
modules:
  - module: naas_abi
    enabled: true
  - module: naas_abi_core.modules.templatablesparqlquery
    enabled: true
  - module: naas_abi_marketplace.ai.chatgpt
    enabled: true

services:
  triple_store:
    triple_store_adapter:
      adapter: "apache_jena_tdb2"
      config:
        jena_tdb2_url: "http://admin:abi@localhost:3030/ds"
```

## Architecture

**Four-Layer AI Operating System:**

1. **User Layer**: Chat UI, REST API, MCP Protocol
2. **Agent Layer**: ABI SuperAssistant + 20+ domain experts
3. **Storage Layer**: Knowledge Graph (Jena/Oxigraph), Vector DB (Qdrant), Memory (PostgreSQL)
4. **Execution Layer**: Ontologies (BFO), Workflows, Integrations, Analytics

```mermaid
graph LR
    USER[👤 User] --> APPS[📱 Apps]
    APPS --> AGENTS[🧠 Agents]
    AGENTS --> STORAGE[(💾 Storage)]
    AGENTS --> EXEC[⚙️ Components]
    STORAGE --> KG[(Knowledge Graph)]
    STORAGE --> VDB[(Vector DB)]
    EXEC --> ONT[Ontologies]
    EXEC --> WF[Workflows]
```

## Key Features

### 🤖 Multi-Model AI
- **Cloud**: ChatGPT, Claude, Gemini, Grok, Llama, Mistral
- **Local**: Qwen, DeepSeek, Gemma (via Ollama)
- **Supervisor**: ABI agent with intelligent routing

### 🧠 Knowledge Management
- **Semantic Graph**: BFO-compliant RDF ontologies
- **SPARQL Queries**: 30+ optimized queries
- **Vector Search**: Intent matching via embeddings
- **Memory**: Persistent conversation context

### 🏪 Marketplace
- **Domain Experts**: 20+ agents (Engineer, Analyst, Creator, etc.)
- **Integrations**: GitHub, LinkedIn, Google, PostgreSQL, ArXiv, etc.
- **Modular**: Enable/disable via `config.yaml`

### ⚙️ Automation
- **Workflows**: End-to-end process automation
- **Pipelines**: Data → Semantic transformation
- **Event-Driven**: Knowledge graph triggers
- **Integrations**: External APIs and exports

### 🌐 Multiple Interfaces
- **Terminal**: `uv run abi chat` - Interactive CLI
- **REST API**: HTTP endpoints
- **MCP Protocol**: Claude Desktop / VS Code
- **Web UI**: http://localhost:3000

### Production Deployment

### Deploy to Naas Cloud
```bash
uv run abi deploy naas
```
Requires [Naas subscription](https://naas.ai). Deploys as containerized API at `https://{space}.default.space.naas.ai`

### Self-Hosted Docker
```bash
docker-compose up -d
```
Full stack with PostgreSQL, Fuseki, Qdrant, MinIO

## Services

| Service | Port | Purpose |
|---------|------|---------|
| Nexus Web | 3000 | Frontend UI |
| Nexus API | 9879 | Platform API |
| Agent API | 8001 | Agent execution |
| Fuseki | 3030 | Graph database |
| PostgreSQL | 5432 | Relational DB |
| Qdrant | 6333 | Vector DB |
| MinIO | 9000/9001 | Object storage |

## Why ABI?

**Ontology-Based AI for Freedom to Reason**: When semantic alignment meets kinetic action through ontology-driven systems, we get one of the most powerful technologies ever created. This power should be distributed, not concentrated - the ability to understand, reason, and act upon complex information is fundamental to human autonomy and democratic society.

**Built on International Standards:**
- [ISO/IEC 42001:2023](https://www.iso.org/standard/42001) - AI Management Systems
- [ISO/IEC 21838-2:2021](https://www.iso.org/standard/74572.html) - Basic Formal Ontology (BFO)
- EU AI Act compliance-ready

**For:**
- 👤 **Individuals**: Run locally, own your data
- ⚡ **Pro**: Automate workflows, optimize costs
- 👥 **Teams**: Share knowledge, build agents
- 🏢 **Enterprise**: Deploy at scale, full control

## Research & Development

Collaborative effort between:
- **[NaasAI](https://naas.ai)** - Applied AI Research Lab
- **[OpenTeams](https://openteams.com/)** - Open SaaS Infrastructure
- **[University at Buffalo](https://www.buffalo.edu/)** - Research University
- **[NCOR](https://ncor.buffalo.edu/)** - National Center for Ontological Research
- **[Forvis Mazars](https://www.forvismazars.com/)** - Global Audit & Consulting

## Requirements

**System:**
- Python 3.10+
- uv package manager
- Git

**Hardware (Minimal - Cloud AI):**
- 2GB+ RAM
- 500MB disk

**Hardware (Full - Local/Docker):**
- 8GB+ RAM
- 10GB+ disk
- Docker Desktop

**API Keys (at least one):**
- OpenAI, Anthropic, Google AI, OpenRouter, or other LLM providers

## Contributing

We welcome contributions! See [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](https://opensource.org/licenses/MIT)

For enterprise support: support@naas.ai
