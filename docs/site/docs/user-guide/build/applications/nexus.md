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

Nexus has no login of its own: no password, magic link or one-time code. People sign in at an identity provider (`identity.providers` in the config); the built-in one (`naas-abi-idp`) is the default of `abi dev up`, `abi deploy local` and `abi new project`. The login page takes an email, the provider emails a 6-digit code, and the browser returns to Nexus with an httpOnly session cookie.

### Local development

The project seeds a single admin account, `admin@example.com` (`users:` in the `nexus_config`). The API makes it exist at the built-in provider when it starts, and its first sign-in links it to the Nexus account, which keeps the roles configured there. There is no password.

Under `abi dev`, the provider's mail is a file in `storage/email` (the filesystem email adapter): print the newest code with

```bash
abi dev code                          # mailed to admin@example.com
abi dev code --email bob@example.com
```

The email service of a Docker stack or a production deployment is configured with a real adapter (`smtp`, `ses`, `sendgrid` or `microsoft_outlook`); the sign-in codes and the invitations go through it.

Self-registration is off: add people by invitation (`abi user invite`, `abi iam invite`, or **Create user** in Organization settings, Users) or through `users:` in the configuration. Whether the provider lets anyone register is the provider's own setting (`ABI_IDP_SIGNUP`; `abi dev up` turns it on). To use another provider (Okta, Entra, Zitadel, Keycloak), add an `identity:` block: see `docs/identity-providers.md`.

### Scripts

A script uses a personal API key (`abi_pk_...`, made in Nexus under Account, API keys) as `Authorization: Bearer abi_pk_...`, for example `NEXUS_ACCESS_TOKEN=abi_pk_... abi workspace list`. The `/api/auth/*` and `/api/iam/*` routes take a signed-in session only.

### Upgrading accounts of the old login

Accounts of the removed password / magic-link login are moved with `abi user migrate` (a dry run), then `abi user migrate --apply`: each is made at the built-in provider with the same email. The person's first sign-in with the mailed code links the account, which keeps its roles, groups and data. Only the built-in provider links an account by verified email. The old settings (`auth_password_enabled`, `auth_signup_enabled`, `magic_link_*`, `otp_*`) are ignored with a warning.

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
