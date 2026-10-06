# Sign-up lock and brute-force limits

Status: Accepted

Date: 2026-09-24

## Context

With password login enabled (every scaffolded config), `/api/auth/register` let anyone who reached the login page create an account. Rate limiting existed but `Settings.model_post_init` switched it off whenever `ENVIRONMENT=development` or `NEXUS_ENV=local`, which are the defaults, so no shipped deployment had it. It was also missing from `/token`, magic-link verify, forgot and reset password. A wrong sign-in code was charged only to the newest code while being compared against every active one, and the per-code counter was a read-modify-write, so requesting fresh codes and guessing in parallel defeated the per-code cap. uvicorn trusted `X-Forwarded-For` from any client, so the per-IP key could be chosen by the caller. `/api/ollama/*` needed no session.

## Decision

- Self-registration is off by default (`auth_signup_enabled: false`). Accounts come from invitations or the config seed; `/api/auth/register` answers 403 and `/api/auth/config` reports `signup_enabled`.
- Rate limiting is on in every environment. Each credential endpoint checks the client IP (`rate_limit_ip_attempts`, default 20 per window) and, where an account is named, the email (`rate_limit_login_attempts`, default 5). Password and code checks count failures only, so sign-ins behind a shared IP are not blocked; endpoints that mint something (code requests, registration, reset) count every call.
- A wrong code is charged to every active code, and the counter is incremented with a single `UPDATE … RETURNING`.
- uvicorn trusts forwarded headers only from loopback and private networks (`FORWARDED_ALLOW_IPS` overrides).
- `/api/ollama/status` requires a session; pulling models and starting Ollama require a superadmin. `/app-html/` checks the app-html credential on the route as well as in the core middleware.
- `main_public_routes_test.py` lists every route reachable without a session; a new route without an auth dependency fails the build.

## Consequences

Deployments that relied on open registration must set `auth_signup_enabled: true`. Five wrong passwords or codes for one email within the window lock that email for the window, which an attacker can use to delay a victim's sign-in; the window is short (`rate_limit_window_seconds`, 5 minutes). Deployments behind a proxy outside private address space must set `FORWARDED_ALLOW_IPS`.
