---
sidebar_position: 1
---

# Quickstart

Get a running ABI stack in under 10 minutes.

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) - required for local services
- [uv](https://docs.astral.sh/uv/getting-started/installation/) - Python package manager
- An [OpenRouter API key](https://openrouter.ai) - optional but recommended for cloud models. Skip for local-only mode.

---

## 1) Clone and install

```bash
git clone https://github.com/jupyter-naas/abi.git
cd abi

# Install all dependencies
uv sync --all-extras
uv pip install greenlet
```

---

## 2) Configure

```bash
# Copy the example config
cp config.yaml.example config.yaml
cp .env.example .env
```

Edit `.env` and set at minimum:

```bash
# Cloud mode (recommended for full capability)
OPENROUTER_API_KEY=sk-or-...

# Local mode (no internet, no API key required)
# Set ai_mode: "local" in config.yaml instead, and install Ollama
```

---

## 3) Start the stack

```bash
abi stack start
```

This starts all Docker services (Fuseki, PostgreSQL, RabbitMQ, MinIO) and confirms readiness before returning. Check status at any time:

```bash
abi stack status
```

---

## 4) Chat with ABI

```bash
abi chat
```

This launches the terminal agent. Type a question - ABI will route it to the correct specialized agent.

Or start the API server:

```bash
uv run python -m naas_abi_core.apps.api.api
```

Then open:
- `http://localhost:9879/` - Nexus web app
- `http://localhost:9879/docs` - API documentation (Swagger)
- `http://localhost:9879/redoc` - API documentation (Redoc)

---

## AI mode: cloud vs. local

**Cloud mode** (default): uses OpenRouter to access GPT-4o, Claude 3.5 Sonnet, Gemini 2.0, and others. Requires `OPENROUTER_API_KEY`.

**Local mode**: all AI processing runs on your machine via Ollama. No data leaves your network.

```bash
# Install Ollama: https://ollama.com/download
ollama pull qwen3:8b   # or deepseek-r1:8b or gemma3:4b
```

Set in `config.yaml`:

```yaml
global_config:
  ai_mode: "local"
```

---

## Useful commands

```bash
# Service management
abi stack start          # Start all services
abi stack stop           # Stop all services
abi stack status         # Health check
abi stack logs api       # Stream API logs

# Development
make api                 # Start API server (port 9879)
make mcp                 # Start MCP server for Claude Desktop
make sparql-terminal     # Interactive SPARQL query terminal

# Data
make datastore-pull      # Pull datastore from remote
make datastore-push      # Push local changes to remote

# Testing
make test                # Run all tests
make check               # Code quality checks
```

---

## Service URLs (when running)

| Service | URL | Purpose |
|---------|-----|---------|
| ABI API | http://localhost:9879 | REST API + Nexus web |
| Fuseki SPARQL | http://localhost:3030 | Knowledge graph admin |
| Dagster | http://localhost:3001 | Orchestration UI |
| MCP server | http://localhost:8000 | Model Context Protocol |
| Qdrant | http://localhost:6333 | Vector store admin |

Next: [[getting-started/configuration|Configuration Reference]] or [[building/creating-a-module|Build your first module]].
