# CLI Reference

The `abi` CLI (`naas-abi-cli`) creates projects and modules, runs them natively or with Docker, deploys them and administers a running Nexus. This page documents **every command and option**; `abi <command> --help` prints the same from the installed version. A test walks the CLI's command tree and fails when a command or an option is missing here.

Inside a project, `abi` re-runs itself with the project's own CLI version (it says so on stderr), so a project is always driven by the version it was created with.

| Command | What it does |
|---|---|
| [`abi new`](#abi-new) | Scaffold a project, a module, an agent, a workflow, a pipeline, an integration, an app |
| [`abi init`](#abi-init) | Create an empty folder |
| [`abi dev`](#abi-dev) | Run the project natively, without Docker |
| [`abi stack`](#abi-stack), [`abi start`](#abi-start), [`abi stop`](#abi-stop), [`abi logs`](#abi-logs) | Run the Docker stack |
| [`abi deploy`](#abi-deploy) | Render the Docker stack, a Dokploy stack, or deploy to Naas Spaces |
| [`abi module`](#abi-module) | The configured modules |
| [`abi iam`](#abi-iam) | Service accounts, keys, module permissions, group bindings, invitations |
| [`abi agent`](#abi-agent) | List agents, move and prune agent memory |
| [`abi chat`](#abi-chat), [`abi run`](#abi-run) | Chat with an agent, run a script with the engine loaded |
| [`abi config`](#abi-config), [`abi docs`](#abi-docs) | Validate and render the config, check the reference pages |
| [`abi org`](#abi-org), [`abi user`](#abi-user), [`abi workspace`](#abi-workspace) | Administer a running Nexus |
| [`abi secrets`](#abi-secrets) | Naas secrets |
| [`abi setup`](#abi-setup) | Add a Headscale service to a project's Docker stack |

---

## Installation

```bash
uv tool install naas-abi-cli --force --upgrade --with-executables-from naas-abi-core
abi --help
```

See [Install and prerequisites](/user-guide/get-started/install).

---

## `abi new`

Scaffold a project, or a part of one.

```bash
abi new project my_ai                     # a NATS project (the default since 3.0)
abi new module research                   # a remote module (SDK) in a NATS project
abi new module legacy --in-engine         # a module the engine loads (alias --local)
```

### `abi new project`

```bash
abi new project my_ai [PATH] [options]
```

| Option | Effect |
|---|---|
| `--with-nats` / `--without-nats` | NATS (the default), or the classic in-process project: RabbitMQ in the Compose stack, Dagster, the `naas-abi-core[dagster,rabbitmq]` extras. `--without-nats` is [legacy](/user-guide/get-started/legacy-mode). |
| `--with-local-deploy` / `--without-local-deploy` | Generate the Docker Compose stack and `.deploy/` (the default), or skip it. |
| `--with-headscale` / `--without-headscale` | A Headscale service in the local stack (off by default). |
| `--with-coding` / `--without-coding` | Coding workspaces in the local stack: Coder, Forgejo, Actions CI (off by default). |
| `--with-abi-submodule` / `--without-abi-submodule` | Add `jupyter-naas/abi` as the git submodule `.abi/` (the default). A NATS project needs it until `naas-abi-proto` and `naas-abi-sdk` are on PyPI: `--without-abi-submodule` is refused with NATS. |
| `--abi-source URL_OR_PATH` | Where `.abi` is cloned from (its HEAD): a git URL or a local checkout. Default `https://github.com/jupyter-naas/abi.git`. A checkout lets you test framework changes that are not on GitHub yet. |
| `--domain example.com` | Base domain: `BASE_DOMAIN`, with `PUBLIC_WEB_HOST` and `PUBLIC_API_HOST` derived as `nexus.<domain>` and `api.<domain>`. Default `localhost`. |

It writes the configs (with a `nats:` block), the Docker Compose stack, and `.env` with the broker's passwords (`NATS_ENGINE_PASSWORD`, `NATS_AUTH_PASSWORD`), the seed of its auth callout (`NATS_AUTH_CALLOUT_SEED`) and the identity provider's client secret. There is no admin password: `admin@example.com` signs in with the code the built-in identity provider emails. Without a terminal it cannot prompt for `OPENROUTER_API_KEY`: export it first (any value works when nobody chats).

### `abi new module`

```bash
abi new module research                   # remote: SDK, own process (default in a NATS project)
abi new module legacy --in-engine         # classic: naas_abi_core, loaded by the engine
abi new module research --remote          # remote, in a project without NATS
abi new module research --standalone      # remote, in a repository of its own
```

| Option | Effect |
|---|---|
| `--in-engine`, `--local` | A classic module the engine loads (agents, integrations, pipelines, workflows, ontologies). Add it under `modules:` in `config.yaml`. |
| `--remote` | A remote module in a project without NATS too (it runs once the project is on NATS). |
| `--standalone` | A remote module as a repository of its own (`pyproject.toml`, `Dockerfile`, README): the default outside a project. |
| `--abi-ref REF` | With `--standalone`: the ABI branch, tag or commit `naas-abi-sdk` and `naas-abi-proto` install from. Default: this CLI's release tag, `naas-abi-cli-v<version>`. |

In a project, a remote module goes to `src/<name>/` with a `dev.modules` entry, a service in `docker-compose.override.yml` (its service key goes in `.env` as `<NAME>_SERVICE_KEY`, and its permission manifest waits for `abi iam module approve`); it registers itself through discovery, so it is not listed under `modules:`. In a project without a `nats:` block the default is an in-engine module, and the command says so. See [Build a Remote Module](/user-guide/build/sdk/build-a-remote-module) and [Creating a Module](/user-guide/build/modules/creating-a-module).

### Inside a module

`agent`, `workflow`, `pipeline`, `integration`, `app` and `orchestration` run **inside a module** (`cd src/<module>`), with a name and an optional path inside the module. None takes an option besides `--help`.

```bash
cd src/legacy
abi new agent analyst agents
abi new app reports apps
```

- In a remote module, `abi new agent <Name> agents` writes an SDK agent and `abi new app <name> apps` an app; `workflow`, `pipeline`, `integration` and `orchestration` refuse, because they write `naas_abi_core` code.
- In an in-engine module: `agent`, `workflow`, `pipeline`, `integration` and `app`.

### `abi new agent`

`abi new agent <AgentName> [PATH]`: an SDK `IntentAgent` in a remote module, a `naas_abi_core` `Agent` in an in-engine one. See [Creating an agent](/user-guide/build/agents/creating-an-agent).

### `abi new workflow`

`abi new workflow <name> [PATH]`: a workflow of an in-engine module. See [Creating a workflow](/user-guide/build/agents/creating-a-workflow).

### `abi new pipeline`

`abi new pipeline <name> [PATH]`: a knowledge-graph pipeline of an in-engine module. See [Creating a pipeline](/user-guide/build/knowledge-graph/creating-a-pipeline).

### `abi new integration`

`abi new integration <name> [PATH]`: an integration of an in-engine module. See [Creating an integration](/user-guide/build/agents/creating-an-integration).

### `abi new app`

`abi new app <name> [PATH]`: an app, served by Nexus.

### `abi new orchestration`

`abi new orchestration <name> [PATH]` writes a Dagster orchestration, for a project without NATS only ([legacy](/user-guide/build/applications/dagster)). In a NATS project schedule with [module jobs](/user-guide/build/modules/module-jobs).

---

## `abi init`

```bash
abi init my_folder        # create it (`.` is the current directory)
```

Creates the folder. It writes nothing else; use `abi new project` for a project.

---

## `abi dev`

Run the project natively, without Docker.

```bash
abi dev up                       # foreground; Ctrl+C stops everything
abi dev up -d                    # in the background
abi dev status                   # services, dev modules, pids and health
abi dev ports                    # the ports of this checkout
abi dev logs research -f         # a service's or dev module's log
abi dev code                     # the newest sign-in code mailed to admin@example.com
abi dev down                     # stop (dev modules first)
abi dev nuke                     # wipe local state; keeps .env
```

### `abi dev up`

| Option | Effect |
|---|---|
| `--service NAME` | Start only this service or dev module (repeatable). Default in NATS mode: `oxigraph`, `nats`, `api`, `nexus-web`, then every `dev.modules` entry. |
| `-d`, `--detach` | Run in the background and return. |
| `--log-level LEVEL` | `LOG_LEVEL` of the api (and legacy Dagster): `CRITICAL`, `ERROR`, `WARNING`, `INFO` or `DEBUG`. Default `$LOG_LEVEL`, else `DEBUG`. |
| `--with-nats` / `--without-nats` | Force NATS mode, or the in-process engine (legacy). Default: NATS mode when the config has a `nats:` block. |
| `--with-tracing` | Run a native Jaeger (`jaeger` v2 on `PATH`) and export OpenTelemetry spans to it. |

- **NATS mode**: `nats-server` (2.14 or later, on `PATH`), Oxigraph, the API with discovery and jobs, Nexus web, then every `dev.modules` entry. It writes the broker's config with the users `engine` and `auth` and its auth callout, the broker's passwords and the callout's seed in `.env` when missing, and `.abi/dev/dev.overlay.yaml`, which points the engine at its broker; `config.yaml` stays untouched. Unless the config names an identity provider, it also runs the built-in one (`naas-abi-idp`) as a dev module, which mails the sign-in codes. Dagster is left out. `abi dev up -d` waits for the API before it starts the modules.
- **In-process mode** ([legacy](/user-guide/get-started/legacy-mode)): Oxigraph, the API, Dagster (only when the project installs the `naas-abi-core[dagster]` extra) and Nexus web. `abi dev up -d` returns at once: poll the API's `/docs`.
- **Dev modules** (`dev.modules` in the config) each run as `python -m <module>` under a supervisor that restarts them, as their own service account `module/<project>/<module_id>`: `abi dev up` creates it, gives it a fresh key and approves its permission manifest. They get `ABI_NATS_URL`, `ABI_SERVICE_KEY`, `ABI_DISCOVERY_PROJECT` and, with tracing, `OTEL_EXPORTER_OTLP_ENDPOINT`.
- Each git worktree gets its own ports.

### `abi dev code`

Prints the newest sign-in code the built-in identity provider mailed: under `abi dev up` the mail is a file in `storage/email`. There is no admin password: `admin@example.com` signs in with a code.

| Option | Effect |
|---|---|
| `--email ADDRESS` | The address the code was mailed to (default `admin@example.com`); empty for anyone's. |

### `abi dev down`

`--service NAME` stops only that service or dev module (repeatable). No option: stop all.

### `abi dev status`

Prints the services, dev modules, pids and health. No options.

### `abi dev ports`

Prints the ports allocated to this checkout. No options.

### `abi dev logs`

```bash
abi dev logs <service> [-f] [-n 100]
```

`-f`, `--follow` tails; `-n`, `--lines N` prints the last N lines (default 100).

### `abi dev nuke`

Wipes the SQLite databases, the Oxigraph store, Dagster's run history and stale logs. It refuses while a managed service is alive. It keeps `.abi/dev/instance.json` (stable ports), `.env` and `node_modules`.

| Option | Effect |
|---|---|
| `-y`, `--yes` | Skip the confirmation. |
| `--start` | `abi dev up` again after the wipe. |
| `--reset-env` | Also remove the admin credential lines older versions wrote to `.env` (there is no password any more: the admin signs in with a mailed code). |

---

## `abi stack`

Manage the Docker stack. See [Deploy with Docker](/user-guide/deploy/local-docker).

```bash
abi stack start                  # start, and wait until services are ready
abi stack status                 # readiness per service (TCP/HTTP probes)
abi stack logs api               # logs of one service
abi stack stop
abi stack tui                    # interactive terminal UI
```

### `abi stack start`

It starts the stack, waits until it is ready, then opens Nexus in the browser. On a Linux host without a display (a server reached over SSH) it prints the URL instead.

`--legacy`: legacy, for the ABI repository's own stack. Also starts the `legacy` Compose profile (Dagster, RabbitMQ) and runs the engine without NATS, with its bus on RabbitMQ, through the generated overlay `.abi/stack/legacy.overlay.yaml`. A generated project refuses it. Default: the stack on NATS.

### `abi stack status`

Readiness of every service. No options.

### `abi stack logs`

`abi stack logs [SERVICE]` follows the logs of one service, or of all.

### `abi stack stop`

`-v`, `--volumes` removes the volumes along with the containers. It also stops the `legacy` profile.

### `abi stack tui`

`--interval SECONDS`: refresh interval (default 1.5).

### `abi stack snapshot`

Create, restore and move snapshots of the stack's data. A snapshot archives the stateful data volumes (including `nats_data`) and `storage/`.

```bash
abi stack snapshot create -m "before upgrade"
abi stack snapshot list
abi stack snapshot restore <id>  # destructive
```

#### `abi stack snapshot create`

Stops the stack, archives its data, then restarts it. `-m`, `--note TEXT` describes the snapshot; `--name TEXT` adds a label to its id.

#### `abi stack snapshot list`

Lists snapshots, newest first. No options.

#### `abi stack snapshot restore`

`abi stack snapshot restore <id>` rolls the stack back (destructive). `--yes` skips the confirmation; `--safety-snapshot` / `--no-safety-snapshot` takes a snapshot of the current state first (the default).

#### `abi stack snapshot delete`

`abi stack snapshot delete <id>`; `--yes` skips the confirmation.

#### `abi stack snapshot prune`

Deletes all but the newest snapshots. `--keep N` (default 5); `--yes` skips the confirmation.

#### `abi stack snapshot export`

`abi stack snapshot export <id> <destination>` writes one portable archive for another host. `--force` overwrites the destination.

#### `abi stack snapshot import`

`abi stack snapshot import <archive>` imports an archive made by `export`. `--force` replaces a snapshot with the same id.

---

## `abi start`

Shortcut for [`abi stack start`](#abi-stack-start), with the same `--legacy` option.

## `abi stop`

Shortcut for [`abi stack stop`](#abi-stack-stop): `-v`, `--volumes` removes the volumes.

## `abi logs`

Shortcut for [`abi stack logs`](#abi-stack-logs): `abi logs [SERVICE]` follows the stack's logs.

---

## `abi deploy`

```bash
abi deploy local                 # write the Docker Compose stack
abi deploy local-up -d           # docker compose up, with docker-compose.override.yml
abi deploy dokploy --domain example.com
abi deploy naas                  # deploy to a Naas Space
```

### `abi deploy local`

Writes the project's Docker Compose stack, `.deploy/` and the stack's variables in `.env`. See [Deploy with Docker](/user-guide/deploy/local-docker).

| Option | Effect |
|---|---|
| `-e`, `--env NAME` | The config environment (default `local`: `config.local.yaml`, else `config.yaml`). |
| `--regenerate` | Re-render from the current templates, after a backup in `.abi-backups/` (it holds a copy of `.env` and ignores itself in git). Never touches `docker-compose.override.yml`. |
| `--no-backup` | With `--regenerate`: no backup. |
| `--headscale` | Include a Headscale service. |
| `--coding` | Include coding workspaces: Coder, Forgejo, Actions CI. |

A project with a `nats:` block gets the NATS stack: a `nats` service the engine waits for, no Dagster, RabbitMQ behind the profile `rabbitmq`. A project without one keeps the classic stack ([legacy](/user-guide/get-started/legacy-mode)) and gets the `naas-abi-core[dagster,rabbitmq]` extras added to its `pyproject.toml`. It writes `.deploy/docker/nats/nats.conf` (the broker users `engine` and `auth`, and the auth callout that admits every module with its approved permissions) and the broker's passwords, the callout's seed and the identity provider's client secret in `.env`: regenerate after each CLI upgrade.

### `abi deploy local-up`

`docker compose up` with `docker-compose.override.yml`, where remote modules live. `-d`, `--detach` runs in the background.

### `abi deploy local-logs`

Follows the Compose logs. No options.

### `abi deploy local-down`

`docker compose down`. `-v`, `--volumes` also removes the volumes.

### `abi deploy dokploy`

Renders `docker-compose.dokploy.yml`, `config.dokploy.yaml` and `.env.dokploy` for a Dokploy server. See [Deploy with Dokploy](/user-guide/deploy/dokploy).

| Option | Effect |
|---|---|
| `--domain example.com` | Base domain: Nexus at `nexus.<domain>`, the API at `api.<domain>`. Prompted on the first run; later runs keep the hosts. |
| `--coding` | Include coding workspaces (Coder, Forgejo, Actions CI). |
| `--regenerate` | Generate new secrets in `.env.dokploy` (the old file is backed up). |
| `--wildcard-cert-resolver NAME` | With `--coding`: the DNS-challenge resolver in Dokploy's Traefik that issues the `*.coder` wildcard certificate. Kept on later runs. |
| `--headscale` | Refused: not supported on Dokploy yet. |

### `abi deploy naas`

Builds the project's image, pushes it to a Naas registry and creates or updates a Naas Space. It needs a `deploy:` section in the config. See [Production and remote deployments](/user-guide/deploy/production#naas-spaces).

`-e`, `--env NAME`: the config environment (default `prod`: `config.prod.yaml`, else `config.yaml`).

---

## `abi module`

```bash
abi module list                  # the modules in the config, and whether they are enabled
```

A remote module has no key to derive: it runs as a service account with its own key and an approved permission manifest. See [`abi iam`](#abi-iam).

### `abi module list`

Lists the modules in the config, and whether they are enabled. No options.

---

## `abi iam`

Service accounts, keys, module permission manifests, group bindings and invitations, on the project's IAM store (`services.iam.store`, SQLite or PostgreSQL). Each command tells a running engine to reload (`abi.iam.v1.changed`). A key (`abi_sk_...`) is printed once, at creation; only its hash is stored.

```bash
abi iam service-account create module/default/research --key
abi iam key create module/default/research --description prod
abi iam module list --status pending
abi iam module approve module/default/research
abi iam invite ada@example.com --org org-... --org-role member
abi iam group bind okta engineering --org org-... --role member
```

### `abi iam service-account`

#### `abi iam service-account create`

`abi iam service-account create NAME` creates the account: `module/<project>/<module_id>` for a remote module, `ci/<name>` for a script.

| Option | Effect |
|---|---|
| `--key` | Create a first key for it too. |

#### `abi iam service-account list`

Lists the service accounts. No options.

#### `abi iam service-account delete`

`abi iam service-account delete ACCOUNT` deletes the account (a name or an `sa_` id): its keys stop at once. No options.

### `abi iam key`

An account holds at most five active keys; `ci/*` keys expire after 90 days. A revoked key fails its next exchange and its next broker connection; tokens already issued expire within ten minutes.

#### `abi iam key create`

`abi iam key create ACCOUNT` creates a key and prints it, once.

| Option | Effect |
|---|---|
| `--description TEXT` | What the key is for. |
| `--expires-in-days N` | Default: never (`ci/*`: 90). |

#### `abi iam key list`

`abi iam key list ACCOUNT` lists the account's keys, never their values. No options.

#### `abi iam key rotate`

`abi iam key rotate ACCOUNT KEY_ID` replaces the key with a new one (printed once) and revokes it. No options.

#### `abi iam key revoke`

`abi iam key revoke ACCOUNT KEY_ID` revokes the key. No options.

### `abi iam module`

A remote module submits its permission manifest when it starts and waits for approval; until then the broker lets it reach IAM only.

#### `abi iam module list`

Lists the submitted manifests, oldest first.

| Option | Effect |
|---|---|
| `--status pending\|approved\|rejected\|superseded` | Only manifests in this state. |

#### `abi iam module show`

`abi iam module show ACCOUNT` prints a manifest as submitted, to review or narrow it.

| Option | Effect |
|---|---|
| `--sha256 TEXT` | A version; default: the latest submitted. |

#### `abi iam module approve`

`abi iam module approve ACCOUNT` approves the manifest: it becomes the module's policy.

| Option | Effect |
|---|---|
| `--sha256 TEXT` | The version to approve (`list` prints its first 12 characters); default: the latest pending one. |
| `--document FILE` | Approve this policy document instead (narrowed), YAML or JSON. |

#### `abi iam module reject`

`abi iam module reject ACCOUNT` rejects the pending manifest.

| Option | Effect |
|---|---|
| `--sha256 TEXT` | A version; default: the latest pending one. |
| `--reason TEXT` | Shown to the module. |

### `abi iam group`

Bind an identity provider's groups to roles.

#### `abi iam group list`

Lists the bindings: provider, group, role, scope.

| Option | Effect |
|---|---|
| `--provider TEXT` | Only this provider's bindings. |

#### `abi iam group bind`

`abi iam group bind PROVIDER GROUP` gives the members of the provider's group a role in an organization or a workspace.

| Option | Effect |
|---|---|
| `--org ORG_ID` | The organization id. Without `--workspace` the role is the organization's own. |
| `--workspace WORKSPACE_ID` | The workspace id (with `--org` unless IAM knows it). |
| `--role owner\|admin\|member\|viewer` | Required. |

#### `abi iam group unbind`

`abi iam group unbind PROVIDER GROUP` takes that role from the group's members.

| Option | Effect |
|---|---|
| `--org ORG_ID` | The organization id. |
| `--workspace WORKSPACE_ID` | The workspace id (with `--org` unless IAM knows it). |
| `--role owner\|admin\|member\|viewer` | Required. |

### `abi iam invite`

`abi iam invite EMAIL` keeps roles waiting for the person and makes them exist at their provider. The roles attach when they first sign in with this address verified. Where the provider's people are managed in the provider (`provisioning: none`) only the pending grants are kept.

| Option | Effect |
|---|---|
| `--org ORG_ID` | The organization id. |
| `--org-role owner\|admin\|member\|viewer` | The role in the organization itself. |
| `--workspace WORKSPACE_ID` | The workspace id. |
| `--role owner\|admin\|member\|viewer` | The role in the workspace. |
| `--provider TEXT` | The identity provider (default: the engine's default). |
| `--name TEXT` | Their display name, where the provider needs one. |
| `--no-provision` | Only keep the pending grants: do not create the person at the provider. |

### `abi iam invitation`

#### `abi iam invitation list`

Lists the pending grants: id, role, scope, provider, email.

| Option | Effect |
|---|---|
| `--email TEXT` | Only this address's grants. |
| `--provider TEXT` | Only this provider's grants. |

#### `abi iam invitation revoke`

`abi iam invitation revoke GRANT_ID` withdraws a pending grant. No options.

---

## `abi agent`

```bash
abi agent list                                   # agents the engine loads
abi agent migrate-memory                         # dry run: PostgreSQL memory → Document Service
abi agent migrate-memory --apply
abi agent migrate-memory --from documents-v1     # from document schema 1
abi agent prune-memory --keep-last 20            # dry run
abi agent prune-memory --keep-last 20 --apply
```

### `abi agent list`

Lists the agents the engine loads. No options.

### `abi agent migrate-memory`

Copies agent memory into the Document Service (schema 2). A dry run unless `--apply`; idempotent.

| Option | Effect |
|---|---|
| `--from postgres\|documents-v1` | LangGraph's PostgreSQL tables (default), or document schema 1. |
| `--source-url URL` | With `--from postgres`: LangGraph's database (`POSTGRES_URL`). |
| `--namespace NAME` | Document namespace (default: the engine's agent memory). |
| `--agent-id ID` | Checkpoint scope (default: the engine's). |
| `--thread ID` | Only this thread (repeatable). |
| `--apply` | Write; otherwise only report. |

### `abi agent prune-memory`

Deletes old agent memory, keeping each thread's newest checkpoints. A dry run unless `--apply`.

| Option | Effect |
|---|---|
| `--keep-last N` | Checkpoints kept per thread (default 20). |
| `--namespace NAME`, `--agent-id ID`, `--thread ID` | As for `migrate-memory`. |
| `--min-age SECONDS` | Younger stored values are kept (default 60). |
| `--apply` | Delete; otherwise only report. |

Stop the engines before `migrate-memory` or `prune-memory`. In NATS mode, the engine runs the same work as jobs: `agent_memory_migrate` (on demand, from the System app) and `agent_memory_prune` (daily). See [Migrate from 2.x to 3.0](/user-guide/upgrade/migrate-to-3#right-after-the-restart-copy-agent-memory-and-activity-logs).

---

## `abi chat`

```bash
abi chat                         # the default agent
abi chat naas_abi AbiAgent       # an agent, by module and name
```

`abi chat [MODULE_NAME] [AGENT_NAME]`. It loads an engine with `ABI_ENGINE_ROLE=auto`: it serves when no engine runs, and is a NATS client of the running one otherwise.

In a NATS project it reaches the broker named in `config.yaml` (`127.0.0.1:4222`, the Docker stack's). `abi dev up` runs its own broker on another port and writes it to `.abi/dev/dev.overlay.yaml`: while a dev service runs, every command that loads the engine (`abi chat`, `abi agent list`, `abi run script`, ...) reads that overlay too, unless `ABI_CONFIG_OVERLAY` is already set. Run them from the project root. To load the engine in-process, with no broker at all, point `ABI_CONFIG_OVERLAY` at a file that holds `nats: null`.

## `abi run`

### `abi run script`

```bash
abi run script path/to/script.py [args...]
```

Loads the engine (role `auto`), then runs the script with the arguments after its path.

---

## `abi config`

```bash
abi config validate              # load and validate the project's config
abi config validate --modules    # also import every enabled module and validate its config
abi config render                # print it rendered
```

### `abi config validate`

`--configuration-file PATH` validates that file instead of the environment's config. `--modules` also checks that each enabled module imports and its config is valid.

### `abi config render`

Prints the rendered config. `--configuration-file PATH` renders that file.

## `abi docs`

### `abi docs sync`

Checks (or generates) the library reference pages against their source.

```bash
abi docs sync --fail-on-stale    # reference pages older than their source
```

| Option | Effect |
|---|---|
| `--source DIR` | Python source root (default `libs/naas-abi-core/naas_abi_core`). |
| `--output DIR` | Where the markdown pages are expected (default `docs/reference`). |
| `--include-tests` | Include test files in the staleness check. |
| `--fail-on-stale` | Exit non-zero when pages are stale. |
| `--generate` | Write the stale pages with the documentation agent. |
| `--model ID` | The model it uses (default `gpt-5.2`). |
| `--workers N` | Pages generated in parallel (default 10). |

---

## `abi org`, `abi user`, `abi workspace`

Administer a running Nexus through its HTTP API: organizations, users, workspaces and their members.

```bash
export NEXUS_API_URL=http://localhost:9879          # under `abi dev up`, the api port of `abi dev ports`
abi org create --name "Acme" --slug acme
abi workspace create --name "Research" --slug research --org org-...
abi user invite --email ada@example.com --org org-... --workspace ws-...
```

### Nexus API options

Every command of these three groups takes the same options to reach Nexus and sign in:

| Option | Effect |
|---|---|
| `--api-url URL` | The Nexus API base URL, no trailing slash (default `http://localhost:9879`, env `NEXUS_API_URL`). |
| `--token TOKEN` | A personal API key (`abi_pk_...`, made in Nexus under Account, API keys) or an engine session token (env `NEXUS_ACCESS_TOKEN`). |
| `--dry-run` | Print the API call that would be made, without making it. |

There is no password to sign in with: sign in to Nexus as `admin@example.com` (the code the built-in identity provider emails; `abi dev code` prints it), make a personal API key under Account, API keys, and export it as `NEXUS_ACCESS_TOKEN`. Roles are `owner`, `admin`, `member` for organizations and `admin`, `member`, `viewer` for workspaces.

### `abi org`

#### `abi org list`

Lists the organizations of the signed-in user.

#### `abi org get`

`--id ORG_ID` (required): fetch an organization.

#### `abi org create`

Creates an organization; the caller becomes its owner. `--name TEXT` and `--slug TEXT` are required.

#### `abi org workspaces`

`--org ORG_ID` (required): list the workspaces under an organization.

#### `abi org members`

##### `abi org members list`

`--org ORG_ID` (required): list the members.

##### `abi org members invite`

Invites a user into an organization (the account is created when missing, and a sign-in email is sent).

| Option | Effect |
|---|---|
| `--org ORG_ID` | Required. |
| `--email EMAIL` | Required. |
| `--name TEXT` | Display name, when creating the user. |
| `--role owner\|admin\|member` | The organization role (default `member`). |
| `--workspace WORKSPACE_ID` | Also add the user to this workspace. |
| `--workspace-role admin\|member\|viewer` | Its workspace role (default `member`). |

### `abi user`

#### `abi user list`

Lists the users of an organization (`--org ORG_ID`) or a workspace (`--workspace WORKSPACE_ID`). There is no global user index.

#### `abi user invite`

Invites a user: the identity provider makes the person exist and Nexus emails them a link to sign in (the provider mails the code). Prefer `--org`, with `--workspace` for both.

| Option | Effect |
|---|---|
| `--email EMAIL` | Required. |
| `--name TEXT` | Display name, when creating the user. |
| `--org ORG_ID` | The organization to invite into. |
| `--workspace WORKSPACE_ID` | The workspace to invite into. |
| `--role owner\|admin\|member\|viewer` | The organization role with `--org`; the workspace role when only `--workspace` is set (default `member`). |
| `--workspace-role admin\|member\|viewer` | The workspace role with `--org` and `--workspace` together (default `member`). |

#### `abi user migrate`

Moves the users of Nexus's old login (passwords, magic links) to the built-in identity provider: every account that no provider signs in yet is made at the provider with the same email. Each person then signs in with the code the provider mails to that address, and that first sign-in links the account, which keeps its roles, groups and data. Passwords do not move. Without `--apply` it is a dry run; run it again whenever accounts were added, it creates nobody twice.

| Option | Effect |
|---|---|
| `--provider TEXT` | The built-in identity provider to move the users to (default: the engine's default). |
| `--database-url TEXT` | Nexus's database (default: `nexus_config.database_url` of the project's configuration). |
| `--apply` | Make the people exist at the provider. |

### `abi workspace`

#### `abi workspace list`

Lists the workspaces of the signed-in user, or those under an organization with `--org ORG_ID`.

#### `abi workspace get`

`--id WORKSPACE_ID` or `--slug SLUG`: fetch a workspace.

#### `abi workspace create`

Creates a workspace under an organization.

| Option | Effect |
|---|---|
| `--name TEXT`, `--slug SLUG`, `--org ORG_ID` | Required. |
| `--via api\|postgres` | `api` (default), or `postgres`: break-glass SQL on the ops host. |
| `--owner-id USER_ID` | The owner, required with `--via postgres`. The API path always uses the caller. |

#### `abi workspace delete`

`--id WORKSPACE_ID` (required): delete a workspace (owner only). `--yes` skips the confirmation.

#### `abi workspace members`

##### `abi workspace members list`

`--workspace WORKSPACE_ID` (required): list the members.

##### `abi workspace members add`

Invites a user into a workspace, creating the account when missing.

| Option | Effect |
|---|---|
| `--workspace WORKSPACE_ID`, `--email EMAIL` | Required. |
| `--name TEXT` | Display name, when creating the user. |
| `--role admin\|member\|viewer` | Default `member`. |

##### `abi workspace members remove`

`--workspace WORKSPACE_ID` and `--user-id USER_ID` (required): remove a member. `--yes` skips the confirmation.

---

## `abi secrets`

### `abi secrets naas`

Manage the secrets a project keeps in Naas, as a base64-encoded `.env` (the `naas` and `base64` secret adapters read it). Each command takes `--naas-api-key` (default `$NAAS_API_KEY`) and `--naas-api-url` (default `https://api.naas.ai`).

#### `abi secrets naas list`

Prints the secrets stored in Naas. Options: `--naas-api-key`, `--naas-api-url`.

#### `abi secrets naas push-env-as-base64`

Pushes an env file as one base64 secret. Options: `--naas-api-key`, `--naas-api-url`, `--naas-secret-name NAME` (default `abi_secrets`) and `--env-file PATH` (default `.env.prod`).

#### `abi secrets naas get-base64-env`

Prints the env file stored in a secret, decoded. Options: `--naas-api-key`, `--naas-api-url` and `--naas-secret-name NAME` (default `abi_secrets`).

---

## `abi setup`

### `abi setup headscale`

Sets up the current project's Docker stack with a Headscale service and its configuration, as `abi deploy local --headscale` does. No options.

---

## Makefile targets (repository)

The ABI repository's `Makefile` has lower-level targets for working on ABI itself. See [The Makefile](/developer-guide/toolchain/makefile).
