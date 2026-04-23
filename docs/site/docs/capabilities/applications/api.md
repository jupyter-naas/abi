# REST API

The ABI API is a FastAPI application that serves as the primary programmatic interface to the ABI stack. It auto-discovers and registers every loaded agent, workflow, and pipeline as API endpoints.

---

## Starting the API

```bash
# Development
make api
# or
uv run python -m naas_abi_core.apps.api.api

# Production (Docker)
make api-prod
```

Default port: **9879**

---

## API documentation

When the server is running:

- `http://localhost:9879/docs` - Swagger UI (interactive)
- `http://localhost:9879/redoc` - Redoc (readable)
- `http://localhost:9879/openapi.json` - OpenAPI spec

---

## Authentication

All endpoints require Bearer token authentication:

```bash
curl -X POST "http://localhost:9879/agents/abi/completion" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What organizations are in my knowledge graph?", "thread_id": 1}'
```

---

## Auto-registered endpoints

### Agents

Every loaded agent is available at:

```http
POST /agents/{agent_name}/completion
POST /agents/{agent_name}/stream-completion
```

Request body:
```json
{
  "prompt": "Your question or instruction",
  "thread_id": 1
}
```

### SPARQL query endpoint

```http
POST /graph/query
Body: { "query": "SELECT * WHERE { ?s ?p ?o } LIMIT 10" }
```

### Knowledge graph endpoints

```bash
GET  /graph/entities          # List entities
POST /abi/sync                # Trigger a data sync
GET  /ontology/classes        # List ontology classes
```

### Workspace and auth

```http
POST /auth/login
POST /auth/refresh
GET  /workspaces
GET  /organizations
```

---

## CORS

CORS origins are configured in `config.yaml` under `api.cors_origins`. This is the single source of truth - both the core API and the embedded Nexus API share the same origin list. See [ADR: CORS](/updates/cors-single-source-of-truth).

---

## Tenant configuration

The `/api/tenant` endpoint returns branding configuration for the current deployment (logo, colors, title). This is consumed by the Nexus frontend. Configuration is set in `config.yaml`. See [ADR: Tenant Provisioning](/updates/config-driven-tenant-provisioning).
