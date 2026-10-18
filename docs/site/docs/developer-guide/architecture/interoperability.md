---
sidebar_position: 5
title: "Interoperability"
---

# Interoperability

ABI is built on open protocols at every integration point. Every interface uses a standard that exists independently of ABI: no proprietary SDK required, no lock-in to a particular cloud, identity provider, or model vendor.

---

## Semantic interoperability

The knowledge graph is queryable via SPARQL 1.1, the W3C standard for RDF query. Any SPARQL-compatible client (the bundled SPARQL workbench, Apache Jena tooling, Python `SPARQLWrapper`, or custom scripts) can query ABI's knowledge graph directly against the Fuseki endpoint.

Ontologies are authored and stored as OWL Turtle (`.ttl`) files. They can be exported, imported, merged with external ontologies, and versioned in Git. An ontology built for ABI is portable to any OWL-compatible reasoner or triple store.

OWL reasoning is available natively. Inference rules defined in the ontology (subclass hierarchies, inverse properties, transitivity) are automatically applied by the reasoner, allowing agents to query over inferred facts without explicitly encoding every relationship.

---

## Model interoperability

Every agent accepts a `ChatModel` interface rather than a hardcoded provider. The interface is compatible with any service that implements the OpenAI chat completions API, which includes OpenRouter, Ollama, Azure OpenAI, and most self-hosted inference servers.

The MCP server exposes every registered agent as a tool for any MCP-compatible AI client. Claude Desktop, Cursor, and other MCP clients can invoke ABI agents directly without any additional integration code. New agents are automatically discovered and registered at MCP server startup with no manual configuration.

---

## Data interoperability

The object store (MinIO) exposes a full S3-compatible API. Any tool that speaks S3 (AWS CLI, boto3, DuckDB, Spark, Airbyte) can read from and write to it directly. Raw data ingested by ABI integrations is accessible through the same S3 interface.

PostgreSQL is accessed via standard PSQL and JDBC. Any BI tool, notebook, or SQL client that connects to Postgres can query agent memory, workflow state, and application data.

The REST API (FastAPI) provides programmatic access to every agent and workflow. Endpoints follow OpenAPI 3.0 and are documented at `/docs`. Bearer token authentication is required; tokens are JWTs with configurable expiry and scope.

---

## Code interoperability

Integrations, pipelines, workflows, and agents are plain Python. No proprietary DSL, no framework-specific decorators, no generated code that cannot be read directly.

`naas-abi-core` is a standard Python package installable via `pip` or `uv`. Any Python project can depend on it to use the Engine, service adapters, or ontology tooling independently of the full ABI stack.

Modules are Python packages. A module built for `naas-abi-marketplace` is a versioned, importable package with no ABI-specific publishing pipeline; it can be distributed on PyPI, installed from a private registry, or linked locally.

---

## Security interoperability

Authentication uses JWTs with configurable secret keys. The token endpoint is a standard OAuth2 password flow (`/auth/token`). ABI does not ship a built-in identity provider; SAML and OIDC integration can be layered in front of the API via Caddy (the bundled reverse proxy) without modifying application code.

Authorization is enforced at the API boundary via token scopes. No cloud IAM, no proprietary access control system, no agents calling home.

Secrets are managed via environment variables and `config.yaml`. HashiCorp Vault, AWS Secrets Manager, or any secrets provider that can inject environment variables at runtime is compatible without code changes.

All communication between services inside the stack uses internal Docker networking with no public exposure by default. TLS termination is handled by Caddy with your own certificates; Let's Encrypt automatic provisioning is supported out of the box.

---

→ [The Runtime](./deployment-models)
