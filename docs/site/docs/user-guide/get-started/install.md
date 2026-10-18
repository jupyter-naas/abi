---
sidebar_position: 0
title: "Install and prerequisites"
---

# Install and prerequisites

What a machine needs before you create a project with `abi new project`, and
what each way of running it adds. ABI runs on **macOS and Linux**.

---

## What you need, by task

| You want to | You need |
|---|---|
| Install the CLI and create a project | [git](https://git-scm.com/), [uv](https://docs.astral.sh/uv/getting-started/installation/) |
| Run the project natively (`abi dev up`) | `nats-server` 2.14 or later, Node.js 18.17 or later and [pnpm](https://pnpm.io/installation) |
| Run the project in Docker (`abi deploy local`, `abi stack start`) | [Docker](https://docs.docker.com/get-docker/) with Compose v2, 8 GB of RAM or more |
| Chat with an agent | A model: an [OpenRouter](https://openrouter.ai/keys) key (or another cloud provider's), or [Ollama](https://ollama.com/download) for local models |
| Trace calls across processes (`abi dev up --with-tracing`) | [`jaeger`](https://www.jaegertracing.io/download/) v2 on `PATH` |

---

## uv and Python

[uv](https://docs.astral.sh/uv/) installs the CLI and manages every project's
Python environment:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

A project created by `abi new project` requires **Python 3.12 or later**
(`requires-python = ">=3.12"` in its `pyproject.toml`). You do not have to install
it yourself: uv downloads a matching interpreter the first time it builds the
project's environment. The CLI itself runs on 3.11 or later.

You also need [git](https://git-scm.com/): a project adds ABI as the `.abi` git
submodule, which is how it resolves the framework until `naas-abi-proto` and
`naas-abi-sdk` are on PyPI.

---

## The CLI

```bash
uv tool install naas-abi-cli --force --upgrade --with-executables-from naas-abi-core
abi --help
```

Run it again to upgrade. Inside a project, `abi` re-runs itself with the project's
own CLI version (it says so on stderr), so an old global install never drives a
newer project.

---

## nats-server, for `abi dev up`

Since 3.0 a project runs on a NATS broker. `abi dev up` starts a native
`nats-server`, so it must be on `PATH`, at version **2.14 or later** (JetStream
message schedules with time zones need it):

```bash
brew install nats-server        # macOS
nats-server --version           # v2.14.x or later
```

On Linux, download a release binary from the
[nats-server releases](https://github.com/nats-io/nats-server/releases) and put it
in `~/.local/bin`. A project that runs only in Docker needs no local broker: its
Compose stack has a `nats` service.

## Node.js and pnpm, for Nexus web

`abi dev up` runs the Nexus web app natively, which needs Node.js 18.17 or later and
pnpm (CI runs Node 20 and 22). It runs `pnpm install` itself on the first start.

---

## Docker, for `abi deploy local`

`abi deploy local` writes a Docker Compose stack and `abi stack start` (or
`docker compose up -d`) runs it: NATS, PostgreSQL, Fuseki, Qdrant, MinIO, Redis,
the API, Nexus web, the MCP server and Caddy. Give Docker 8 GB of RAM or more.
See [Deploy with Docker](/user-guide/deploy/local-docker).

---

## A model: a cloud key or Ollama

Agents need a model provider. Pick one:

- **Cloud** (the default). A generated project routes models through OpenRouter:
  put an [`OPENROUTER_API_KEY`](https://openrouter.ai/keys) in the environment or
  in `.env`. `abi new project` asks for it when it is missing; without a terminal
  (CI, scripts) export it first. Any value works when nobody chats.
- **Local.** [Install Ollama](https://ollama.com/download), pull the models and
  switch the project to `ai_mode: "local"`. No data leaves the machine. The steps
  are in [AI mode: cloud vs. local](/user-guide/get-started/quickstart#ai-mode-cloud-vs-local).

Other providers (OpenAI, Anthropic, Gemini, Mistral, Bedrock, ...) are marketplace
modules: see [Marketplace overview](/user-guide/build/modules/marketplace/marketplace-overview).

---

## Check your machine

```bash
git --version
uv --version
nats-server --version     # only for `abi dev up`
node --version            # only for `abi dev up`
pnpm --version            # only for `abi dev up`
docker compose version    # only for the Docker stack
```

Then follow the [Quickstart](/user-guide/get-started/quickstart).
