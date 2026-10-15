---
sidebar_position: 1
---

# Quickstart

Get a running ABI project in under 10 minutes.

:::tip Upgrading from 2.x?
ABI 3.0 runs on NATS, makes module jobs the default scheduler, and turns Dagster
and RabbitMQ into legacy extras. Read [Migrate from 2.x to 3.0](/upgrade/migrate-to-3)
and the [release note](/updates/abi-3-0-nats).
:::

---

## Prerequisites

- Python 3.12+, [git](https://git-scm.com/) and [uv](https://docs.astral.sh/uv/getting-started/installation/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`). The project adds ABI as a git submodule.
- To run the project natively with `abi dev up`:
  - [`nats-server`](https://docs.nats.io/running-a-nats-service/introduction/installation) 2.14 or later on `PATH` (`brew install nats-server`, or a release binary);
  - Node.js 18+ and [pnpm](https://pnpm.io/installation) 8.15+, for the Nexus web app;
  - optionally [`jaeger`](https://www.jaegertracing.io/download/) v2 on `PATH`, for `abi dev up --with-tracing`.
- Or [Docker](https://www.docker.com/products/docker-desktop/) (8 GB+ RAM) to run the project's Docker Compose stack instead.
- An [OpenRouter API key](https://openrouter.ai/keys) for cloud models. Skip it for local-only mode (Ollama).

---

## 1) Install the CLI

```bash
uv tool install naas-abi-cli --force --upgrade --with-executables-from naas-abi-core
abi --help
```

---

## 2) Create a project

```bash
abi new project my_ai
cd my_ai
```

`abi new project` asks for the base domain (`localhost` by default), adds ABI
as a git submodule (`.abi/`), installs the packages, and validates the config.
The validation asks for `OPENROUTER_API_KEY` when it is not in your environment
or in `.env`.

The project runs on **NATS**: its configs have a `nats:` block with discovery
on, and `.env` holds the signing secret (`NATS_JWT_SECRET`), the broker's
passwords (`NATS_ABI_PASSWORD`, `NATS_MODULE_PASSWORD`) and the admin's
generated password (`NEXUS_USER_ADMIN_EXAMPLE_COM_PASSWORD`).

| Option | Effect |
|---|---|
| `--without-nats` | The classic in-process project: RabbitMQ and Dagster (legacy, removed in the next major), with the `naas-abi-core[dagster,rabbitmq]` extras. |
| `--without-local-deploy` | No Docker Compose stack. |
| `--domain example.com` | Public hosts `nexus.example.com` and `api.example.com`. |
| `--with-coding`, `--with-headscale` | Coding workspaces, a Headscale service. |

---

## 3) Start it

**Natively, no Docker:**

```bash
abi dev up
```

It starts `nats-server`, an Oxigraph server, the API (the engine, with
discovery), Nexus web, and the remote modules listed under `dev.modules`. It
prints each service's URL and the admin login. The first boot takes a few
minutes. Ports are offset per checkout: `abi dev ports` prints them.

```bash
abi dev status            # services and their health
abi dev logs api -f       # follow a service's log
abi dev up -d             # run in the background
abi dev up --with-tracing # also run Jaeger and trace every call
abi dev down              # stop everything
```

**With Docker Compose:**

```bash
docker compose up -d
abi stack status
```

The stack: NATS, PostgreSQL, Fuseki, Qdrant, MinIO, Redis, the API, Nexus web
(port 3042), the MCP server and Caddy. Regenerate it after a CLI upgrade with
`abi deploy local --regenerate`.

Sign in to Nexus as `admin@example.com`, with the password from `.env`.

---

## 4) Add a module

```bash
abi new module research
```

In a NATS project this is a **remote module**: it runs in its own process with
`naas-abi-sdk`, publishes an agent and an hourly job, and registers itself in
discovery. `abi dev up` runs it (`dev.modules` in `config.yaml`), and so does
Docker Compose (`docker-compose.override.yml`). Its agent appears in Nexus once
it logs `READY`. Continue with [Build a Remote Module](/capabilities/sdk/build-a-remote-module).

`abi new module <name> --in-engine` creates a classic module that the engine
loads (agents, workflows, pipelines, integrations, ontologies); add it under
`modules:` in the config. See [Creating a Module](/capabilities/modules/creating-a-module).

---

## 5) Chat with ABI

In Nexus, or from the terminal:

```bash
abi chat
```

---

## AI mode: cloud vs. local

**Cloud mode** (default): models come through OpenRouter. Requires `OPENROUTER_API_KEY`.

**Local mode**: all AI processing runs on your machine via Ollama. No data leaves your network.

```bash
# Install Ollama: https://ollama.com/download
ollama pull qwen2.5:3b && ollama pull nomic-embed-text
uv add "naas-abi-marketplace[ai-ollama]"
```

Then, in `config.yaml` (the generated file shows each step in its comments):
uncomment the `naas_abi_marketplace.ai.ollama` module, and set

```yaml
global_config:
  ai_mode: "local"

services:
  model_registry:
    default_chat_model: "qwen-2.5-3b"
    default_embedding_model: "nomic-embed-text"
```

---

## Service URLs

| Service | `abi dev up` | Docker Compose |
|---|---|---|
| Nexus web | `abi dev ports` (`nexus-web`) | http://localhost:3042 |
| API (Swagger at `/docs`) | `abi dev ports` (`api`) | http://localhost:9879 |
| NATS monitoring | printed by `abi dev up` | http://localhost:8222 |
| SPARQL | `abi dev ports` (`oxigraph`) | http://localhost:3030 (Fuseki) |
| MCP server | none | http://localhost:8000 |

The Nexus **System** app (sidebar, super admins) shows the kernel services,
modules, jobs, agents, NATS and traces: see [Observability](/architecture/observability).

Next: [Configuration Reference](/get-started/configuration), [NATS and the Kernel Services](/architecture/nats), or [Build a Remote Module](/capabilities/sdk/build-a-remote-module).
