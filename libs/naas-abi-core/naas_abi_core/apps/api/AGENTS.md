# ABI kernel API

> Scope: `libs/naas-abi-core/naas_abi_core/apps/api/`. Canonical reference for the FastAPI kernel.

## Purpose

The kernel HTTP app. Every loaded **Expose** process that actually registers routes becomes an endpoint. Agents already were. Workflows, pipelines, and module tools now follow the same rule.

Empty stubs do not appear in OpenAPI. A LangChain-only `BaseTool` stays agent-internal.

## Files

| File | Role |
|---|---|
| `api.py` | FastAPI app, auth, `_load_runtime_routes` |
| `abi_api_key_auth.py` | Bearer / query-token check |
| `openapi_doc.py` | Landing HTML and tag copy |
| `../utils/process_api.py` | Instantiate processes; mount `as_api` or a default `run()` POST |

## What `_load_runtime_routes` mounts

1. **Agents** (`/agents`): `agent.New()` then `agent.as_api(agents_router)`. Unchanged.
2. **Workflows** (`/workflows`): every `module.workflows` instance through `mount_module_processes`.
3. **Pipelines** (`/pipelines`): same for `module.pipelines`.
4. **Tools** (`/tools`): only items on `module.tools` that implement `as_api`. No invented `POST /tools/{name}` for LangChain tools.

`/workflows`, `/pipelines`, and `/tools` routers are included only when they have routes, so OpenAPI does not advertise dead tags.

5. **Module routes**: each module's `api(app)` hook, through `module_routes.mount_module_apis`. Every route and mount a module adds there answers only a request with a credential the engine accepts (`ABI_API_KEY`, or one a registered validator vouches for: the `/app-html/` check), else 401. A module opts out explicitly (`BaseModule`): `api_checks_its_callers = True` when every route it mounts checks its caller itself (`naas_abi`, which mounts the Nexus API), or `unguarded_api_paths` for public files (logos, portraits) and routers with their own caller check (People, Personnel Cockpit). The guard finds the route a request reaches as the router does (same routes, same order, same scope; never the URL rebuilt from `Host`), and runs innermost, inside CORS. `/app-html/` keeps its own middleware.

Discovery happens in `BaseModule.on_load` (class walk). Instantiation happens in `on_initialized` (services are up). See [module/AGENTS.md](../../module/AGENTS.md).

## Default `run()` POST

If `as_api` adds no routes, the kernel registers `POST /{class_slug}` only when:

- the class overrides `run` (not `Workflow.run` / `Pipeline.run`)
- the first parameter is a Pydantic model

`rdflib.Graph` results are returned as `{"format": "turtle", "data": "..."}`.

## Tests

```bash
uv run pytest libs/naas-abi-core/naas_abi_core/utils/process_api_test.py -v
uv run pytest libs/naas-abi-core/naas_abi_core/module/ModuleComponentLoader_test.py -v
uv run pytest libs/naas-abi-core/naas_abi_core/apps/api/api_test.py -v
```

`process_api_test.py` uses fixture workflows, pipelines, and tools. It does not invent customer agents.

`api_test.py` boots the real engine. It needs a working local config. If ABI services are missing, report that rather than weakening the test.

## Local curl

After `abi dev up` (API port from `abi dev ports`):

```bash
# Auth: there is no token endpoint. Send the configured ABI_API_KEY as
# `Authorization: Bearer <key>` (or `?token=<key>`), as in the examples below.

# OpenAPI: agent paths stay; process paths appear only when live
curl -s "http://127.0.0.1:<api-port>/openapi.json" | python -c \
  "import json,sys; p=json.load(sys.stdin)['paths'];
print('\n'.join(sorted(k for k in p if k.startswith(('/agents','/workflows','/pipelines','/tools')))))"

# Example default run() (only if that class is loaded and constructible)
curl -s -X POST "http://127.0.0.1:<api-port>/workflows/<slug>" \
  -H "Authorization: Bearer ${ABI_API_KEY:-abi}" \
  -H "Content-Type: application/json" \
  -d '{}'
```

Issue: [jupyter-naas/abi#1202](https://github.com/jupyter-naas/abi/issues/1202). Related: #1195 (CLI / Nexus list), #1011 (engine catalog).
