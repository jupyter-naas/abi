# REST API

The ABI API is a FastAPI application and the primary programmatic interface to the ABI stack. It auto-discovers every agent, workflow and pipeline of the modules the engine loads and registers them as endpoints. The Nexus API is mounted on the same process, under `/api`.

---

## Starting the API

```bash
# Natively: Oxigraph, NATS, the API and Nexus web
abi dev up

# With Docker Compose
abi stack start
```

The API listens on port **9879** by default. `abi dev up` offsets the ports per checkout so several projects can run side by side: `abi dev ports` prints the live ones. In the ABI repository, `make api` runs the API alone (`uv run python -m naas_abi_core.apps.api.api`); in a NATS project it needs a broker.

The first boot takes a few minutes: the engine loads every module and ontology. The API is ready when `/docs` answers. For a production deployment, see [Deploy](/user-guide/deploy/overview).

---

## API documentation

When the server is running:

- `http://localhost:9879/docs` - Swagger UI (interactive)
- `http://localhost:9879/redoc` - Redoc (readable)
- `http://localhost:9879/openapi.json` - OpenAPI spec

(Use the `api` port printed by `abi dev ports` with `abi dev up`.)

---

## Authentication

The routes the engine registers (`/agents`, `/workflows`, `/pipelines`, `/tools`) require the project's API key as a Bearer token. It is `ABI_API_KEY` in the project's `.env`:

```bash
curl -X POST "http://localhost:9879/agents/Abi/completion" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What organizations are in my knowledge graph?", "thread_id": 1}'
```

There is no token endpoint for these routes. The key can also be sent as `?token=<key>`.

The Nexus routes under `/api` use the Nexus sign-in instead: `POST /api/auth/login` returns an access token and a refresh token, `POST /api/auth/refresh` renews it. See [Nexus](/user-guide/build/applications/nexus#authentication).

---

## Auto-registered endpoints

### Agents

Every agent the engine loads is available at:

```http
POST /agents/{agent_name}/completion
POST /agents/{agent_name}/stream-completion
```

`{agent_name}` is the agent's `name`, with characters other than letters, digits, `_` and `-` replaced by `_`. Request body:

```json
{
  "prompt": "Your question or instruction",
  "thread_id": 1
}
```

`stream-completion` answers with server-sent events.

### Workflows, pipelines and tools

A workflow or pipeline whose `run(parameters)` takes a Pydantic parameters model gets a route, named after its class in snake case:

```http
POST /workflows/{workflow_name}
POST /pipelines/{pipeline_name}
POST /tools/{tool_name}
```

The body is the parameters model. A pipeline's graph comes back as `{"format": "turtle", "data": "..."}`. A class can override `as_api` for a different surface. Empty stubs are not published, and a LangChain-only tool is not given a REST route. See [Creating a Workflow](/user-guide/build/agents/creating-a-workflow) and [Creating a Pipeline](/user-guide/build/knowledge-graph/creating-a-pipeline).

### Agents of remote modules

Agents published by [remote modules](/user-guide/build/sdk/build-a-remote-module) have no `/agents/...` route. Call them through the chat API, which selects them by **id**:

```http
POST /api/chat/stream
POST /api/chat/complete
```

### The Nexus API

The Nexus API is served under `/api`: authentication (`/api/auth/...`), organizations and workspaces (`/api/organizations`, `/api/workspaces`), chat (`/api/chat/...`), the knowledge graph (`/api/graph/...`, `/api/ontology/...`, `/api/search`), modules and apps (`/api/modules`, `/api/apps`), files, and the admin and System endpoints. Its OpenAPI document is part of `/openapi.json`; browse it in Swagger UI.

---

## CORS

CORS origins are configured in `config.yaml` under `api.cors_origins`. This is the single source of truth - both the core API and the embedded Nexus API share the same origin list. See [ADR: CORS](/user-guide/release-notes/cors-single-source-of-truth).

---

## Tenant configuration

The `/api/tenant` endpoint returns the branding configuration of the deployment (tab title, logo, colors). It is consumed by the Nexus frontend and set in the `tenant:` block of the `naas_abi` module's `nexus_config` in `config.yaml`. See [Nexus](/user-guide/build/applications/nexus#tenant-branding) and [ADR: Tenant Provisioning](/user-guide/release-notes/config-driven-tenant-provisioning).
