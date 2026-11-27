# Security

This page is for two readers: people who report a vulnerability, and organisations that run ABI
on their own infrastructure, including deployments with no connection to the vendor. It describes
the code and configuration of this repository as they are. **TODO (maintainers)** marks a decision
not made yet; *to be tested* marks a procedure that has not been run end to end.

- [Reporting a vulnerability](#reporting-a-vulnerability)
- [Software bill of materials](#software-bill-of-materials)
- [Reference architecture: isolated deployment on Azure](#reference-architecture-isolated-deployment-on-azure)
- [Network egress and telemetry](#network-egress-and-telemetry)
- [Backup, restore and upgrade](#backup-restore-and-upgrade)

## Reporting a vulnerability

Do not report a vulnerability in a public issue, pull request or discussion. Email
**security@naas.ai** with:

1. what the vulnerability is and what an attacker can do with it;
2. the steps to reproduce it;
3. the affected components and versions (package versions, image tags or commit);
4. a fix, if you have one;
5. how to reach you.

> **TODO (maintainers):** GitHub private vulnerability reporting would give reporters a second,
> private channel. List it here once it is on for this repository.

What happens next:

1. The report is acknowledged, then assessed and given a severity.
2. A fix is developed and released: new package versions on PyPI
   ([`release.yml`](.github/workflows/release.yml)) and new container images on GitHub Container
   Registry ([`build_abi_container.yml`](.github/workflows/build_abi_container.yml),
   [`build_nexus_web_container.yml`](.github/workflows/build_nexus_web_container.yml)).
3. A GitHub security advisory is published, crediting the reporter unless they prefer to stay
   anonymous. Disclosure is coordinated: keep the details private until the advisory is out.

| Severity | Acknowledgement within | Fix released within |
|---|---|---|
| Critical | TODO | TODO |
| High | TODO | TODO |
| Medium | TODO | TODO |
| Low | TODO | TODO |

> **TODO (maintainers):** set these targets and say which release lines receive security fixes.
> The Nexus application's own policy,
> [`libs/naas-abi/naas_abi/apps/nexus/SECURITY.md`](libs/naas-abi/naas_abi/apps/nexus/SECURITY.md),
> states targets for Nexus: keep one source.

## Software bill of materials

No workflow in [`.github/workflows`](.github/workflows) produces a CycloneDX or SPDX SBOM today.

What exists:

- **Locked dependencies.** [`uv.lock`](uv.lock) at the root and one per package under `libs/`;
  [`pnpm-lock.yaml`](libs/naas-abi/naas_abi/apps/nexus/pnpm-lock.yaml) for the Nexus web app.
- **Checks on every pull request to `main`** ([`pull_request.yml`](.github/workflows/pull_request.yml)):
  `make check` runs bandit on `naas-abi-core`, `naas-abi-cli` and `naas-abi` (medium severity and
  confidence and above); `make trivy-container-scan` scans the `abi` image with Trivy. The Trivy step
  reports findings and does not fail the job ([`Makefile`](Makefile)).
- **Releases.** Packages go to PyPI through trusted publishing (an OIDC token, no stored password;
  the publish action is pinned to a commit). The `abi` and `nexus-web` images go to GitHub Container
  Registry when a release is published.

> **TODO (maintainers):** generate a CycloneDX (or SPDX) SBOM for each published package and image
> in the release workflows, and attach it to the GitHub release.

Until then, generate the SBOM from the exact images you deploy, for example
`trivy image --format cyclonedx --output abi.cdx.json <registry>/abi@<digest>`, and keep it with
the deployment record.

## Reference architecture: isolated deployment on Azure

This maps the services of the Docker deployments in this repository
([`docker-compose.yml`](docker-compose.yml), and the `abi deploy local` and `abi deploy dokploy`
templates under
[`libs/naas-abi-cli/naas_abi_cli/cli/deploy/templates/`](libs/naas-abi-cli/naas_abi_cli/cli/deploy/templates/))
to Azure services, for an engine on NATS (the default) that never reaches the vendor. It has not
been deployed as written: treat it as a design to validate.

### Runtime components

| Component | Compose service | Data it keeps | Azure target |
|---|---|---|---|
| Nexus web (Next.js, port 3000) | `nexus-web` | none | Azure Container Apps |
| ABI API: engine, REST API and Nexus API (port 9879) | `abi` | see [The ABI API](#the-abi-api) | Azure Container Apps, one replica |
| Built-in identity provider | `idp` | in the engine's stores | Azure Container Apps, only if it is a configured provider |
| NATS with JetStream | `nats` | bus streams, KV buckets, module registry, job schedules, the engine lease | AKS (StatefulSet) or a VM, on a managed disk |
| Apache Jena Fuseki (TDB2) | `fuseki`, `fuseki-compact` | knowledge graph | AKS or a VM, on a managed disk; compaction as a scheduled job |
| Qdrant | `qdrant` | vectors | AKS or a VM, on a managed disk |
| PostgreSQL | `postgres` | IAM (schema `abi_iam`) and documents in `POSTGRES_DB`; databases `nexus` and `ducklake` (dataset catalog) | Azure Database for PostgreSQL Flexible Server |
| Redis | `redis` | durable keys (run with `--appendonly yes`) and caches | Azure Managed Redis |
| Object storage, S3 API | `minio`, `minio-init` | objects (bucket `abi`) | S3-compatible storage: MinIO on AKS or a VM, on a managed disk |
| Mail | none: an `email` adapter | none | the organisation's SMTP relay (`smtp`) or Microsoft Graph (`microsoft_outlook`) |
| Images | pulled from Docker Hub, GHCR, Codeberg | | Azure Container Registry |
| Secrets | `.env` files, `dotenv` adapter | see [Secrets](#secrets-azure-key-vault) | Azure Key Vault |
| Sign-in | `identity.providers` | | Microsoft Entra ID (OIDC) |
| Models | model registry | | Azure AI Foundry deployments, see [Models](#models) |
| Reverse proxy | `caddy` (local), Traefik (Dokploy) | none | Azure Application Gateway (WAF) in front of internal Container Apps ingress |

Notes:

- The object storage adapters are `fs`, `s3`, `naas`, `r2` and `nats_rpc`. The `s3` adapter takes an
  `endpoint_url`, so any S3-compatible store works. An Azure Blob Storage adapter is planned; until it
  ships, use an S3-compatible store.
- The code creates no PostgreSQL extension. The coding environment adds databases `coder` and
  `forgejo`; legacy Dagster uses `POSTGRES_DB`.
- Several images float (`stain/jena-fuseki:latest`, `qdrant/qdrant:latest`, `redis:7-alpine`) and
  the compose files pull with `pull_policy: always`. Import each image into Azure Container Registry
  once (`az acr import`) and deploy it by digest.

### The ABI API

- **One replica.** On NATS, exactly one engine per NATS account serves the kernel services, under a
  lease ([`engine/ownership/AGENTS.md`](libs/naas-abi-core/naas_abi_core/engine/ownership/AGENTS.md)).
  A second engine fails at start, unless it carries another `ABI_ROLLOUT_ID`: it then stands by and
  takes over when the first stops. That handover is refused while a service the engine owns keeps its
  data on the local host.
- **Local data.** The shipped configurations keep some data on the container's disk: the event log
  (`sqlite`, `storage/events/events.sqlite` by default), DuckLake table data
  (`data_path: storage/datasets/`), filesystem mail, and the writable secret file. Move them to
  shared backends (event adapter `postgresql`; DuckLake `data_path: s3://…`; mail `smtp`) or mount
  persistent storage. Otherwise they are lost when the container is replaced.
- **Model weights.** With the marketplace document module on, Docling weights are cached in the
  `huggingface_cache` volume. Pre-load that cache or leave the module off.

### Not for production

These services exist in the compose files for development. Do not deploy them:

| Service | What it is | Where |
|---|---|---|
| `yasgui` | SPARQL editor UI | root compose, `abi deploy local` |
| `redis-commander` | Redis admin UI | root compose, `abi deploy local` |
| `service-portal` | page linking every UI | root compose, `abi deploy local` |
| `graph-explorer` | graph explorer UI | root compose, `abi deploy local` |
| MinIO console | port 9001 of `minio` | root compose, `abi deploy local` |
| `headscale` | VPN mesh control server | root compose (`headscale` profile), `abi deploy local --headscale` |
| `coder`, `forgejo`, `act-runner`, `coding-init` | browser code workspaces, git forge, CI runner; `coder`, `act-runner` and `coding-init` mount the Docker socket | `coder` and `forgejo` in the root compose; all four with `abi deploy local --coding` or `abi deploy dokploy --coding` |
| `dagster`, `rabbitmq` | legacy orchestration and bus, with admin UIs | `legacy` profile, or an engine without NATS |

`mcp-server` checks no inbound credential and calls agents with `ABI_API_KEY`: leave it out, or keep
it internal. No tracing UI ships in the compose files (see [Telemetry](#telemetry)).

### Network

- Put everything in one virtual network: a Container Apps environment with internal ingress only,
  AKS (private cluster) or VMs in private subnets, and private endpoints with public access off for
  PostgreSQL, Redis, Key Vault, Container Registry and the model endpoint.
- Publish one entry point: an Application Gateway that serves two host names over HTTPS, the web host
  (`nexus-web:3000`) and the API host (`abi:9879`). The browser calls the API host, and the sign-in
  callback (`/api/auth/oidc/callback`) and the built-in provider (`/idp`) are on it
  ([`Caddyfile`](.deploy/docker/Caddyfile)). Nothing else is published: not NATS (4222, and 8222,
  whose monitoring endpoint has no authentication), Fuseki (3030), Qdrant (6333, 6334), Redis, MinIO
  (9000, 9001) or the MCP server (8000).
- [`nats.conf`](.deploy/docker/nats/nats.conf) has no TLS block: broker traffic stays inside the
  private network. Every connection authenticates: the engine and its auth callout responder as two
  static users, modules through the auth callout with their own service key.
- The compose files run Qdrant without an API key and Redis without a password. Set both: the Qdrant
  adapter takes `api_key` and `https`; the Redis adapters take a URL. Azure Managed Redis and Flexible
  Server enforce TLS and authentication by default: set the connection URLs accordingly
  (*to be tested*).
- `api.cors_origins` lists only the deployment's own web and API hosts. `ABI_API_KEY` is a static
  bearer key for the engine REST API: store it in Key Vault and make it long and random.

### Sign-in: Microsoft Entra ID

Nexus has no login of its own: people sign in at an OIDC provider the engine trusts
([`EngineConfiguration_Identity.py`](libs/naas-abi-core/naas_abi_core/engine/engine_configuration/EngineConfiguration_Identity.py),
[`services/identity/AGENTS.md`](libs/naas-abi-core/naas_abi_core/services/identity/AGENTS.md)).

```yaml
identity:
  default_provider: entra
  providers:
    - name: entra
      issuer: https://login.microsoftonline.com/<tenant-id>/v2.0   # tenant-specific: common/organizations are refused
      client_id: <application id>
      client_secret: "{{ secret.ENTRA_CLIENT_SECRET }}"
      groups_claim: groups          # Entra sends group object IDs
      scopes: [openid, email, profile, offline_access]
      provisioning: none            # people are managed in Entra; an invitation is a pending grant
      trust_email: true             # Entra sends no email_verified
```

- Register the redirect URI `<API URL>/api/auth/oidc/callback` and the post-logout URI
  `<web URL>/auth/login`. Issuers must use `https`.
- Above 200 groups Entra sends an overage claim instead of `groups`.
- Map groups to IAM groups or roles (`iam.map_idp_group`, `iam.bind_idp_group`).
- With Entra ID as the only provider the built-in provider (`idp`) is not in the sign-in path; running
  without it is *to be tested* (the `users:` seed provisions people at the built-in provider).
- The engine reads the issuer's discovery document and JWKS, and Nexus refreshes sessions at the
  provider at least every 10 minutes: allow outbound HTTPS to the Entra ID endpoints.

### Secrets: Azure Key Vault

- When the configuration renders `{{ secret.NAME }}`, the process environment wins over the secret
  adapters ([`EngineConfiguration.py`](libs/naas-abi-core/naas_abi_core/engine/engine_configuration/EngineConfiguration.py)).
  The adapters are `dotenv`, `naas` (the vendor's API), `base64`, `nats_rpc` and `custom`; there is no
  Key Vault adapter.
- Keep the bootstrap secrets (database, Fuseki, Redis, Qdrant, MinIO and NATS credentials,
  `NATS_AUTH_CALLOUT_SEED`, `ABI_API_KEY`, the OIDC client secret) in Key Vault and hand them to the
  containers as environment variables: Container Apps secrets that reference Key Vault, or the Secrets
  Store CSI driver on AKS.
- The engine also writes to its secret store at runtime: IAM signing keys and its own service key
  (under `iam/`), and `NEXUS_SECRETS_KEY`, which encrypts workspace secrets, when none is configured.
  With the `dotenv` adapter that store is a file: keep it on persistent, access-restricted storage and
  back it up. Losing `NEXUS_SECRETS_KEY` loses the workspace secrets.

> **TODO (maintainers):** a Key Vault secret adapter, so that runtime-written secrets need no file.

### Models

Agents ask the model registry for a canonical model ID; provider modules register the models
([`services/model_registry/AGENTS.md`](libs/naas-abi-core/naas_abi_core/services/model_registry/AGENTS.md)).
Only modules listed in the configuration with `enabled: true` load.

- No module serves Azure AI Foundry yet: the marketplace `azure` module
  ([`ai/azure/__init__.py`](libs/naas-abi-marketplace/naas_abi_marketplace/ai/azure/__init__.py))
  takes a key and registers no model. Until one exists, register the Foundry deployments' chat and
  embedding models from a project module under canonical IDs, and point
  `services.model_registry.default_chat_model` and `default_embedding_model` at them. Self-hosted
  models through the Ollama module (`base_url`) are the other option.
- A project from `abi new project` enables the OpenRouter module (a hosted model gateway): turn it off.
- Register the embedding model Nexus uses for chat files (see
  [Model providers outside the registry](#model-providers-outside-the-registry)).

> **TODO (maintainers):** a provider module for Azure AI Foundry (or any OpenAI-compatible endpoint
> with a configurable base URL).

## Network egress and telemetry

Deny outbound traffic by default (Azure Firewall, network security groups) and allow only the Entra
ID endpoints and the private endpoints of the services above. The calls below then fail, and the
features that need them do not work.

### Telemetry

- **Engine.** OpenTelemetry tracing is off by default (`telemetry.enabled: false`). When on, and with
  the `naas-abi-core[otel]` extra installed, spans go over OTLP/HTTP to `telemetry.otlp_endpoint`, or to
  the standard `OTEL_EXPORTER_OTLP_*` variables when it is unset
  ([`EngineTelemetryLoader.py`](libs/naas-abi-core/naas_abi_core/engine/engine_loaders/EngineTelemetryLoader.py)).
  Point it at a collector inside the network, or leave it off.
- **Remote modules (SDK).** Spans export only when `OTEL_EXPORTER_OTLP_ENDPOINT` or
  `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` is set and `naas-abi-sdk[otel]` is installed
  ([`telemetry.py`](libs/naas-abi-sdk/naas_abi_sdk/telemetry.py)). Credentials are scrubbed from the
  exception messages and stack traces recorded on spans.
- **No vendor telemetry.** No code in this repository reports usage to the vendor.
- **Third-party images.** The Nexus images set `NEXT_TELEMETRY_DISABLED=1`, and the compose files set
  `CODER_TELEMETRY_ENABLE: "false"`. They set no telemetry option for the other images: check each
  image's documentation (Qdrant, for example, has its own usage statistics setting).

### Vendor endpoints

Nothing calls the vendor unless it is configured or run by hand. The code that can:

| What | Calls | Keep it off |
|---|---|---|
| Secret adapter `naas` | `api.naas.ai` | not in `services.secret.secret_adapters` |
| Object storage adapter `naas` | `api.naas.ai` | not selected |
| Marketplace module `naas_abi_marketplace.applications.naas` | `api.naas.ai` | not in `modules` |
| `abi deploy naas`, `abi secrets naas …`, the `deploy:` configuration block | `api.naas.ai` | not run; block removed |
| `make datastore-*`, `storage-*`, `triplestore-prod-*` ([`scripts/common.py`](scripts/common.py)) | `api.naas.ai` | not run |
| Nexus web profiles `cloudflare` and `staging` | the vendor's hosted Nexus | `NEXT_PUBLIC_NEXUS_ENV=local`, as the compose files set |

In the browser, the logos of many agents and modules are images on a public bucket of the vendor, and
help links point to the vendor's website: a browser without Internet access shows no image. The
`http://ontology.naas.ai/…` addresses in the ontologies and configuration are identifiers, not
endpoints.

### Model providers outside the registry

Three paths call a model provider without going through the model registry. Keep them unconfigured:

- **Nexus chat providers**
  ([`provider_runtime.py`](libs/naas-abi/naas_abi/apps/nexus/apps/api/app/services/provider_runtime.py)).
  A chat request that names a provider other than ABI calls Anthropic, OpenAI, Cloudflare Workers AI,
  Ollama or an OpenAI-compatible endpoint directly, with a key from the request or from the Nexus
  settings (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `CLOUDFLARE_API_TOKEN`). Leave those variables unset.
- **Chat file embeddings**
  ([`chat_file_embeddings.py`](libs/naas-abi/naas_abi/apps/nexus/apps/api/app/services/chat/chat_file_embeddings.py)).
  The registry comes first; an embedding model it does not hold falls back to OpenAI with
  `OPENAI_API_KEY` from the secret service. Register the embedding model and leave that key unset.
- **OpenCode coding agent.** The keys under `opencode.providers` are written to OpenCode's auth file,
  and OpenCode calls those providers itself. Leave the list empty.

### Other outbound calls

- **Identity provider.** Discovery document, JWKS and token endpoint (Entra ID: `login.microsoftonline.com`).
- **Nexus web server routes.** Some server routes fetch external content; the Maps app reaches public
  data feeds and map tiles (weather, flights, disasters, news, OpenStreetMap; Google Places and
  AISStream when their keys are set). Deny the web container outbound access.
- **Ontology imports.** An import missing from the bundled `ontologies/imports` directory is fetched
  from this repository on GitHub, then from the import's own address.
- **Apps builder.** "Submit" pushes to GitHub only when `apps_submit_repo` and `APPS_SUBMIT_TOKEN` are set.
- **Marketplace modules.** Integrations call their own services, and they load only when listed with
  `enabled: true`. The `naas_abi` module's optional dependencies are soft: they do not load unless
  listed.
- **Builds.** The project `Dockerfile` installs the OpenCode CLI from `opencode.ai` and the Python
  dependencies from PyPI. Build in a connected zone, push to Azure Container Registry, and run with no
  outbound access.

## Backup, restore and upgrade

### What to back up

| Store | Holds | In this repository | On Azure |
|---|---|---|---|
| PostgreSQL | IAM, documents, Nexus, DuckLake catalog | `abi stack snapshot` (cold volume copy) | Flexible Server automated backups and point-in-time restore; `pg_dump` of each database for long retention (*to be tested*) |
| Fuseki (TDB2) | knowledge graph | [`scripts/fuseki_backup.sh`](scripts/fuseki_backup.sh): online N-Quads backup through the admin API into `$FUSEKI_BASE/backups/`, optional compaction; `fuseki-compact` service; `abi stack snapshot` | run the script on a schedule and copy the dump off the volume; disk snapshot with Fuseki stopped |
| Qdrant | vectors | `abi stack snapshot` | disk snapshot with Qdrant stopped, or Qdrant's snapshot API (*to be tested*) |
| NATS JetStream | bus streams, KV buckets, module registry, job schedules | `abi stack snapshot` | disk snapshot with `nats-server` stopped (*to be tested*) |
| Object storage | objects | `abi stack snapshot` | MinIO disk snapshot, or a mirror of the bucket to a second store (*to be tested*) |
| Redis | durable keys and caches | `abi stack snapshot` | Azure Managed Redis persistence or export (*to be tested*) |
| Secret store | bootstrap secrets; IAM signing keys, service key, `NEXUS_SECRETS_KEY` | not copied: a snapshot records a hash of `.env` and `config.local.yaml`, not their content | Key Vault backup, plus a copy of the writable secret file |
| `storage/` on the ABI host | event log, local DuckLake data, filesystem mail | `abi stack snapshot` | backup of the persistent volume, or none once these are on shared backends |

### Docker host: `abi stack snapshot`

For the Docker stack (`abi stack start`, `config.local.yaml`), `abi stack snapshot create` stops the
stack, archives the stateful volumes and the `storage/` directory, then starts it again
([`snapshot_runtime.py`](libs/naas-abi-cli/naas_abi_cli/cli/snapshot_runtime.py)). `list`, `restore`,
`delete`, `prune`, `export` and `import` manage snapshots; `restore` takes a safety snapshot first. It
skips Caddy certificates, Dagster history and caches, which rebuild themselves. Back up `.env`
separately.

### Restore on Azure (*to be tested*)

Backups taken store by store while the system runs are not consistent with each other. Stop the
stack for a coordinated copy, as `abi stack snapshot` does, or restore every store to the same point
in time and check the result.

1. Stop `nexus-web`, the ABI API, `idp` and remote modules.
2. Restore PostgreSQL, Fuseki, Qdrant, NATS, object storage and Redis to the same point in time.
3. Restore the secret store of that point, including `NEXUS_SECRETS_KEY`.
4. Start NATS, Fuseki, Qdrant and object storage, then the ABI API, then `nexus-web`.
5. Check: the API answers, a user signs in, a workspace opens, a chat file search and a graph query
   return data.

### Upgrade

- Versions come from the commit history (python-semantic-release). Each package has a `CHANGELOG.md`
  under `libs/`; images are tagged with the release.
- Schema changes apply at start and only forward: the Nexus API runs its SQL migrations
  ([`migrations/`](libs/naas-abi/naas_abi/apps/nexus/apps/api/migrations)) at every start, and the IAM
  store upgrades its schema when it first opens. There are no down migrations: going back means
  restoring a backup and the previous images.

Procedure (*to be tested*):

1. Read the changelogs between the two versions.
2. Import the new images into Azure Container Registry and pin their digests.
3. Take a coordinated backup, secret store included.
4. Stop the ABI API, then start the new version. With every owned service on a shared backend, start
   the new revision with a new `ABI_ROLLOUT_ID` instead: it stands by and takes over when the old one
   stops.
5. Watch the logs until migrations finish and the API answers, then upgrade `nexus-web` and run the
   checks of the restore procedure.
6. Keep the backup until the new version is accepted.
