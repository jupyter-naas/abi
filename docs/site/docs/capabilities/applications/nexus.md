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

Nexus has no login of its own: no password, magic link or one-time code. People sign in at an identity provider (`identity.providers`); the built-in one is the default of `abi dev up`, `abi deploy local` and `abi new project`. The login page takes an email, the provider emails a 6-digit code, and the browser returns with an httpOnly session cookie.

The local stack seeds a single admin account, `admin@example.com` (`users:` in the configuration). The API makes it exist at the built-in provider when it starts, and its first sign-in links it to the Nexus account, which keeps the roles configured there. There is no password.

### Retrieving the sign-in code locally

In `abi dev` the provider's mail is a file in `storage/email`. Print the newest code:

```bash
abi dev code                         # mailed to admin@example.com
abi dev code --email bob@example.com
```

### Scripts

A script uses a personal API key (`abi_pk_...`, made in Nexus under Account, API keys) as `Authorization: Bearer abi_pk_...`. The `/api/auth/*` and `/api/iam/*` routes take a signed-in session only.

### Upgrading accounts of the old login

Accounts of the removed password / magic-link login are moved with `abi user migrate` (a dry run) then `abi user migrate --apply`: each is made at the built-in provider with the same email. The person's first sign-in with the mailed code links the account, which keeps its roles, groups and data. Only the built-in provider links an account by verified email. The old settings (`auth_password_enabled`, `auth_signup_enabled`, `magic_link_*`, `otp_*`) are ignored with a warning.

---

## Workspace routing

After login, Nexus redirects users to their workspace using a three-tier resolution: last-visited cookie, `DEFAULT_WORKSPACE` env var, then a hardcoded fallback of `primary`.

**Production deployments must set `NEXUS_DEFAULT_WORKSPACE`** in `.env` to match their workspace slug, or first-visit redirects will land on a 404.

See [ADR: Default workspace routing](/updates/workspace-routing) for the full decision record.
