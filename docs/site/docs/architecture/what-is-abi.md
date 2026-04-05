---
sidebar_position: 1
---

# What is ABI?

ABI (Agentic Brain Infrastructure) is an open-source AI operating system that gives any organization its own private knowledge graph, a configurable fleet of AI agents, and the infrastructure to connect them to every tool and data source it uses.

---

## The problem it solves

Most organizations have a data problem masquerading as an AI problem. Data lives in dozens of disconnected SaaS tools. Querying it means either hand-coding integrations for each source or feeding unstructured exports into an LLM and hoping it reasons correctly.

ABI takes a different approach: convert raw data into a **structured knowledge graph** grounded in a formal ontology, then let AI agents query that graph with precision. Agents know the difference between a Person, a Role, and an Organization - because the ontology says so, not because an LLM guessed.

---

## What it is not

- It is not a chatbot wrapper. The knowledge graph and the service infrastructure are the product; agents are the interface on top.
- It is not a low-code platform. ABI is a Python framework for teams that want to own their AI stack in code.
- It is not cloud-locked. The full stack runs locally with Docker, entirely air-gapped, or on your own infrastructure.

---

## How it compares

| Capability | ABI | Palantir Foundry | LangChain / LlamaIndex |
|---|---|---|---|
| Formal ontology (BFO/OWL) | Yes | Yes | No |
| Self-hosted / air-gapped | Yes | No | Yes |
| Open source (MIT) | Yes | No | Yes |
| Knowledge graph (SPARQL) | Yes | Yes | Partial |
| Multi-agent orchestration | Yes | No | Yes |
| Module marketplace | Yes | No | Limited |
| Managed enterprise tier | Yes (naas.ai) | Yes | No |

---

## Key capabilities

- **Knowledge graph**: All data is stored as RDF triples in an OWL-compliant triple store. Ontologies define the schema. SPARQL queries retrieve it with precision.
- **Agent system**: Configurable AI agents with persistent memory, tool calling, and multi-agent delegation. Agents are exposed as REST API endpoints and MCP tools automatically.
- **Module system**: Functionality is packaged in modules (core, custom, marketplace). Modules declare their dependencies and are loaded by the Engine in topological order.
- **Platform services**: Triple store, vector store, object storage, secret manager, message bus, key-value store - all behind port interfaces with pluggable adapters.
- **Full-stack deployment**: Nexus web frontend, FastAPI REST API, MCP server, Dagster orchestration, and the `abi` CLI ship together.
- **Pluggable models**: OpenRouter provides a single API key for access to every major LLM (OpenAI, Anthropic, Google, Mistral, Meta, DeepSeek, Qwen). Local models via Ollama are also supported for air-gapped or privacy-constrained deployments.

---

## Who uses it

- Engineering teams building a private AI platform on their own infrastructure.
- Data teams that need structured, queryable knowledge on top of SaaS data sources.
- Organizations in regulated industries (finance, defense, healthcare) that cannot send data to third-party AI services.
- Companies building products on top of ABI's infrastructure - see the [[apps/nexus|Nexus]] full-stack app.
