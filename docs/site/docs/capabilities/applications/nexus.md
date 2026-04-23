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
