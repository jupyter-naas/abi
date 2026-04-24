---
sidebar_position: 6
title: "The Runtime"
---

# The Runtime

ABI runs on Docker. Every service in the stack is a standard container orchestrated by Docker Compose, with no proprietary Kubernetes substrate and no managed infrastructure required. You operate it with tools you already know.

This is an intentional design choice. Abstracting infrastructure into a managed runtime delivers security and availability guarantees but removes operator visibility and control. ABI makes the opposite tradeoff: the infrastructure is yours to inspect, modify, extend, and replace. You own operations; in return, there are no accreditation dependencies, no vendor upgrade cycles, and no egress charges.

The same Docker Compose manifest runs on a developer laptop and in a production data center. The only differences between environments are the `config.yaml` overrides that select service backends, the model provider, and the LLM routing configuration.

---

## Local development

The simplest deployment: everything runs on your machine with Docker.

- Triple store: Apache Jena Fuseki (or Oxigraph for lighter footprint)
- Message bus: in-process Python queue (no RabbitMQ required)
- Key-value: in-memory dictionary
- Embeddings: OpenRouter or local Ollama model

Start everything with one command:

```bash
abi stack start
```

---

## Self-hosted (on-premises)

The production configuration. All services run in your infrastructure, nothing leaves your network.

- Your Kubernetes cluster or bare-metal Docker Compose
- Your Postgres, RabbitMQ, MinIO instances
- Your LLM infrastructure (Ollama cluster or private API endpoints)
- Your SSL/TLS termination

This is the configuration naas.ai deploys for enterprise customers who require data residency compliance.

---

## Air-gapped

Full offline capability using locally-run models:

- Ollama serves LLM inference from a local model library
- No calls to OpenAI, Anthropic, or any external API
- Models: Qwen3 8B, DeepSeek R1 8B, Gemma3 4B, or any Ollama-compatible model
- `ai_mode: "local"` in `config.yaml`

The `airgap_gemma` and `airgap_qwen` model configurations in `naas_abi/models/` are purpose-built for this scenario.

---

## Managed (naas.ai)

naas.ai provides enterprise-managed ABI deployments. The open-source core is MIT-licensed; the managed tier adds:

- Deployment and maintenance on your premises or naas.ai infrastructure
- 24/7 support and SLA
- Security compliance assistance (SOC 2, ISO 42001)
- Upgrade management

See [naas.ai/enterprise](https://naas.ai/enterprise) for details.

---

## Configuration per environment

ABI supports environment-specific config files:

```bash
config.yaml              # Default / shared
config.development.yaml  # Local dev overrides
config.production.yaml   # Production overrides
config.airgap.yaml       # Air-gapped overrides
```

The active environment is selected via the `ABI_ENV` environment variable. See [Configuration Reference](/get-started/configuration).

---

→ [The Agent System](./agent-system)
