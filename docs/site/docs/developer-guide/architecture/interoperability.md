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

ABI does not run an OWL reasoner of its own at query time: SPARQL runs against the triples the store holds. Because ontologies are plain OWL, you can apply any OWL-compatible reasoner, or a triple store configured with inference, to the same files and data.

---

## Model interoperability

Every agent accepts a `ChatModel` interface rather than a hardcoded provider. A `ChatModel` wraps a LangChain chat model, and the marketplace has provider modules for OpenRouter, OpenAI, Anthropic, Azure, Bedrock, Ollama and many more; a server that implements the OpenAI chat completions API works through the OpenAI-compatible modules. Which models exist is decided by the model registry and the modules you enable.

The MCP server exposes every registered agent as a tool for any MCP-compatible AI client. Claude Desktop, Cursor, and other MCP clients can invoke ABI agents directly without any additional integration code. New agents are automatically discovered and registered at MCP server startup with no manual configuration.

---

## Data interoperability

The object store (MinIO) exposes a full S3-compatible API. Any tool that speaks S3 (AWS CLI, boto3, DuckDB, Spark, Airbyte) can read from and write to it directly. Raw data ingested by ABI integrations is accessible through the same S3 interface.

PostgreSQL is accessed via standard PSQL and JDBC. Any BI tool, notebook, or SQL client that connects to Postgres can read the application data of Nexus, the documents of the Document Service (agent memory, job runs) and the dataset catalog.

The REST API (FastAPI) provides programmatic access to every agent and workflow. Endpoints follow OpenAPI 3.0 and are documented at `/docs`. The agent endpoints take a bearer token (the shared `ABI_API_KEY`); the Nexus API signs users in and issues JWTs (`/api/auth/token`).

---

## Service interoperability

The kernel services (object storage, triple store, datasets, documents, secrets, key-value, events, vector store and the rest) are versioned protobuf contracts on the NATS broker (`abi.svc.<service>.v1.*`). The contracts live in `naas-abi-proto`, and `naas-abi-sdk` gives async clients for them. A module written against them runs in its own process, in any deployment, with no knowledge of the backends; any NATS client that implements a contract and presents a valid service token can call it. See [NATS and the kernel services](./nats) and [Remote modules and jobs](./remote-modules).

---

## Code interoperability

Integrations, pipelines, workflows, and agents are plain Python. No proprietary DSL, no framework-specific decorators, no generated code that cannot be read directly.

`naas-abi-core` is a standard Python package installable via `pip` or `uv`. Any Python project can depend on it to use the Engine, service adapters, or ontology tooling independently of the full ABI stack.

Modules are Python packages. A module built for `naas-abi-marketplace` is a versioned, importable package with no ABI-specific publishing pipeline; it can be distributed on PyPI, installed from a private registry, or linked locally.

---

## Security interoperability

Nexus has its own user accounts (password and magic-link sign-in) and signs users in with JWTs through a standard OAuth2 password flow (`/api/auth/token`). It has no built-in SAML or OpenID Connect: put an identity-aware proxy in front of the API (Caddy, the bundled reverse proxy, can sit in the chain) without modifying application code.

Authorization is enforced at the API boundary through the roles of organizations and workspaces. No cloud IAM, no proprietary access control system, no agents calling home.

Secrets are read through the secret service, which composes a `.env` file, the Naas secret store and base64 adapters, and `config.yaml` refers to them as `{{ secret.NAME }}`. HashiCorp Vault, AWS Secrets Manager, or any provider that can inject environment variables or write the `.env` file at deploy time works without code changes.

Inside the stack, containers talk over the internal Docker network with no public exposure by default; the NATS broker is published on 127.0.0.1 only. TLS termination is handled by Caddy with your own certificates, or Let's Encrypt for a public domain. Traffic to the broker is not encrypted: see [Security model](./security).

---

→ [Deployment models](/user-guide/deploy/deployment-models)
