# ABI Documentation

ABI (Agentic Brain Infrastructure) is an open-source AI operating system for building your own data and AI platform. It gives your organization a knowledge graph, a fleet of AI agents, and the infrastructure to connect them - on your premises or in the cloud.

---

## Who is this for?

### For decision-makers and architects
Understand what ABI is, why it exists, and how it fits into your organization.

- [[concepts/what-is-abi|What is ABI?]] - The problem it solves and how it compares
- [[concepts/the-stack|The ABI Stack]] - Four packages, one coherent system
- [[concepts/knowledge-graph|Knowledge Graph and Ontologies]] - Why structured knowledge beats raw data
- [[concepts/agent-system|The Agent System]] - How agents, intents, and tools compose
- [[concepts/deployment-models|Deployment Models]] - Local, managed, or air-gapped

### For developers getting started
Get a running stack and understand the architecture.

- [[getting-started/quickstart|Quickstart]] - Zero to running in one command
- [[getting-started/installation|Installation]] - All install options (clone, fork, private fork)
- [[getting-started/configuration|Configuration Reference]] - `config.yaml` explained
- [[getting-started/first-agent|Your First Agent]] - Chat with ABI in under 5 minutes

### For builders
Deep-dive reference for building modules, agents, and integrations.

- [[building/creating-a-module|Creating a Module]] - The extension unit of ABI
- [[building/creating-an-agent|Creating an Agent]] - `Agent.New()` pattern
- [[building/creating-an-integration|Creating an Integration]] - External service adapters
- [[building/creating-a-pipeline|Creating a Pipeline]] - Data ingestion into the knowledge graph
- [[building/creating-a-workflow|Creating a Workflow]] - Business logic exposed as tools + API
- [[building/creating-an-ontology|Creating an Ontology]] - TTL + onto2py code generation

---

## Core Reference

- [[libs/naas-abi-core/index|naas-abi-core]] - The infrastructure library (Engine, Services, Module System)
  - [[libs/naas-abi-core/Architecture|Architecture]]
  - [[libs/naas-abi-core/Engine|Engine]]
  - [[libs/naas-abi-core/Module-System|Module System]]
  - [[libs/naas-abi-core/Quickstart|Library Quickstart]]
  - [[libs/naas-abi-core/services/Overview|Services Overview]]

## Applications

- [[apps/api|REST API]] - FastAPI server on port 9879
- [[apps/nexus|Nexus Web App]] - The full-stack web frontend
- [[apps/mcp-server|MCP Server]] - Claude Desktop and editor integration
- [[apps/dagster|Dagster]] - Orchestration and scheduled jobs
- [[apps/terminal-agent|Terminal Agent]] - CLI chat interface

## CLI

- [[cli/index|abi CLI]] - `abi stack`, `abi chat`, and more

## Architecture Decisions

All major technical decisions are documented as ADRs.

- [[adr/20260330_nexus-hexagonal-architecture|Nexus Hexagonal Architecture]] (2026-03)
- [[adr/20260305_agent-class-new-pattern|Agent.New() Pattern]] (2026-03)
- [[adr/20260212_apache-jena-fuseki-default-triplestore|Apache Jena Fuseki as Default Triple Store]] (2026-02)
- [[adr/20260211_nexus-monorepo-integration|Nexus Monorepo Integration]] (2026-02)
- [[adr/20260127_onto2py-ontology-to-python-codegen|onto2py Codegen]] (2026-01)
- [[adr/20251130_python-monorepo-libs-split|Monorepo Split]] (2025-11)
- [[adr/20251106_openrouter-unified-model-layer|OpenRouter Unified Model Layer]] (2025-11)
- → [[adr/20250812_three-tier-module-architecture|Full ADR list]]

---

> Legacy documentation is archived under `.old/` and excluded from publication.
