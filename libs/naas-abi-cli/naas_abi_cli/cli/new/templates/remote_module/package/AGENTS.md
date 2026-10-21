# {{module_name_snake}} — AGENTS.md

A **remote ABI module** (`module_id = "{{module_id}}"`). It runs in its own
process and reaches the engine only through NATS, with `naas-abi-sdk`. The
engine does not load it: it registers itself in the engine's module registry
(discovery project `{{discovery_project}}`), and Nexus lists its agents next to
the engine's.

## Rules

- **Never import `naas_abi_core`** (or `naas_abi`, `naas_abi_marketplace`).
  The Dockerfile fails the build if core is installed, and
  `tests/module_test.py` fails if anything imports it. Use `naas_abi_sdk`.
- Reach engine services through `self.engine.services.<name>`, and declare
  each one in `ModuleDependencies(services=(...))`: undeclared calls are
  refused. Available: `activity_log`, `bus`, `cache`, `coding_environment`,
  `dataset`, `document`, `email`, `event`, `keyvalue` (`kv`), `model_registry`,
  `object_storage`, `secret`, `source_control`, `tool_registry` (read the
  engine's tool catalog: list, get, search; `invoke` runs an engine tool on the engine, with a
  secret referenced by name, only as far as the operator granted this module),
  `triple_store`, `vector_store`. All calls are `async`.
- Every agent is declared in `ABIModule.agents` (an `AgentDescriptor` with the
  `agent.invoke.v1` capability) **and** bound in `on_initialized` with
  `self.expose_agent(name, agent.as_handler())`, before the module is READY.
- A module can also publish tools for the engine's agents: declare
  `tools = (ToolDescriptor(...),)` and bind each with `self.expose_tool(name, handler)`
  in `on_initialized` (install `naas-abi-sdk[tools]`). Arguments arrive validated against
  the input schema; by default only the engine may call them (`authorize_tool`). Engine
  secrets never reach the module: keep its credentials in its own environment.
- Scheduled or event-driven work is a `@job(...)` method (`Every`, `Cron`,
  `OnEvent` triggers from `naas_abi_sdk.jobs`). Delivery is at least once.
- Keep `MODULE_ID` stable: discovery, job subjects and agent memory use it.

## Files

| File | What |
|---|---|
| `__init__.py` | `ABIModule`: id, configuration, dependencies, agents, jobs, lifecycle |
| `__main__.py` | `python -m {{module_name_snake}}`: `run_module` with discovery, signals |
| `agents/` | SDK `IntentAgent`s on the engine's models, memory in the Document Service |
| `jobs.py` | job bodies, testable without a broker |
| `apps/` | web apps, served through Nexus at `/app-html/remote/{{module_id}}/<app>/` |
| `tests/` | offline tests (`uv run pytest`) |

## Run it

| Where | How |
|---|---|
| `abi dev up` (in the project) | started from `dev.modules` in `config.yaml`; `abi dev logs {{module_name}}` |
| Docker (`abi start`) | the `{{module_name}}` service in `docker-compose.override.yml` |
| By hand | `ABI_NATS_URL=nats://module:<NATS_MODULE_PASSWORD>@127.0.0.1:4222 ABI_MODULE_KEY=$(abi module key {{module_id}}) python -m {{module_name_snake}}` |

It is up when it logs `READY`. `ABI_HEALTH_PORT=8080` opens `/health` and
`/ready`.

## Add to it

- An agent: `abi new agent <Name> agents` from this folder, then declare and
  expose it in `ABIModule`.
- A service: add it to `dependencies`, call `self.engine.services.<name>`.
- Another module's agent: add its id to `ModuleDependencies(modules=(...))`,
  then `await self.engine.modules["<id>"].get_agent("<Name>")`.
- An app: `abi new app <name> apps` from this folder. Nexus lists it on its
  Apps page while the module runs. For a backend, bind an ASGI app (FastAPI)
  in `on_initialized`: `self.expose_app("<name>", api)`; the page calls it
  with relative URLs (`fetch("api/...")`), and
  `request.scope["abi"]["user_id"]` is the signed-in user,
  `request.scope["abi"]["workspace_id"]` the workspace they opened the app
  from (enable it on that workspace's Apps page). The page runs
  sandboxed: no `localStorage` or `document.cookie`, and absolute URLs start
  with `root_path`. Bodies stream: read
  an upload with `request.stream()` (pass it to
  `put_object_stream(prefix, key, request.stream())`), answer with a
  `StreamingResponse`. Uploads up to `max_upload_bytes` in the manifest
  (default 1 GiB); an app idle for 60 s gets 504.

SDK reference: the ABI repository's `libs/naas-abi-sdk/README.md`.
