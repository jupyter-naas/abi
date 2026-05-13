# Nexus Web App

Nexus is the full-stack web application for ABI. It provides a browser-based interface for chatting with agents, browsing the knowledge graph, and managing workspaces and organizations.

---

## Architecture

Nexus is integrated into the ABI monorepo as of February 2026:

```bash
libs/naas-abi/naas_abi/apps/nexus/
├── apps/
│   ├── api/              # FastAPI backend (mounted on the core ABI API process)
│   └── web/              # Next.js frontend
```

The Nexus FastAPI API is wired into the ABI Engine as a module - it receives the engine's configured services (TripleStore, VectorStore, BusService, etc.) at startup. The Next.js frontend and its backend share the same process.

---

## Starting Nexus

Nexus starts automatically with the full stack:

```bash
abi stack start
```

The web frontend is served at `http://localhost:9879` (or your configured port).

---

## Features

- **Agent chat**: conversation interface for all loaded ABI agents, with thread history and streaming responses.
- **Knowledge graph browser**: explore entities, relationships, and ontology classes.
- **Workspace management**: multi-tenant workspaces with organization and membership management.
- **File browser**: browse object storage and uploaded documents.
- **Search**: semantic search across the knowledge graph and vector store.

---

## Authentication

### Local development

The local stack seeds a single admin account on first start. Default credentials:

| Email | Password |
|---|---|
| `admin@example.com` | `Admin1234!` |

The password is read from `.env` at seed time via `NEXUS_USER_ADMIN_EXAMPLE_COM_PASSWORD`. Change it there before sharing the stack with others.

### Password login vs. magic link

`config.local.yaml` controls which method is active:

```yaml
nexus_config:
  auth_password_enabled: true   # password form
  # auth_password_enabled: false  # magic link form
```

Switch by editing the flag and restarting the backend:

```bash
docker compose restart abi
```

No frontend rebuild required. The login page fetches `/api/auth/config` at runtime.

### Retrieving a magic link locally

When `auth_password_enabled: false` and SMTP is not configured (the default for local dev), magic links are generated but not emailed. Retrieve the latest token directly from the database:

```bash
docker compose exec postgres psql -U abi -d nexus \
  -c "SELECT token, expires_at FROM magic_link_tokens ORDER BY created_at DESC LIMIT 1;"
```

Then open:

```
http://localhost:3042/auth/magic-link?token=<token>
```

Tokens expire after 15 minutes.

---

## Tenant branding

Nexus supports per-deployment white-labeling configured in `config.yaml`:

```yaml
modules:
  - module: "naas_abi.modules.core.nexus"
    enabled: true
    config:
      tenant:
        title: "My AI Platform"
        logo_url: "https://cdn.example.com/logo.png"
        primary_color: "#22c55e"
        favicon_url: "https://cdn.example.com/favicon.ico"
```

No frontend rebuild required. Branding changes take effect on config update and service restart.

See [ADR: Tenant Provisioning](/updates/config-driven-tenant-provisioning).

---

## Workspace routing

After login, Nexus redirects users to their workspace using a three-tier resolution: last-visited cookie, `DEFAULT_WORKSPACE` env var, then a hardcoded fallback of `primary`.

**Production deployments must set `NEXUS_DEFAULT_WORKSPACE`** in `.env` to match their workspace slug, or first-visit redirects will land on a 404.

See [ADR: Default workspace routing](/updates/workspace-routing) for the full decision record.
