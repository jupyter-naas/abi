# CLI Reference

The `abi` CLI is the unified command-line interface for managing your ABI stack.

---

## Installation

The CLI is part of the `naas-abi-cli` package and is installed automatically with the monorepo:

```bash
uv sync --all-extras
```

Verify:

```bash
abi --help
```

---

## abi stack

Manage local Docker services.

```bash
abi stack start          # Start all services (Fuseki, Postgres, RabbitMQ, MinIO, ...)
abi stack stop           # Stop all services
abi stack status         # Health check with per-service readiness probe
abi stack logs           # Stream logs from all services
abi stack logs api       # Stream logs from the API service
abi stack tui            # Open interactive terminal UI for service inspection
```

`abi stack status` probes each service for readiness (TCP/HTTP) rather than relying on Docker container status. A container can be "running" but not yet accepting connections - `status` tells you when it is actually ready.

---

## abi chat

Start a terminal agent session.

```bash
abi chat                         # Chat with the default ABI supervisor agent
abi chat --agent my_agent        # Chat with a specific agent by name
abi chat --thread 42             # Continue conversation thread 42
```

---

## abi deploy

Deploy ABI to a remote environment.

```bash
abi deploy --env production      # Deploy using config.production.yaml
abi deploy --env staging
```

---

## Makefile targets (legacy)

Many operations are also available as `make` targets. These are lower-level than the CLI but useful in CI/CD pipelines:

```bash
# API
make api                   # Start API dev server (port 9879)
make mcp                   # Start MCP server for Claude Desktop (STDIO)
make mcp-http              # Start MCP server in HTTP mode (port 8000)

# Knowledge graph
make sparql-terminal       # Interactive SPARQL query terminal
make oxigraph-admin        # Oxigraph database admin (if using Oxigraph)

# Data sync
make datastore-pull        # Pull datastore from remote
make datastore-push        # Push local changes to remote
make triplestore-export-turtle  # Export triple store to Turtle file

# Dagster
make dagster-dev           # Start Dagster dev server
make dagster-ui            # Open Dagster web UI

# Code quality
make test                  # Run all tests
make check                 # Run linting and type checks
make fmt                   # Format code with ruff

# Publishing
make publish-remote-agents          # Publish agents to naas.ai workspace
make publish-remote-agents-dry-run  # Preview publishing without executing
```
