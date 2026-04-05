---
sidebar_position: 1
title: "Platform Capabilities"
---

# Platform Capabilities

ABI is a full-stack AI operating system. The table below maps every capability to the open-source technology that delivers it.

| # | Capability | Description |
|---|---|---|
| 01 | **Secure LLM Access** | OpenRouter (one API key, 300+ models across 60+ providers: Claude, GPT-4o, Mistral, Llama, DeepSeek, Qwen). LiteLLM proxy for routing, fallback, and cost control. Ollama / vLLM for air-gapped or on-device deployment. PII guardrails enforced at the proxy layer. Each deployment holds and controls its own API key; data policy configured directly in their account. |
| 02 | **End-to-End Observability** | OpenTelemetry (distributed tracing, spans per agent step), Prometheus (metrics collection), Grafana (dashboards and alerting). Full provenance chain from user query to output stored in the knowledge graph. |
| 03 | **Context Engineering** | Dagster (pipeline orchestration), RabbitMQ (event bus and async messaging), custom source connectors (REST, RSS, file watcher, direct DB). Structured, logic, and action context from five source classes. |
| 04 | **Ontology System** | Apache Jena / Fuseki (RDF triplestore, SPARQL endpoint), BFO ISO 21838-2 seven-bucket classification, OOPS! and SHACL validators. Formal upper ontology alignment to an international standard. |
| 05 | **Vector and Compute** | Qdrant (vector store, open source), Apache Jena SPARQL (graph queries), MinIO (S3-compatible object storage, open source). Semantic search and embedding retrieval across unstructured and structured sources. |
| 06 | **Security and Governance** | Keycloak (open-source identity and access management, OIDC/SAML, RBAC, MFA), per-query audit log, data classification marking at every output, SHACL validation on all graph assertions, CCV enforcement at ingestion. |
| 07 | **Agent Lifecycle** | SuperAssistant orchestrator, domain agent ensemble, evaluation suites, versioned agent logic with Git-based rollback. Built on ABI (open-source, MIT license). |
| 08 | **Operational Automation** | Dagster schedules and sensors (event-driven pipeline triggers), RabbitMQ (async event bus), Caddy (reverse proxy, TLS termination). Headscale (WireGuard mesh VPN) federates geographically distributed deployments into a single secure network. |
| 09 | **Development Environments** | JupyterHub, VS Code (open source build), MCP server integration, Python SDK. Full Git-based contribution workflow; teams extend agents directly against the open codebase. |
| 10 | **Human+AI Applications** | Nexus (React, open source): chat interface, sector dashboards, analyst workbench, report preview, SPARQL workbench, data classification markings at every output. |
| 11 | **Package, Release, Deploy** | Docker (containerization), Kubernetes (orchestration), Helm (release management), OpenTofu (infrastructure as code). Hexagonal ports-and-adapters architecture. Deploys on any cloud, on-prem server, or edge device. |
| 12 | **Enterprise Automation** | Auto-decomposition pipeline, gap detection and alert routing, predictive scoring engine, automated report generation (PDF, JSON, RDF). End-to-end from user question to scored, traceable output. |

---

## How capabilities map to the stack

```
LLM Access (01)          → OpenRouter / LiteLLM / Ollama
Context Engineering (03) → Dagster + RabbitMQ + connectors
Ontology System (04)     → Apache Jena / Fuseki + BFO/CCO
Vector and Compute (05)  → Qdrant + MinIO
Agent Lifecycle (07)     → ABI engine + LangGraph
Applications (10)        → Nexus (React) + REST API + MCP
Deploy (11)              → Docker + Kubernetes + Helm
```

Each capability is independently configurable: swap any component via `config.yaml` without touching application code. See [Configuration Reference](../get-started/configuration) for adapter options.
