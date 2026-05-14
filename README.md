<div align="center">
<img src="libs/naas-abi/naas_abi/apps/nexus/apps/web/public/abi-logo-rounded.png" alt="ABI Logo" width="128" height="128">

# ABI

_Question Everything, Create your own AI System_

ABI (Agentic Brain Infrastructure) is the open-source AI Operating System that grounds LLMs in your organization's ontology to create tools that extend human capabilities. An open and accessible alternative to Palantir.

</div>

<div align="center">

[![Version](https://img.shields.io/badge/version-ABI--OS1%20Beta-red.svg)](https://github.com/jupyter-naas/abi/releases)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-00a393.svg)](https://fastapi.tiangolo.com/)

[![GitHub Stars](https://img.shields.io/github/stars/jupyter-naas/abi?style=social)](https://github.com/jupyter-naas/abi/stargazers)
[![GitHub Forks](https://img.shields.io/github/forks/jupyter-naas/abi?style=social)](https://github.com/jupyter-naas/abi/network/members)
[![Contributors](https://img.shields.io/github/contributors/jupyter-naas/abi.svg)](https://github.com/jupyter-naas/abi/graphs/contributors)

</div>

## Quick Start

### Prerequisites

- Python 3.12+, Git, [uv](https://astral.sh/uv) (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- [Docker Desktop](https://www.docker.com/products/docker-desktop) (8GB+ RAM for full stack)
- LLMs API key: OpenAI and OpenRouter

You also need to have the `docker` command available in your terminal.

### Get started

```bash
uv tool install naas-abi-cli --force --upgrade

abi new project my_ai   # replace "my_ai" with your project name
cd my_ai
abi start
```

**Web UI** — http://localhost:3042 (login: `admin@example.com` / `Admin1234!`)

<div align="center">
  <img src="docs/site/static/abi/Screenshot_Local_WebUI.png" alt="ABI web UI" width="800">
</div>

**API** — http://localhost:9879/docs

<div align="center">
  <img src="docs/site/static/abi/Screenshot_Local_API.png" alt="ABI API docs" width="800">
</div>

**CLI** — `abi chat` for a terminal conversation

<div align="center">
  <img src="docs/site/static/abi/Screenshot_Local_CLI.png" alt="ABI CLI" width="800">
</div>

### CLI Commands

```bash
abi start            # Start all services
abi stop             # Stop all services
abi chat             # Interactive agent chat
abi config validate  # Validate the configuration
```

## How It Works

Connect your data sources, build domain agents grounded in your organization's ontology, and route every question to the right model or expert agent through a knowledge graph you own and control.

Full architecture: [The ABI Stack](https://docs.naas.ai/architecture/the-stack)

## Repository Layout

| Package                | What it does                                                     |
| ---------------------- | ---------------------------------------------------------------- |
| `naas-abi-core`        | Infrastructure adapters: storage, vector DB, message bus, SPARQL |
| `naas-abi`             | Core agents, ontologies, and the Nexus app (API + web UI)        |
| `naas-abi-cli`         | The `abi` CLI                                                    |
| `naas-abi-marketplace` | Optional domain agents and third-party integrations              |

## Production Deployment

### Self-Hosted Docker

```bash
docker compose up -d
```

Full stack with PostgreSQL, Fuseki, Qdrant, MinIO

### Managed Hosting

Need a hosted, managed deployment? [Get started on naas.ai](https://naas.ai) or reach out to the team directly.

## Why ABI?

Most AI tools are black boxes. ABI is built on open standards so every decision is traceable, every model is replaceable, and you own your data.

**Built on international standards:**

- [ISO/IEC 42001:2023](https://www.iso.org/standard/42001) - AI Management Systems
- [ISO/IEC 21838-2:2021](https://www.iso.org/standard/74572.html) - Basic Formal Ontology (BFO)
- EU AI Act compliance-ready

## Research & Development

Collaborative effort between:

- **[NaasAI](https://naas.ai)** - Applied AI Research Lab
- **[OpenTeams](https://openteams.com/)** - Open SaaS Infrastructure
- **[University at Buffalo](https://www.buffalo.edu/)** - Research University
- **[NCOR](https://ncor.buffalo.edu/)** - National Center for Ontological Research
- **[Forvis Mazars](https://www.forvismazars.com/)** - Global Audit & Consulting

⭐ **If ABI is useful to you, star the repo to help others find it.**

## Contributing

We welcome contributions. Open an issue or pull request to get started.

## License

MIT License - see [LICENSE](https://opensource.org/licenses/MIT)

For enterprise support or managed hosting, visit [naas.ai](https://naas.ai).
