# Apps

## Overview

ABI ships with four built-in user interfaces that cover the primary interaction modes. All UIs are started with `make local-up` or `uv run abi stack start` and served through Caddy as the reverse proxy.

Access all interfaces through the **Service Portal** at http://localhost:8080.

---

## Built-in Interfaces

### Nexus Web UI
**URL:** http://localhost:3042

The primary analyst and user interface. Built with React/Next.js. Provides:
- Conversational AI interface to all registered agents
- Workspace management
- Knowledge graph browsing
- Module and agent configuration

Backend API runs on http://localhost:9879.

---

### YasGUI — SPARQL Workbench
**URL:** http://localhost:3000

A browser-based SPARQL query editor connected to the Jena/Fuseki triple store. Use this to:
- Run ad hoc SPARQL queries against the knowledge graph
- Explore ontology structure and populated instances
- Debug pipeline outputs directly in the graph
- Export query results as CSV, JSON, or RDF

For terminal-based SPARQL queries, use `make sparql-terminal`.

---

### Element — Matrix Client
**URL:** http://localhost:8081

A web-based Matrix client connected to the local Synapse server. Use this for:
- Multi-user collaboration workspaces
- Federated messaging across ABI nodes
- Team communication tied to the same infrastructure

Matrix/Synapse server runs on http://localhost:8008.

---

### CLI — Terminal Agent Interface

The fastest way to interact with ABI agents without starting Docker services:

```bash
# Start the main ABI agent
make chat-abi-agent

# Other available agents
make chat-naas-agent
make chat-support-agent
make chat-ontology-agent

# Local (air-gapped) models via Ollama
make chat-qwen-agent      # Qwen3 8B
make chat-deepseek-agent  # DeepSeek R1 8B
make chat-gemma-agent     # Gemma3 4B
```

---

### MCP Server — Claude Desktop / VS Code Integration
**HTTP URL:** http://localhost:8000

Exposes all ABI agents as MCP tools. Supports two transport modes:

```bash
make mcp        # STDIO mode — for Claude Desktop integration
make mcp-http   # HTTP mode — for remote or VS Code integration
```

See [MCP Integration](../distribution/devops/mcp.md) for Claude Desktop setup.

---

## Adding Custom Apps to a Module

Custom UIs can be added to any module. ABI does not enforce a specific framework. Any Python app that imports your module's workflows and integrations works.

**Recommended frameworks:**
- **Streamlit** — fast dashboards and data apps
- **Gradio** — ML demo interfaces
- **Click** — CLI apps
- **FastAPI** — REST APIs exposed via `as_api()` on workflows/pipelines

**Module structure:**
```
your_module/
├── apps/
│   ├── streamlit/app.py
│   ├── cli/cli.py
│   └── assets/
├── workflows/
├── pipelines/
└── integrations/
```

**Best practices:**
- Keep business logic in workflows and pipelines — not in the UI layer
- Use `secret.get("KEY")` for credentials, never hardcode them in app files
- Register custom API routes via the `as_api()` method on your workflow or pipeline class
- For scheduled data collection, use Dagster orchestration rather than a background thread in the app
