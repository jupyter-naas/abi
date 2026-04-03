# The ABI Stack

ABI is organized as four focused Python packages, each with a specific responsibility.

Related pages: [[concepts/what-is-abi|What is ABI?]], [[libs/naas-abi-core/Architecture|Architecture]], [[adr/20251130_python-monorepo-libs-split|ADR: Monorepo Split]].

---

## The four packages

```
┌─────────────────────────────────────────────────────────────┐
│  naas-abi-cli          abi stack / abi chat / abi deploy    │
├─────────────────────────────────────────────────────────────┤
│  naas-abi              Agents · Nexus · Pipelines · Modules │
│  naas-abi-marketplace  Community integrations and agents    │
├─────────────────────────────────────────────────────────────┤
│  naas-abi-core         Engine · Services · Module runtime   │
└─────────────────────────────────────────────────────────────┘
```

| Package | Path | What it is |
|---------|------|-----------|
| `naas-abi-core` | `libs/naas-abi-core/` | The infrastructure library. Engine, ports, service adapters (triple store, vector store, object storage, bus, key-value, cache, secrets). Publishable as a standalone Python package. No agents, no business logic. |
| `naas-abi` | `libs/naas-abi/` | The application layer. Built-in agents, the Nexus web app and its FastAPI backend, core pipelines, and ontologies. Imports `naas-abi-core`. |
| `naas-abi-marketplace` | `libs/naas-abi-marketplace/` | Community-contributed modules, integrations, and agents. All disabled by default, enabled selectively via `config.yaml`. |
| `naas-abi-cli` | `libs/naas-abi-cli/` | The `abi` command-line tool. `abi stack start/stop/status`, `abi chat`, `abi deploy`. |

---

## Inside naas-abi: the module layers

Within the application layer, modules follow a three-tier separation:

```
libs/naas-abi/naas_abi/
├── apps/
│   ├── nexus/          # Full-stack web app (Next.js + FastAPI)
│   ├── api/            # Core REST API
│   ├── mcp/            # MCP server
│   └── sparql_terminal/
├── agents/             # Built-in agents (AbiAgent, OntologyEngineerAgent, ...)
├── pipelines/          # Data ingestion pipelines
└── modules/
    ├── core/           # Always-loaded system modules
    ├── custom/         # Your private modules (not committed to upstream)
    └── marketplace/    # Community modules (from naas-abi-marketplace)
```

---

## Inside naas-abi-core: services and the engine

```
naas_abi_core/
├── engine/             # Engine, EngineProxy, EngineConfiguration, loaders
├── module/             # BaseModule, ModuleConfiguration, ModuleDependencies
├── services/
│   ├── triple_store/   # RDF triple store (Apache Jena Fuseki, Oxigraph, Neptune, FS)
│   ├── vector_store/   # Vector embeddings (Qdrant, in-memory)
│   ├── object_storage/ # File/blob storage (FS, S3, Naas)
│   ├── secret/         # Secret management (dotenv, Naas, base64)
│   ├── bus/            # Message bus (Python queue, RabbitMQ)
│   ├── keyvalue/       # Key-value store (in-memory, Redis)
│   ├── cache/          # Result cache (filesystem)
│   ├── ontology/       # Ontology service (NER port)
│   └── agent/          # Agent base class + IntentAgent
├── models/             # Model registry (OpenRouter, local, airgap)
└── utils/              # onto2py, SPARQL helpers, graph utils, lazy loader
```

---

## The data flow

```
External services  →  Integrations  →  Pipelines  →  Knowledge Graph (Triple Store)
                                                              ↓
                                                        SPARQL Queries
                                                              ↓
                       User / API  ←  Agents  ←  Workflows  ←  Tools
```

1. **Integrations** talk to external APIs (GitHub, LinkedIn, Salesforce, etc.) and return raw data.
2. **Pipelines** transform raw data into OWL/RDF triples and store them in the triple store.
3. **Workflows** implement business logic. They query the knowledge graph with SPARQL and call integrations for write operations.
4. **Agents** are LLM-powered routers that select and invoke the right workflows and integrations as tools.
5. **Apps** (REST API, MCP, Nexus) expose agents and workflows to end users and other systems.

---

## What runs in production

A production ABI deployment runs these Docker services:

| Service | Port | Purpose |
|---------|------|---------|
| Fuseki (Jena TDB2) | 3030 | Primary triple store |
| Qdrant | 6333 | Vector store |
| PostgreSQL | 5432 | Agent memory + Nexus app data |
| RabbitMQ | 5672 | Message bus |
| MinIO / S3 | 9000 | Object storage |
| ABI API | 9879 | FastAPI REST API |
| Nexus frontend | 9879/app | Next.js web app |
| Dagster | 3001 | Orchestration UI |
| MCP server | 8000 | Model Context Protocol |

For local development, lightweight alternatives replace the production services (in-process queue instead of RabbitMQ, in-memory key-value instead of Redis, Oxigraph instead of Fuseki, qdrant-in-memory).
