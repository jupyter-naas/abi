---
sidebar_position: 1
---

# Quickstart

Create a project, add modules, start it and chat with its agents, in about 10 minutes plus the first boot.

:::tip Upgrading from 2.x?
ABI 3.0 runs on NATS, makes module jobs the default scheduler, and turns Dagster
and RabbitMQ into legacy extras. Read [Migrate from 2.x to 3.0](/user-guide/upgrade/migrate-to-3)
and the [release note](/user-guide/release-notes/abi-3-0-nats).
:::

---

## Prerequisites

[git](https://git-scm.com/) and [uv](https://docs.astral.sh/uv/getting-started/installation/); for `abi dev up`, `nats-server` 2.14 or later, Node.js 18.17 or later and [pnpm](https://pnpm.io/installation); an [OpenRouter API key](https://openrouter.ai/keys) (or Ollama, see [AI mode](#ai-mode-cloud-vs-local)); for the Docker stack, [Docker](https://www.docker.com/products/docker-desktop/) with 8 GB of RAM or more. Details and versions: [Install and prerequisites](/user-guide/get-started/install).

---

## 1) Install the CLI

```bash
uv tool install naas-abi-cli --force --upgrade --with-executables-from naas-abi-core
abi --help
```

---

## 2) Create a project

```bash
export OPENROUTER_API_KEY=sk-or-...       # asked for when missing, and impossible to ask without a terminal
abi new project my_ai --domain localhost
cd my_ai
```

`abi new project` adds ABI as a git submodule (`.abi/`), installs the packages and
validates the config. The project runs on **NATS**: its configs have a `nats:` block with
discovery on, and `.env` holds the signing secret (`NATS_JWT_SECRET`), the broker's passwords
(`NATS_ABI_PASSWORD`, `NATS_MODULE_PASSWORD`) and the admin's generated password
(`NEXUS_USER_ADMIN_EXAMPLE_COM_PASSWORD`).

| Option | Effect |
|---|---|
| `--without-nats` | The classic in-process project: RabbitMQ and Dagster. [Legacy](/user-guide/get-started/legacy-mode), removed in the next major. |
| `--without-local-deploy` | No Docker Compose stack. |
| `--domain example.com` | Public hosts `nexus.example.com` and `api.example.com`. |
| `--with-coding`, `--with-headscale` | Coding workspaces, a Headscale service. |

Every option: [`abi new project`](/user-guide/reference/cli#abi-new-project).

---

## 3) Add modules

```bash
abi new module research                   # a remote module: own process, naas-abi-sdk
abi new module legacy --in-engine         # a module the engine loads: naas_abi_core
```

A **remote module** runs in its own process: it publishes an agent and an hourly job,
registers itself in discovery, and `abi dev up` (or Docker Compose) runs it. An
**in-engine module** is loaded by the engine and has pipelines, workflows, integrations and
ontologies as well. Add it under `modules:` in `config.yaml`, as the command prints:

```yaml
modules:
  - module: legacy
    enabled: true
```

Add an agent and an app inside each module (see [Creating a Module](/user-guide/build/modules/creating-a-module)
for when to choose which):

```bash
cd src/legacy
abi new agent analyst agents
abi new app reports apps
cd ../..
uv run pytest                             # the tests the modules came with
```

---

## 4) Start it

**Natively, no Docker:**

```bash
abi dev up -d
abi dev status
abi dev ports
```

It starts `nats-server`, an Oxigraph server, the API (the engine, with discovery and
jobs), Nexus web and the remote modules listed under `dev.modules`, and prints each
service's URL and the admin login. In NATS mode `abi dev up -d` waits for the API before it
starts the modules. The first boot takes a few minutes: the API loads every module, and
Nexus web installs its packages with pnpm. Ports are offset per checkout: `abi dev ports`
prints them.

```bash
abi dev logs api -f       # follow a service's log
abi dev up --with-tracing # also run Jaeger and trace every call
abi dev down              # stop everything
```

**With Docker Compose:**

```bash
abi stack start
abi stack status
```

The stack: NATS, PostgreSQL, Fuseki, Qdrant, MinIO, Redis, the API, Nexus web (port 3042),
the MCP server and Caddy. See [Deploy with Docker](/user-guide/deploy/local-docker).

Sign in to Nexus as `admin@example.com`, with the password from `.env`. The **Research**,
**Legacy** and **Analyst** agents are listed once the remote module logs `READY` and the
engine has loaded the in-engine one.

---

## 5) Chat with ABI

In Nexus, or from the terminal:

```bash
abi chat
```

`abi chat` (and `abi agent list`, `abi run script`) reads the project's `config.yaml`, whose broker is `127.0.0.1:4222`: the Docker stack's. It is a client of that engine. Under `abi dev up` the broker has its own port, which only the generated overlay knows, so point the command at it:

```bash
ABI_CONFIG_OVERLAY=.abi/dev/dev.overlay.yaml abi chat
```

Without any engine running, it starts its own (it needs a broker: see [`abi chat`](/user-guide/reference/cli#abi-chat)).

---

## AI mode: cloud vs. local

**Cloud mode** (default): models come through OpenRouter. Requires `OPENROUTER_API_KEY` (another provider's module works the same way).

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
modules, jobs, agents, NATS and traces: see [Observability](/developer-guide/architecture/observability).

---

## Next steps

- [Build a Remote Module](/user-guide/build/sdk/build-a-remote-module): agents, apps and jobs in their own process.
- [Module jobs and scheduling](/user-guide/build/modules/module-jobs): run work on a schedule or on an event.
- [Configuration Reference](/user-guide/get-started/configuration): the `nats:` block, services and secrets.
- [Deploy](/user-guide/deploy/overview): Docker, Dokploy, production.
- [NATS and the Kernel Services](/developer-guide/architecture/nats): how it works.
