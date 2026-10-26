# naas-abi-cli — AGENTS.md

> Scope: `libs/naas-abi-cli/`. Canonical reference for agents working on the `abi` command.

## Purpose

The `abi` command: scaffolds projects and modules (`abi new ...`), runs a project
natively (`abi dev ...`) or in Docker (`abi stack ...`, `abi deploy local`),
deploys it (`abi deploy dokploy|naas`) and administers a running Nexus (`abi user`,
`abi org`, `abi workspace`). Every command and option: `README.md` and
`https://docs.naas.ai/user-guide/reference/cli`.

## Files

| Path | Role |
|---|---|
| `naas_abi_cli/cli/__init__.py` | Click group; `main()` re-runs in the project's venv first |
| `naas_abi_cli/cli/bootstrap.py` | Inside a project, `abi ...` re-runs as `uv run --project <root> abi ...`: the project's own CLI version runs |
| `naas_abi_cli/cli/new/` | `abi new project/module/agent/app/...`; templates in `new/templates/` |
| `naas_abi_cli/cli/dev.py`, `dev_modules.py`, `dev_supervisor.py` | `abi dev up/down/status/logs/ports`: native processes, per-project port offsets, state in `<project>/.abi/dev/` |
| `naas_abi_cli/cli/stack*.py` | `abi stack ...`: the Docker Compose stack |
| `naas_abi_cli/cli/deploy/` | `abi deploy local/dokploy/naas`; templates in `deploy/templates/` |
| `naas_abi_cli/cli/iam.py` | `abi iam ...`: service accounts, keys, module manifests, invitations, IdP group bindings; also `provision_dev_modules` for `abi dev up` |
| `naas_abi_cli/cli/user.py`, `org.py`, `workspace.py`, `nexus_client.py` | `abi user/org/workspace ...`: HTTP admin client of a running Nexus; `abi user migrate` |
| `naas_abi_cli/cli/dev_mail.py` | `abi dev code`: reads the newest sign-in code from `storage/email` |
| `naas_abi_cli/cli/dev_modules.py` | SDK modules and the built-in IdP under `abi dev up`: their environment and keys |
| `naas_abi_cli/cli/admin_credentials.py` | Per-project secrets generated into `.env` (API key, IdP client secret, broker passwords, auth-callout seed) |
| `naas_abi_cli/cli/local_operator.py`, `engine_role.py` | Who a command that loads an engine runs as (`engine`), and whether it serves or is a client |
| `naas_abi_cli/cli/utils/Copier.py` | Renders a template tree (Jinja in file names and contents) |

## Identity, access and users

The commands below are the operator's side of the permission system: the engine's
side is [`services/iam/AGENTS.md`](../naas-abi-core/naas_abi_core/services/iam/AGENTS.md)
(policies, service accounts, keys, manifests, pending grants, IdP bindings) and
[`services/identity/AGENTS.md`](../naas-abi-core/naas_abi_core/services/identity/AGENTS.md)
(providers, provisioning); the built-in provider is
[`libs/naas-abi-idp/AGENTS.md`](../naas-abi-idp/AGENTS.md).

### Two kinds of command

- **`abi iam ...` acts as the engine, outside Nexus.** It never calls Nexus and needs no
  token: the operator who holds the project's config is trusted as the engine's own
  service account (`as_service_account("engine")`).
  - `service-account`, `key`, `module` open the IAM store named by `services.iam` in the
    config (`open_project_iam`). An in-memory store is refused (only the engine holding it
    could change it). After each write the command publishes `abi.iam.v1.changed` on the
    broker (`notify_engine`, best effort, 5 s deadline) so a running engine drops its IAM
    cache at once instead of within a minute. When the project's other config blocks name
    secrets the shell lacks, only `services.iam` and `services.secret` are rendered (a
    SQLite store needs none; a PostgreSQL DSN that names secrets is an error), and no
    change notice is sent.
  - `invite`, `invitation`, `group` need the engine's IAM and identity services
    (`open_engine_services`): they load an `Engine` with the engine role `auto`
    (`engine_role.py`: the serving engine's services over NATS when one runs, else this
    process's own).
- **`abi user/org/workspace ...` are a client of Nexus's HTTP API** (`nexus_client.py`),
  as whoever the token names. Nexus has no login of its own and no password: scripts hold a
  personal API key (`abi_pk_...`, made in Nexus under Account, API keys), or a session
  token the engine issued, as `--token` or `NEXUS_ACCESS_TOKEN`; the base URL is
  `--api-url` / `NEXUS_API_URL` (default `http://localhost:9879`). `--dry-run` prints the
  request. API keys cannot call `/api/auth/*`, so there is no `abi user me`.

### `abi iam` commands

| Command | Does |
|---|---|
| `service-account create NAME [--key]`, `list`, `delete ACCOUNT` | Accounts for modules (`module/<project>/<id>`), scripts and CI (`ci/<name>`). An account is named or given by its `sa_` id. Delete stops its keys at once |
| `key create ACCOUNT [--description] [--expires-in-days]`, `list`, `revoke ACCOUNT KEY_ID`, `rotate ACCOUNT KEY_ID` | Service keys `abi_sk_<key id>_<secret>`: stored hashed, printed once (on stdout, the hint on stderr). Revoking takes effect at the next exchange and broker connection; tokens already issued expire within ten minutes. `rotate` makes a new key and revokes the old |
| `module list [--status]`, `show ACCOUNT [--sha256]`, `approve ACCOUNT [--sha256] [--document FILE]`, `reject ACCOUNT [--reason]` | The module permission manifests a module submits when it registers. `approve` makes the manifest (or the narrowed `--document`, YAML or JSON) the managed policy `module.<project>.<id>`; the module reconnects with its new permissions. Name `--sha256` (first 12 characters in `list`) when you reviewed a particular version |
| `invite EMAIL [--org O --org-role R] [--workspace W --role R] [--provider P] [--name N] [--no-provision]` | Pending grants (`builtin.<role>` at the org or workspace scope) that attach at the person's first sign-in with that address verified, and an account made at the provider (`identity.provision_user`). With a provider that manages its own people (`provisioning: none`) only the grants are kept. A failure takes back the grants this call created |
| `invitation list [--email] [--provider]`, `invitation revoke GRANT_ID` | The pending grants; withdrawing one does not undo a membership already made |
| `group bind PROVIDER GROUP --role R (--org O \| --workspace W [--org O])`, `unbind`, `list [--provider]` | Give the members of an identity provider's group (a claim value) a role at an org or workspace |

- Roles are `owner`, `admin`, `member`, `viewer`; `--org` / `--workspace` take IAM's own
  names (the ids Nexus shows). `--workspace` alone works when IAM already placed the
  workspace in an org (`workspace_org`), else name `--org` too.
- `abi iam invite` never sends mail and keeps no invitation list: Nexus's
  `abi user invite` does (`POST .../members/invite`), and records the invitation for the
  people UI. Prefer it where Nexus runs; `abi iam invite` is the lower level.
- The provider is `--provider`, else the engine's default, else the only one configured.

### Module accounts, keys and approval

A remote module runs as service account `module/<project>/<module_id>` and reads its key
as `ABI_SERVICE_KEY`; the broker accepts it with the permissions of its approved manifest
only.

- **`abi dev up`** creates the account and a fresh key for each `dev.modules` entry
  (`provision_dev_modules`, as the engine; keys of earlier runs it made are revoked, so
  each start hands out new ones), puts it in the module's environment, and sets
  `services.iam.modules.auto_approve: true` in the generated dev overlay (dev only: the
  templates keep `false`). The module's environment never carries the CLI's `NATS_*`
  variables, `iam/` secrets or another module's key (`dev_modules.py`).
- **Elsewhere** (`abi deploy`, a module by hand): `abi iam service-account create
  module/<project>/<id> --key`, give the module the key, start it, then
  `abi iam module list --status pending` and `abi iam module approve`. Until approved the
  module registers but every other call is `PERMISSION_DENIED`. A changed manifest is a new
  pending version; the previous approved one stays in force. `abi new module` prints these
  steps for a remote module.
- The built-in identity provider is such a module (`module/<project>/idp`): `abi dev up`
  runs it by default (when the config names no `identity.providers`, or names one with
  `provisioning: builtin`), `abi new project` and `abi deploy local` set it up, and a
  deployment outside them creates its account and key by hand as above.

### Signing in during development

Nexus signs people in at an identity provider, so a fresh project has no password.
`abi dev up` prints how to sign in as `admin@example.com` (`ADMIN_EMAIL`, the account
`users:` of the Nexus configuration seeds: the API makes it exist at the built-in
provider when it starts, and its first sign-in links it). In dev the email adapter writes
messages to `storage/email`, so the 6-digit code is one command away:

```bash
abi dev code                          # the newest code mailed to admin@example.com
abi dev code --email bob@example.com  # an address; --email "" for anyone's
```

`dev_mail.py` reads the newest `.eml` whose body says "sign-in code is: NNNNNN"; with no
match it fails and says to ask the login page for a code first. Per-project secrets
(`ABI_API_KEY`, the client secret Nexus uses at the provider, the broker's passwords and
auth-callout seed) are generated into `.env` once and never defaulted
(`admin_credentials.py`); `abi deploy local --regenerate` drops the keys of the old
password login.

### Upgrading a project from the old login (`abi user migrate`)

Nexus's old built-in login (password, magic link) is gone. An older project runs:

```bash
abi user migrate            # dry run: what would be made at the provider
abi user migrate --apply    # make each person exist at the built-in provider
```

- Reads Nexus's own database (`--database-url`, else `DATABASE_URL`, else
  `nexus_config.database_url` of the config) for accounts no provider signs in yet, and
  makes each exist at the built-in provider (`--provider`, default the engine's default)
  with the same email and a new `sub`. Re-running creates nobody twice; one failure does
  not stop the others (exit is an error if any failed). Addresses a provider cannot mail a
  code to (placeholder domains) are skipped.
- Only a provider with `provisioning: builtin` is accepted: it alone proves an address by
  mailing a code, so it alone may take over an existing account. People of other providers
  are managed in the provider.
- Nothing is linked by the command. At the person's first sign-in with the mailed code,
  Nexus links the provider's `(issuer, sub)` to the existing account (`iam.link_user`), so
  roles, groups, keys and data stay. No password moves. Sessions and tokens signed before
  the upgrade end: people sign in again.
- Related upgrade facts: `secret_key` signs and encrypts nothing any more (workspace
  secrets use `secrets_encryption_key`, `NEXUS_SECRETS_KEY`); a deployment with several
  replicas whose secret store is per replica must set `NEXUS_SECRETS_KEY` before upgrading.
  An organization whose domain routes to an external provider cannot link its old
  accounts this way (see `services/identity/AGENTS.md`).

Authorization of the old data (roles, graph assignments, workspace prefixes) is migrated by
Nexus at its start, not by a CLI command. A fresh install enforces policies from the
start; `authorizer: allow_all` in `services.iam` is the explicit opt-out and warns at boot.

### `abi module list`

Lists the modules of the project's configuration (`modules:`) and whether each is enabled.
It reads the config only: remote modules, which run on their own account, show in
`abi dev status` and in Nexus.

## Tests

Unit tests sit beside the code (`<name>_test.py`). They render templates and stub
`subprocess`; none runs the CLI for real.

```bash
uv run pytest libs/naas-abi-cli                                  # from the repo root
uv run pytest libs/naas-abi-cli/naas_abi_cli/cli/new/project_test.py -v
```

### End-to-end smoke test

`scripts/cli_smoke.sh` runs the CLI for real, as a user would. CI runs it on every
PR into `main` (`.github/workflows/cli_e2e.yml`, one job per variant). In a temp dir
it installs the CLI from the checkout, runs `abi new project --abi-source <checkout>`,
adds a remote module, an in-engine one, an agent and apps, runs their scaffolded
tests, starts the project with `abi dev up -d` and waits for the API's `/docs`, the
remote module READY in discovery, the agents and apps in Nexus, and Nexus web, then
`abi dev down`. The `without-nats` variant does the same for a legacy project with
one in-engine module.

```bash
scripts/cli_smoke.sh                  # both variants, 5-10 minutes each
scripts/cli_smoke.sh nats             # the default project only
scripts/cli_smoke.sh without-nats     # the legacy project only
ABI_SMOKE_DIR=~/abi-smoke ABI_SMOKE_KEEP=1 scripts/cli_smoke.sh nats   # keep it
```

- Needs `uv`, `git`, `curl`, `python3`, `pnpm` (Node.js 18.17+) and, for `nats`,
  `nats-server` 2.14+ on `PATH`. No Docker; no model is downloaded and nothing chats
  (the AI key is a placeholder).
- The project's `.abi` is a clone of the checkout's **HEAD**: commit what you want
  tested under `libs/`. The CLI that creates the project is installed from the
  working tree; inside the project, the `.abi` copy runs (`bootstrap.py`).
- On failure it prints `abi dev status` and `abi dev logs` for every service and
  keeps the work dir; the logs are in `$ABI_SMOKE_DIR/logs/<variant>/` (CI uploads
  them as the `cli-smoke-logs-<variant>` artifact).
- The checks live in `scripts/cli_smoke_checks.py` (standard library only). A new
  user-facing step of the quickstart belongs in the script, and a bug it finds gets
  a unit test beside the code it fixes.

## Conventions

- A template change gets a render test (`config_template_test.py`,
  `pyproject_template_test.py`, ...). Rendered TOML/YAML is parsed in the test.
- Messages tell the user the next command to run; failures raise
  `click.ClickException` with what to do, never a traceback.
- Generated projects need Python 3.12+. A NATS project resolves the framework from
  its `.abi` submodule (`use_local_abi_sources`) until proto and the SDK are on PyPI.
