---
sidebar_position: 1
title: "Platform Capabilities"
---

# Platform Capabilities

ABI is a platform for building agents on a knowledge graph. This page maps what you build with ABI to the pieces that provide it and to the pages of this guide. Every component is configured in `config.yaml`: you swap an adapter without changing your code (see the [Configuration Reference](/user-guide/get-started/configuration)).

## What you build

| You build | With | Read |
|---|---|---|
| **Agents** that call tools and delegate to other agents | `Agent` and `IntentAgent` classes, on the models of the model registry (OpenRouter, Ollama, and the AI providers of the Marketplace) | [Creating an Agent](/user-guide/build/agents/creating-an-agent) |
| **Tools** for those agents | Workflows (business logic), integrations (external APIs), templatable SPARQL queries | [Workflow](/user-guide/build/agents/creating-a-workflow), [Integration](/user-guide/build/agents/creating-an-integration), [SPARQL queries](/user-guide/build/knowledge-graph/sparql_query_template_system) |
| A **knowledge graph** | OWL ontologies in Turtle (BFO and CCO aligned), `onto2py` generated Python classes, pipelines that write RDF to the triple store (Oxigraph, Fuseki and others) | [Ontology](/user-guide/build/knowledge-graph/creating-an-ontology), [Pipeline](/user-guide/build/knowledge-graph/creating-a-pipeline) |
| **Modules** that package all of the above | In-engine modules (`naas_abi_core`) or remote modules (`naas-abi-sdk`, in their own process) | [Creating a Module](/user-guide/build/modules/creating-a-module), [Build a Remote Module](/user-guide/build/sdk/build-a-remote-module) |
| **Scheduled and event-driven work** | Module jobs on NATS JetStream: cron, interval and event triggers, retries, run history in the System app | [Module jobs](/user-guide/build/modules/module-jobs) |
| **Applications** on top | The REST API, the MCP server, the Nexus web app, and apps your modules ship to Nexus | [REST API](/user-guide/build/applications/api), [MCP Server](/user-guide/build/applications/mcp-server), [Nexus](/user-guide/build/applications/nexus) |
| **Reusable components** from others | The Marketplace: AI providers, application integrations and domain agents | [Marketplace](/user-guide/build/modules/marketplace/marketplace-overview) |

## What ABI runs on

| Capability | Provided by |
|---|---|
| **Models** | The model registry serves chat and embedding models by canonical id. OpenRouter is the default provider of a new project (one key); Ollama runs models locally, and the Marketplace adds providers such as Anthropic, OpenAI, Gemini, Mistral and Bedrock. |
| **Knowledge graph** | A triple store behind the `triple_store` service: Oxigraph (the default of `abi dev up`), Apache Jena Fuseki (the Docker stack) and others. Queries are SPARQL. |
| **Vectors and files** | `vector_store` (Qdrant, SQLite-vec) and `object_storage` (filesystem, S3-compatible such as MinIO). |
| **Messaging and scheduling** | A NATS broker with JetStream: the bus, module jobs and discovery. See [NATS and the kernel services](/developer-guide/architecture/nats). |
| **Observability** | The Nexus System app (services, modules, jobs, agents, NATS), and OpenTelemetry traces exported over OTLP (Jaeger with `abi dev up --with-tracing`). See [Observability](/developer-guide/architecture/observability). |
| **Access and security** | Nexus organizations, workspaces and roles, with password or magic-link sign-in; service tokens between the engine and its modules. See [Security model](/developer-guide/architecture/security). |
| **Packaging and deployment** | Docker Compose (`abi deploy local`), Dokploy (`abi deploy dokploy`) and Naas (`abi deploy naas`). See [Deploy](/user-guide/deploy/overview). |

:::note Legacy components
Dagster and the RabbitMQ bus are legacy opt-in extras for projects without NATS, removed in the next major. New projects schedule with [module jobs](/user-guide/build/modules/module-jobs). See [Dagster](/user-guide/build/applications/dagster).
:::

Each component is independently configurable. See the [Configuration Reference](/user-guide/get-started/configuration) for adapter options.
