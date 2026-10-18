# Nexus Web App

Nexus is the full-stack web application for ABI. It provides a browser-based interface for chatting with agents, browsing the knowledge graph, running apps, and managing workspaces and organizations.

---

## Architecture

Nexus lives in the ABI monorepo:

```bash
libs/naas-abi/naas_abi/apps/nexus/
├── apps/
│   ├── api/              # FastAPI backend, mounted on the core ABI API process under /api
│   └── web/              # Next.js frontend (its own process)
```

The Nexus API is wired into the engine by the `naas_abi` module: it receives the engine's configured services (triple store, object storage, secrets, email, and so on) when the API starts, and serves under `/api` next to the core routes (see the [REST API](/user-guide/build/applications/api)). The Next.js frontend is a separate process that calls the API.

---

## Starting Nexus

Nexus starts with the project:

```bash
abi dev up          # natively: the web app is the `nexus-web` service
abi stack start     # with Docker Compose
```

The web UI is at `http://localhost:3042` with the Docker stack. With `abi dev up`, ports are offset per checkout: `abi dev ports` prints the `nexus-web` and `api` ports. The API is at `http://localhost:9879` (Docker).

---

## Features

- **Agent chat**: conversation interface for the agents of the engine and of [remote modules](/user-guide/build/sdk/build-a-remote-module), with thread history and streaming responses.
- **Knowledge graph and ontology**: explore entities, relationships and ontology classes.
- **Workspace management**: multi-tenant workspaces with organization and membership management.
- **Files**: browse object storage and uploaded documents.
- **Search**: semantic search across the knowledge graph and vector store.
- **Apps**: the apps your modules ship (`apps/<name>/manifest.json`), enabled per workspace.
- **Marketplace**: the installed modules and the catalog.
- **System app** (super admins): the kernel services, modules, [jobs](/user-guide/build/modules/module-jobs), agents, NATS and traces. See [Observability](/developer-guide/architecture/observability).

Which sections a user sees depends on the workspace role and the `feature_flags` of `nexus_config` (`enabled_features` and `role_baseline` in the project's config).

---

## Authentication

### Local development

The project seeds a single admin account, `admin@example.com`, on first start. There is no default password: it is generated per project and read from `.env` at seed time via `NEXUS_USER_ADMIN_EXAMPLE_COM_PASSWORD`. Published defaults such as `admin` or `Admin1234!` are refused at login and replaced on boot.

### Password login vs. magic link

The `naas_abi` module's `nexus_config` in `config.yaml` (and `config.local.yaml` for the Docker stack) controls which method is active:

```yaml
modules:
  - module: naas_abi
    enabled: true
    config:
      nexus_config:
        auth_password_enabled: true     # password form
        # auth_password_enabled: false  # magic link / sign-in code only
```

Switch by editing the flag and restarting the backend (`abi dev down` then `abi dev up`, or `docker compose restart abi`). No frontend rebuild is required: the login page fetches `/api/auth/config` at runtime.

### Retrieving a magic link locally

With `auth_password_enabled: false`, a sign-in code and a magic link are sent by the email service. The default email adapter is SMTP on `localhost:1025`, which a fresh project does not run. For local development, store the emails in files instead:

```yaml
services:
  email:
    email_adapter:
      adapter: "filesystem"
      config:
        directory: "storage/email"
```

Each message is written to `storage/email/<id>.eml`: open the newest one for the code and the link. The link looks like:

```
http://localhost:3042/auth/magic-link?token=<token>
```

It expires after 15 minutes. Production deployments configure a real adapter (`smtp`, `ses`, `sendgrid` or `microsoft_outlook`).

---

## Tenant branding

Nexus supports per-deployment white-labeling, configured in the `tenant:` block of `nexus_config`:

```yaml
modules:
  - module: naas_abi
    enabled: true
    config:
      nexus_config:
        tenant:
          tab_title: "My AI Platform"
          logo_url: "https://cdn.example.com/logo.png"
          primary_color: "#22c55e"
          favicon_url: "https://cdn.example.com/favicon.ico"
```

No frontend rebuild is required. Branding changes take effect on config update and service restart. The block also holds the login page's colors and footer, and the external apps listed on the Apps page.

See [ADR: Tenant Provisioning](/user-guide/release-notes/config-driven-tenant-provisioning).

---

## Workspace routing

After login, Nexus redirects users to their workspace using a three-tier resolution: last-visited cookie, the `DEFAULT_WORKSPACE` environment variable of the web app, then a hardcoded fallback of `primary`.

**Production deployments must set `NEXUS_DEFAULT_WORKSPACE`** in `.env` (the Docker deployment maps it to `DEFAULT_WORKSPACE`) to match the slug of a workspace they seed under `organizations:`, or first-visit redirects will land on a 404.

See [ADR: Default workspace routing](/user-guide/release-notes/workspace-routing) for the full decision record.
