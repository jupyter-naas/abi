---
sidebar_position: 6
---

# Security & Compliance

What ABI does for security, what it leaves to you, and how to place it in a compliance programme. ABI is self-hosted software: you run it on your own infrastructure, with your own network, identity provider and storage. It gives you the controls below; the certification of a deployment is a property of the whole deployment, not of the software.

:::info Professional Services Implementation
Security reviews, hardening and compliance mapping are done with our professional services team, customized to your requirements. Contact our enterprise team at [support@naas.ai](mailto:support@naas.ai) to discuss your needs and implementation timeline.
:::

This page is the operator's view. The design of the NATS layer (broker passwords, service tokens, module keys, remote app grants) and its known limits are in [Security model](/developer-guide/architecture/security).

## What ABI provides

### Sign-in and accounts

Nexus has no login of its own: people sign in at an OpenID Connect identity provider that the engine trusts (`identity.providers`), and Nexus keeps a session for them.

- **Identity providers.** The built-in provider (`naas-abi-idp`, the default of a generated project) signs people in with a 6-digit code emailed to them: authorization code with PKCE, rate-limited per address and per client IP (5 failures per address per 5 minutes by default). Okta, Entra, Zitadel, Keycloak or any other OIDC provider plugs in through the same `identity:` block, with its own MFA and policies (`docs/identity-providers.md`).
- **Sessions.** The browser holds an httpOnly, Secure, SameSite cookie the API issues; every request that changes state carries a CSRF token. A session ends when the provider refuses its refresh. Scripts use a personal API key (`abi_pk_...`, made under Account, API keys) that is stored hashed and shown once, and that can be narrowed.
- **No default password.** The seeded account is `admin@example.com`; it has no password, and signs in with the code the provider emails. Accounts of the older password / magic-link login are moved with `abi user migrate` and keep their roles and data.
- **Self-registration is off.** People come from invitations (`abi user invite`, `abi iam invite`, **Create user** in Organization settings) or from the `users:` list of the config. Whether a provider lets anyone register is the provider's setting.
- **Authorization is deny by default.** Every kernel service asks IAM on every call: roles and AWS-style policies decide, and the engine's tokens (ES256, short-lived) carry who is calling. Service accounts and their keys cover scripts and modules.

The REST API also accepts the shared `ABI_API_KEY` (as a bearer token or the `token` query parameter) for service-to-service calls. Treat it as a root credential: keep it in the secret store, rotate it when someone leaves, and do not put it in URLs you share.

### Access control

- **Organizations and workspaces.** Users belong to organizations (roles `owner`, `admin`, `member`) and to workspaces (roles `admin`, `member`, `viewer`).
- **Features by role.** The `nexus_config.feature_flags` of the config set which Nexus sections are on (`chat`, `files`, `agents`, `apps`, `marketplace`, `search`, `ontology`, `graph`, `settings`, and `code` with the coding stack) and which roles get them (`role_baseline`, with per-workspace overrides).
- **Super admins** (`is_superadmin: true`, or promoted in the platform settings) reach the platform's admin console and the System app. Keep that group small.
- **Remote apps** run in a sandbox with a grant bound to one app, one user and one workspace, for at most 8 hours, revoked at logout.

### Secrets

Secrets are read through the secret service, which composes adapters in order (`dotenv`, the Naas secret store, `base64`). The config refers to them as `{{ secret.NAME }}`. The System app masks secrets, and revealing one is a separate, audited action. See [Add secrets to production](/user-guide/deploy/add_secrets_to_production).

The generated stack creates its own secrets (database passwords, the broker's passwords, the callout's seed, the identity provider's client secret) on first run and writes them to `.env`, which is gitignored. The engine's signing keys are its own and live in the secret service. A module's service key is revoked on its own (`abi iam key revoke`): its next exchange and its next broker connection fail.

### Network and transport

- **Entry point.** Caddy is the only service the generated stack exposes on ports 80 and 443. It obtains a certificate from Let's Encrypt for a public domain, or you configure your own certificates.
- **The broker is private.** NATS (4222) and its monitoring port (8222) are published on `127.0.0.1` only. The broker requires a login (the static users `engine` and `auth`; every other connection is admitted by the engine's auth callout with the subjects its approved policy allows), but **traffic to it is not encrypted** and the monitoring endpoint has no authentication. Keep the broker on a private network; a module on another machine reaches it through a VPN or an SSH tunnel.
- **The MCP server** checks no credential of its own and calls agents with `ABI_API_KEY`: the generated stack publishes it on `127.0.0.1` only. Do not expose it.
- **Internal traffic** between the stack's containers uses the Docker network and is not encrypted. On a shared network, add your own encryption.
- **Remote modules run within their approved permissions.** Each logs in with its own service key and gets only the subjects its approved manifest allows (`abi iam module approve`); review a manifest before approving it. Some limits remain: see [Known limits](/developer-guide/architecture/security#known-limits).

### Audit and monitoring

- **System app** (super admins): every change to a service's data from the Data tab (create, replace, delete, reveal a secret) writes an audit row before it runs, needs the resource id typed back to confirm, and is open to super admins only. Cancelling an agent run is audited too.
- **Activity log service.** Events are recorded per actor, fail-open: a failed recording never breaks the call that produced it. The System app's Data tab browses them read-only.
- **Traces and live traffic.** With OpenTelemetry, one request is one trace across Nexus, the engine and the modules; live traffic shows metadata (service, method, caller, sizes, latency, status), never payloads. Logs and traces show remote app links as `/app-remote/[grant]/...`, never the grant.
- **Error codes.** Every failed kernel call carries an `Abi-Error-Code` header.

See [Observability](/developer-guide/architecture/observability). Keep production logs at `INFO`: at `DEBUG` the engine logs model prompts.

ABI does not ship a SIEM connector. Send the container logs and the traces to the log platform and SIEM you already run.

### Data and models

- **Data residency.** All data is in the stores you deploy. With local models (Ollama), no prompt leaves your network; with a cloud provider, prompts go to that provider. See [Air-gapped deployment](/user-guide/deploy/air-gapped).
- **Encryption at rest** is not done by ABI. Use disk or volume encryption, server-side encryption on S3, and your database's encryption.
- **Export and deletion.** The knowledge graph exports to Turtle (`make triplestore-export-turtle`) and to Excel. There is no built-in workflow for data-subject requests: locate and delete a person's data in each store (graph, documents, files, vectors, conversation memory) with your own procedure.

### Build and supply chain

The repository's `make check` runs `ruff`, `mypy` and `bandit` on every package (a pre-commit hook and CI run it), `make trivy-container-scan` scans the container image with Trivy, and CI runs the CLI end to end on every pull request into `main`. Pin and scan your own dependencies: `uv.lock` is committed so installs are reproducible.

2.x gets bug and security fixes from the `v2` branch until 2027-01-31 (see [Staying on 2.x](/user-guide/upgrade/v2-support)).

## What you provide

| Area | Your part |
|---|---|
| Identity | SSO, MFA and account lifecycle through your identity provider or proxy. |
| Network | Firewalls and segmentation (only Caddy public), private network for the broker, TLS certificates, VPN for remote modules. Network policies if you run on Kubernetes. |
| Encryption | At rest (volumes, S3, database) and between hosts. |
| Keys and secrets | Storage in a vault or secret manager; rotation of `ABI_API_KEY`, the broker's passwords and callout seed, and provider keys. |
| Logging | Retention and SIEM. |
| Backups | See [High availability and disaster recovery](/user-guide/deploy/high-availability). |
| Patching | The OS, Docker and the images of the stack's backing services, and ABI upgrades. |
| Policies | Access reviews, incident response, breach notification and retention. These are organizational processes ABI does not implement. |

## Compliance frameworks

ABI is open-source software and does not hold SOC 2, ISO 27001, FedRAMP, HIPAA or any other attestation by itself, and this page does not claim one. A framework applies to an organization and its systems. What ABI can do is make some controls easier to implement and evidence, in a deployment you control:

| Theme (SOC 2, ISO 27001, FedRAMP, HIPAA and GDPR share them) | What ABI offers | What the deployment must add |
|---|---|---|
| Access control and least privilege | Roles, feature flags per role, rate-limited sign-in, no self-registration, super admin separation | SSO and MFA, access reviews |
| Audit logging | System app audit rows, the activity log, traces | Log retention, protection and review |
| Data residency and isolation | Self-hosted; local models; air-gapped installs | Hosting location, physical and network controls |
| Secrets management | Secret service, masked secrets, generated credentials | A vault, rotation policy |
| Encryption | TLS at the edge (Caddy) | At rest, in transit between hosts, key management |
| Availability and recovery | Lease-based handover, restarts, snapshots | Replication, backups, tested recovery |
| Privacy rights (GDPR) | Graph export, per-store deletion | A data-subject request process |
| Change management | Versioned releases, a migration guide per major, committed lockfiles | Your approval and deployment process |

If you need a framework mapped to your deployment, or an assessment, the enterprise team can do it with you ([support@naas.ai](mailto:support@naas.ai)).

## Hardening checklist

1. Keep ports 4222 and 8222 on loopback or a private network; expose only Caddy.
2. Keep self-registration off; invite users.
3. Keep the number of super admins small, and review the service keys and approved module permissions (`abi iam key list`, `abi iam module list`) from time to time.
4. Set `ABI_API_KEY` to a long random value; rotate it when people leave.
5. Run at `LOG_LEVEL=INFO` in production.
6. Run remote modules only from code you trust; give each its own container.
7. Keep `.env`, `.env.dokploy` and `.snapshots/` out of git and out of images, and encrypt archives you move.
8. Encrypt the volumes, and back them up off the host.
9. Upgrade `naas-abi-core`, `naas-abi` and `naas-abi-cli` together, and read the release notes.
10. Regenerate the stack's files (`abi deploy local --regenerate`) after a CLI upgrade, so the broker's permission rules are current.

To report a vulnerability, write to [security@naas.ai](mailto:security@naas.ai).
