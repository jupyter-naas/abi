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
  `object_storage`, `secret`, `source_control`, `triple_store`,
  `vector_store`. All calls are `async`.
- Every agent is declared in `ABIModule.agents` (an `AgentDescriptor` with the
  `agent.invoke.v1` capability) **and** bound in `on_initialized` with
  `self.expose_agent(name, agent.as_handler())`, before the module is READY.
- Workflows (`workflows/`), pipelines (`pipelines/`) and integrations
  (`integrations/`) are written like in-engine ones, on `naas_abi_sdk` only
  (`naas_abi_sdk.workflow`, `.pipeline`, `.integration`). `ABIModule` finds every
  workflow and pipeline class under its folder and builds it after
  `on_initialized`: with `New(module)` if the class has one, else with an empty
  `<Name>Configuration`. One that needs arguments is bound in `on_initialized`
  with `self.expose_workflow(name, instance)` / `self.expose_pipeline(...)`, or
  the module does not start. The name is the class name in snake case. An agent
  takes its tools when it is built, in `on_initialized`: call
  `await self.build_processes()` there first (idempotent; bind the classes that
  need arguments before it), then `self.get_workflow(name).as_tools()`.
- Scheduled or event-driven work is a `@job(...)` method (`Every`, `Cron`,
  `OnEvent` triggers from `naas_abi_sdk.jobs`). Delivery is at least once.
- Ontologies are the `.ttl` files of `ontologies/`: sent to the engine's schema
  graph once the module is READY, additively, and retried in the background if
  a load fails. A module with ontologies declares `triple_store`. See
  `ontologies/AGENTS.md`.
- Keep `MODULE_ID` stable: discovery, job subjects and agent memory use it.

## Files

| File | What |
|---|---|
| `__init__.py` | `ABIModule`: id, configuration, dependencies, agents, jobs, lifecycle |
| `__main__.py` | `python -m {{module_name_snake}}`: `run_module` with discovery, signals |
| `agents/` | SDK `IntentAgent`s on the engine's models, memory in the Document Service |
| `workflows/` | `Workflow`s (`async run(parameters)`), found and built by `ABIModule` |
| `pipelines/` | `Pipeline`s (`async run(parameters)` returning an rdflib `Graph`), likewise |
| `integrations/` | `Integration`s: how to reach a third-party tool (not served; built by workflows, pipelines, agents) |
| `jobs.py` | job bodies, testable without a broker |
| `apps/` | web apps, served through Nexus at `/app-html/remote/{{module_id}}/<app>/` |
| `ontologies/` | `.ttl` files sent to the engine's schema graph as `module/{{module_id}}/<path>` |
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
- A workflow: `abi new workflow <Name> workflows` from this folder. Its agents
  use it with `await self.build_processes()` then
  `self.get_workflow("<name>").as_tools()` in `on_initialized`, before creating
  the agent, passed as `create_agent(..., tools=tools)` (the name is printed).
  Reads credentials with `await module.engine.services.secret.get("KEY")` in
  `New(module)`.
- A pipeline: `abi new pipeline <Name> pipelines`; it returns an rdflib `Graph`
  the module can write with `self.engine.services.triple_store`.
- An integration: `abi new integration <Name> integrations`.
- A service: add it to `dependencies`, call `self.engine.services.<name>`.
- An ontology: add a `.ttl` file under `ontologies/` (see `ontologies/AGENTS.md`);
  the module sends it at its next start.
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
