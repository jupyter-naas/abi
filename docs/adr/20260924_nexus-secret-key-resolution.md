# Nexus secret key resolution

Status: Accepted

Date: 2026-09-24

## Context

The Nexus `SECRET_KEY` signs every JWT (sessions, app-html links, coding-agent tokens), keys the OTP HMAC and derives the Fernet key that encrypts workspace secrets. `ABIModule.on_initialized` built the Nexus `Settings` from `NexusConfig.model_dump()`, which passed every default as an init kwarg. pydantic-settings ranks init kwargs above the environment, so `SECRET_KEY` and `ENVIRONMENT` from the environment were ignored and no shipped config set them. Every deployment signed tokens with the published default `change-me-in-production`, and the startup guard never fired because `environment` stayed `development`. Anyone could forge a session for any user and decrypt stored secrets.

The core API also exposed `POST /token`, which returned `ABI_API_KEY` for the hard-coded password `abi` on the public API host.

## Decision

`POST /token` is removed. `ABI_API_KEY` is configured out of band and never issued over HTTP; the OpenAPI scheme is plain bearer.

`secret_key`, `environment` and `nexus_env` are forwarded from `NexusConfig` only when set in yaml, so the environment applies otherwise. An explicit yaml value still wins.

When the resolved key is a known default, the API process resolves it in `ABIModule.api()`: use `SECRET_KEY` from the engine secret store, else generate one and persist it there (`.env` with the dotenv adapter). Boot fails if the generated key does not read back, since an in-memory key would orphan secrets on restart. Only the API process generates, so Dagster and CLI engines never race it to write a different key. Only known default values count as insecure; an operator's own key is never replaced.

Consumers read the key at call time through `current_secret_key()`, because `naas_abi` replaces `settings` after the Nexus modules may have imported it.

On startup the API re-encrypts workspace secrets still readable only with a known default key under the current key.

## Consequences

Upgraded deployments get a real key on first boot. Existing sessions, pending OTPs and preview links become invalid once, and users sign in again. Workspace secrets are migrated automatically; after that the default key opens nothing.

Rate limiting, HSTS and the production CSP now follow `ENVIRONMENT` / `NEXUS_ENV` from the environment instead of being always off.

Clients that fetched the API key from `/token` must be given `ABI_API_KEY` directly.
