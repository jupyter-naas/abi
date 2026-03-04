# NEXUS

Enterprise AI agent platform with knowledge graphs, semantic search, and multi-LLM support.

## Prerequisites

- **Docker** (for PostgreSQL) — [Get Docker](https://docs.docker.com/get-docker/)
- **Node.js 18+** — [nodejs.org](https://nodejs.org/)
- **pnpm 8.15+** — `npm install -g pnpm`
- **Python 3.11+** & **uv** — [docs.astral.sh/uv](https://docs.astral.sh/uv/)

## Quick Start

```bash
git clone https://github.com/jravenel/nexus.git && cd nexus
make install && make db-up && make db-migrate && make db-seed && make up
```

→ **http://localhost:3000/auth/login** · `alice@example.com` / `nexus2026`

## Features

- **Multi-LLM Chat** — GPT-4, Claude, Mistral, Ollama, custom ABI servers
- **Knowledge Graph** — RDF/Turtle ontologies, SPARQL queries
- **Multi-tenancy** — Organizations, workspaces, RBAC
- **Streaming** — Real-time SSE responses

## Commands

```bash
make help        # Show all commands
make install     # Install dependencies
make up          # Start dev servers
make test        # Run tests
make db-reset    # Reset database
```

## Documentation

- [Quick Start](docs/START.md) — 2-minute setup
- [Essentials](docs/ESSENTIALS.md) — One-page reference
- [API](docs/API.md) — All endpoints
- [Deployment](docs/DEPLOYMENT.md) — Production guide
- [Troubleshooting](docs/TROUBLESHOOTING.md) — Common issues

## Roadmap

1. Provider adapter pattern (protocol-agnostic hub)
2. Files & RAG (upload, embeddings, semantic search)
3. Database backups & indexes
4. 80%+ test coverage
5. Agent marketplace (discover/share)

## Tech Stack

**Frontend:** Next.js 14, TypeScript, Tailwind, Zustand  
**Backend:** FastAPI, Python 3.11, PostgreSQL 16  
**AI:** OpenAI, Anthropic, Ollama, custom providers  
**Ontology:** BFO (ISO 21383-2), RDF/Turtle, SPARQL

## Local AI (Ollama)

NEXUS can use a local Ollama server for on-device models (e.g., `qwen3-vl:2b`).

- Autostart is opt-in and local-only.
- To enable in local development, add to `apps/api/.env`:

```env
ENABLE_OLLAMA_AUTOSTART=true
ENVIRONMENT=development
```

If disabled (default), the API will only report Ollama status without starting it.
Install Ollama separately: https://ollama.ai

## License

MIT — Copyright (c) 2026 naas.ai  
→ [CONTRIBUTING.md](CONTRIBUTING.md) · [SECURITY.md](SECURITY.md)
