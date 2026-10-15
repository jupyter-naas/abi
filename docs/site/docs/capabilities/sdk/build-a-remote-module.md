---
sidebar_position: 1
title: "Build a Remote Module"
---

# Build a Remote Module

A remote module runs in its own process and reaches the engine only through
NATS, with `naas-abi-sdk`. It can publish agents, run jobs and serve web apps,
and it deploys, restarts and scales on its own. How it works underneath is in
[Remote Modules and Jobs](/architecture/remote-modules).

This guide builds one in a project made by `abi new project`, runs it with
`abi dev up`, and deploys it with Docker Compose.

## Before you start

- A NATS project: `abi new project <name>` creates one (see the
  [Quickstart](/get-started/quickstart)). For a 2.x project, follow
  [Migrate from 2.x to 3.0](/upgrade/migrate-to-3) to phase 2 first.
- `nats-server` 2.14 or later on `PATH`, for `abi dev up`.

## 1. Create the module

From the project's root:

```bash
abi new module research
```

```text
Remote module 'research' created at:
  .../src/research

It runs in its own process and registers itself in discovery (project 'my_project'), so it is not added to `modules:`.
- `abi dev up` runs it: added to dev.modules in config.yaml.
- Its module key is in .env (ABI_MODULE_KEY_RESEARCH): it signs its tokens as my_project.research only.
- `abi start` runs it: added the 'research' service to docker-compose.override.yml.
```

What it wrote:

| Path | What |
|---|---|
| `src/research/__init__.py` | `ABIModule`: its id, configuration, dependencies, agents, jobs and lifecycle |
| `src/research/__main__.py` | `python -m research`: `run_module` with discovery and signal handling |
| `src/research/agents/ResearchAgent.py` | An SDK `IntentAgent` on the engine's models, with its memory in the Document Service |
| `src/research/jobs.py` | Job bodies, testable without a broker |
| `src/research/apps/research/` | A web app (`manifest.json`, `index.html`) |
| `src/research/tests/` | Offline tests |
| `src/research/Dockerfile` | An image with the SDK only: the build fails if `naas_abi_core` is installed |
| `config.yaml` | A `dev.modules` entry, for `abi dev up` |
| `docker-compose.override.yml` | A `research` service, for Docker Compose |
| `.env` | `ABI_MODULE_KEY_RESEARCH`, the module's key |

In a project without a `nats:` block, `abi new module` creates an in-engine
module instead (it says so); `--remote` forces a remote one. Outside a
project, or with `--standalone`, it creates a repository of its own (see
[A module in its own repository](#a-module-in-its-own-repository)).

Module names must match `^[a-z][a-z0-9-]{0,62}$` once kebab-cased.

## 2. The module class

```python
from naas_abi_sdk import AgentDescriptor, BaseModule, ModuleConfiguration, ModuleDependencies
from naas_abi_sdk.jobs import Every, JobContext, job

MODULE_ID = "my_project.research"


@dataclass
class ResearchConfiguration(ModuleConfiguration):
    chat_model: str = ""  # a canonical model id the engine registers; empty: its default


class ABIModule(BaseModule[ResearchConfiguration]):
    Configuration = ResearchConfiguration
    module_id = MODULE_ID
    package_version = "0.1.0"
    # Services this module calls on the engine. Undeclared ones are refused.
    dependencies = ModuleDependencies(services=("model_registry", "document"))
    # Published in discovery; Nexus lists them with the engine's agents.
    agents = (AgentDescriptor(NAME, DESCRIPTION, capabilities=("agent.invoke.v1",)),)

    async def on_initialized(self) -> None:
        # The engine's services are reachable; bind what the module declared.
        agent = await create_agent(self.engine, MODULE_ID, chat_model=self.configuration.chat_model)
        self.expose_agent(NAME, agent.as_handler())

    @job(triggers=(Every("1h"),), timeout=timedelta(minutes=5))
    async def heartbeat(self, ctx: JobContext) -> dict[str, Any]:
        return await jobs.heartbeat(self, ctx)

    async def run(self) -> None:
        ...  # waits until READY, then stays up until stopped
```

The rules:

- **Never import `naas_abi_core`** (nor `naas_abi`, `naas_abi_marketplace`).
  The module's tests and its Docker build check it.
- **Keep `module_id` stable.** Discovery, job subjects and the agent's memory
  are keyed by it, and the module's key signs for it only.
- **Declare every service** you call in `ModuleDependencies(services=...)`:
  `activity_log`, `bus`, `cache`, `coding_environment`, `dataset`, `document`,
  `email`, `event`, `keyvalue` (or `kv`), `model_registry`, `object_storage`,
  `secret`, `source_control`, `triple_store`, `vector_store`. Calls are async:
  `await self.engine.services.object_storage.put_object(prefix, key, data)`.
- **Bind in `on_initialized`** every agent, app and job handler the class
  declares: the module becomes `READY` right after.
- Hooks run in this order: `on_load`, `on_initialized`, `run()`, then
  `on_unloaded` at the end. Stop your own background tasks in `on_unloaded`.
- Outside the class, `current_module()` (from `naas_abi_sdk`) returns the
  running module for the current task.

## 3. Add an agent

From the module's folder:

```bash
cd src/research
abi new agent Reviewer agents
```

It writes `agents/ReviewerAgent.py`, an SDK agent. Declare it and bind it:

```python
from research.agents import ReviewerAgent

class ABIModule(BaseModule[ResearchConfiguration]):
    agents = (
        AgentDescriptor(NAME, DESCRIPTION, capabilities=("agent.invoke.v1",)),
        AgentDescriptor(ReviewerAgent.NAME, ReviewerAgent.DESCRIPTION, capabilities=("agent.invoke.v1",)),
    )

    async def on_initialized(self) -> None:
        ...
        reviewer = await ReviewerAgent.create_agent(self.engine, MODULE_ID)
        self.expose_agent(ReviewerAgent.NAME, reviewer.as_handler())
```

The agent uses the engine's models over NATS (no provider key in the module)
and keeps its conversations in the engine's Document Service, so they survive
restarts and are shared by replicas. Any object with an async
`invoke(prompt, context)` (and optionally `stream_invoke`) can be exposed as an
agent too.

To call another module's agent, declare the module and ask discovery:

```python
dependencies = ModuleDependencies(services=("document",), modules=("my_project.other",))

async def ask(self, question: str) -> str:
    other = self.engine.modules["my_project.other"]
    agent = await other.get_agent("Other")
    return await agent.invoke(question)
```

## 4. Add a job

A job is an async method with `@job`. JetStream schedules it, and one replica
of the module runs each trigger:

```python
from datetime import timedelta
from naas_abi_sdk.jobs import Cron, Every, JobContext, job

@job(triggers=(Cron("0 0 6 * * *", time_zone="UTC"),), timeout=timedelta(minutes=30), max_attempts=3)
async def morning_digest(self, ctx: JobContext) -> dict:
    items = await collect(self)
    if not items:
        ctx.skip("nothing new")
        return {}
    ctx.log(f"{len(items)} items")
    return {"items": len(items)}  # stored on the run record
```

- `Cron` takes **six fields, seconds first** (`"0 0 6 * * *"` is 06:00:00).
  `Every("15m")` and `OnEvent(event_type=..., filter=...)` are the other
  triggers.
- Delivery is at least once: a job must tolerate running twice.
- Trigger it from the module with `self.trigger_job("morning_digest", {...})`
  (`await self.atrigger_job(...)` in async code), from the System app's
  **Jobs** tab (**Run now**), or with
  `POST /api/admin/system/jobs/my_project.research/morning_digest/trigger` and
  `{"payload": {...}}` as a super admin.

Triggers, retries, idempotency and retention are described in
[Module jobs](/architecture/remote-modules#module-jobs).

## 5. Add an app

```bash
cd src/research
abi new app dashboard apps
```

It writes `apps/dashboard/` (`manifest.json`, `index.html`). Nexus lists the
app while the module runs; enable it on a workspace's Apps page to open it. The
files of the folder are served as they are. For a backend, bind an ASGI
application:

```python
from fastapi import FastAPI, Request

api = FastAPI()


@api.get("/api/hello")
async def hello(request: Request) -> dict:
    abi = request.scope["abi"]
    return {"user": abi["user_id"], "workspace": abi["workspace_id"]}


class ABIModule(BaseModule[ResearchConfiguration]):
    async def on_initialized(self) -> None:
        ...
        self.expose_app("dashboard", api)  # apps/dashboard/manifest.json
```

The page calls it with a relative URL, `fetch("api/hello")`. It runs sandboxed:
no `localStorage` or `document.cookie`, and absolute URLs start with the app's
`root_path`. Large uploads stream (`request.stream()`), and so do
`StreamingResponse`s. Details and limits: [Remote apps](/architecture/remote-apps).

The module's image installs the SDK only. Add what your backend needs (here
`fastapi`) to the `pip install` line of `src/research/Dockerfile`.

## 6. Run it with `abi dev up`

```bash
abi dev up
```

In a NATS project it starts `nats-server`, Oxigraph, the API (with discovery),
Nexus web, then every `dev.modules` entry, each under a supervisor that
restarts it if it exits. The module gets `ABI_NATS_URL` (logged in as the
broker user `module`), `ABI_MODULE_KEY`, `ABI_DISCOVERY_PROJECT` and, with
`--with-tracing`, `OTEL_EXPORTER_OTLP_ENDPOINT`.

```bash
abi dev status                        # services and dev modules, with their pids
abi dev logs research -f              # the module's log: "... READY: registered in discovery"
abi dev down --service research       # stop the module only
abi dev up -d --service research      # start it again, next to the running stack
```

The `dev.modules` entry `abi new module` added:

```yaml
dev:
  modules:
    - name: research            # process name: logs, --service
      module: research          # run as `python -m research`
      identity: my_project.research   # its module id (default: its ABIModule's)
```

Each entry also takes `args`, `env` (values may name `${ABI_NATS_URL}` and the
other variables), `enabled` and `restart` (`on-failure`, `always`, `never`).

Once the module is `READY`, Nexus lists its agent, the System app shows it on
the **Modules** tab and its job on the **Jobs** tab, and its app appears on the
Apps page.

Test it offline, with no broker:

```bash
uv run --with pytest pytest src/research/tests
```

## 7. Deploy it with Docker Compose

`abi new module` added a service to `docker-compose.override.yml`, which
Compose merges into the project's `docker-compose.yml`:

```yaml
services:
  research:
    build:
      context: ./src/research
      additional_contexts:
        abi_proto: ./.abi/libs/naas-abi-proto
        abi_sdk: ./.abi/libs/naas-abi-sdk
    restart: unless-stopped
    environment:
    - ABI_NATS_URL=nats://module:${NATS_MODULE_PASSWORD}@nats:4222
    - 'ABI_MODULE_KEY=${ABI_MODULE_KEY_RESEARCH:?...}'
    - ABI_DISCOVERY_PROJECT=my_project
    - LOG_LEVEL=${LOG_LEVEL:-INFO}
    depends_on:
      abi:
        condition: service_healthy
    networks:
    - abi-network
```

Build and start it with the stack:

```bash
docker compose up -d --build
docker compose logs -f research
```

- The image is built from the module's folder alone, with the SDK and proto
  packages from the `.abi` submodule; the project root is never sent.
- `abi deploy local --regenerate` never touches `docker-compose.override.yml`.
- **Replicas** (`docker compose up -d --scale research=2`) share the module's
  agent runs and jobs: one replica takes each job trigger.
- **Health probes:** set `ABI_HEALTH_PORT` (for example `8080`) to open
  `GET /health` (liveness) and `GET /ready` (200 only when discovery reports
  `READY`).
- **Tracing:** set `OTEL_EXPORTER_OTLP_ENDPOINT` (see
  [Observability](/architecture/observability)).
- **Rollouts:** set `ABI_ROLLOUT_ID` per deploy so the previous version keeps
  serving until the new one is ready, then drains.
- `SIGTERM` drains the module: it stops taking new work, finishes what it
  started, and unregisters.

## Run it by hand

Any supervisor can run the module. It needs the broker and its key:

```bash
ABI_NATS_URL=nats://module:<NATS_MODULE_PASSWORD>@127.0.0.1:4222 \
ABI_MODULE_KEY=$(abi module key my_project.research) \
ABI_DISCOVERY_PROJECT=my_project \
python -m research
```

`abi module key <module_id>` derives the key from the project's
`NATS_JWT_SECRET` (`$NATS_JWT_SECRET`, else `./.env`). Never give a module
`NATS_JWT_SECRET` itself. A module whose package has no `__main__` runs with
the SDK's runner instead: `naas-abi-module <package> --config module.json`,
where the JSON file holds the fields of the module's `Configuration`.

## A module in its own repository

```bash
abi new module research --standalone
```

It creates `./research/` with a `pyproject.toml`, a `Dockerfile` and a README,
for a team that ships the module separately. Until `naas-abi-sdk` and
`naas-abi-proto` are on PyPI, it installs them from the ABI repository, pinned
to the CLI's release tag (`--abi-ref` picks another branch, tag or commit). The
project that runs the engine gives it its key (`abi module key <module_id>`)
and the broker's `module` password.

## Reference

- [`naas_abi_sdk` reference](/reference/libraries/naas_abi_sdk): every public module of
  the SDK.
- [`naas_abi_proto`](/reference/libraries/naas_abi_proto/overview): the
  protobuf contracts and NATS subjects.
- `libs/naas-abi-sdk/README.md` in the ABI repository: the SDK's design notes
  (facades, invocation status and replay, transfers, discovery timing).
