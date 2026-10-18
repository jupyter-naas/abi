---
sidebar_position: 6
title: "The Runtime"
---

# The Runtime

ABI runs on Docker. Every service in the stack is a standard container orchestrated by Docker Compose, with no proprietary Kubernetes substrate and no managed infrastructure required. You operate it with tools you already know.

This is an intentional design choice. Abstracting infrastructure into a managed runtime delivers security and availability guarantees but removes operator visibility and control. ABI makes the opposite tradeoff: the infrastructure is yours to inspect, modify, extend, and replace. You own operations; in return, there are no accreditation dependencies, no vendor upgrade cycles, and no egress charges.

The same project runs on a developer laptop and in a production data center. The only differences between environments are the config files that select service backends, the model provider, and the LLM routing configuration.

Since 3.0 every deployment runs on a [NATS broker](./nats): the engine serves its kernel services over it, the bus and the [module jobs](./remote-modules#module-jobs) use JetStream, and remote modules run in their own containers next to the engine.

---

## Local development

Two ways to run a project on your machine:

- **Native, no Docker:** `abi dev up` starts `nats-server`, an Oxigraph server, the API, Nexus web and the remote modules listed under `dev.modules`, as native processes with file-based backends (SQLite, the file system). Each git worktree gets its own ports. It needs `nats-server` 2.14 or later on `PATH`, and `jaeger` for `--with-tracing`.
- **Docker Compose:** `abi deploy local` writes the project's stack, and `docker compose up -d` (or `abi stack start`) starts it: NATS, PostgreSQL, Fuseki, Qdrant, MinIO, Redis, the API, Nexus web, the MCP server and Caddy. Remote modules each get a service in `docker-compose.override.yml`.

See the [Quickstart](/user-guide/get-started/quickstart).

---

## Self-hosted (on-premises)

The production configuration. All services run in your infrastructure, nothing leaves your network.

- Your Kubernetes cluster or bare-metal Docker Compose
- Your NATS server (2.14 or later, JetStream on), PostgreSQL, MinIO or S3, Redis, Fuseki and Qdrant
- Your LLM infrastructure (Ollama cluster or private API endpoints)
- Your SSL/TLS termination

Things to plan for:

- **One serving engine.** One engine serves the kernel services per NATS account. For deploys without downtime, set `ABI_ROLLOUT_ID` per deploy and use shared backends (no SQLite or local files): the new engine stands by and takes over when the old one stops. See [one serving engine](./nats#one-serving-engine).
- **A supervisor.** The API and remote modules exit when the broker is unreachable for about two minutes; Docker (`restart: unless-stopped`) or Kubernetes restarts them.
- **The broker stays private.** Traffic to NATS is not encrypted, and its monitoring port has no authentication. See [Security model](./security).
- **Remote modules** scale on their own: several replicas of a module share its agent runs and its jobs.

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

A project made by `abi new project` keeps one config file per environment:

```bash
config.yaml          # Default: what `abi dev up` and the CLI read
config.local.yaml    # The Docker Compose stack (its `abi` service sets ENV=local)
config.remote.yaml   # A remote deployment
```

The engine reads `config.<ENV>.yaml` when the `ENV` environment variable names one that exists, else `config.yaml`. `ABI_CONFIG_OVERLAY` merges a YAML file over it (`abi dev up` uses it for its broker settings). See [Configuration Reference](/user-guide/get-started/configuration).

---

→ [The Agent System](./agent-system)
