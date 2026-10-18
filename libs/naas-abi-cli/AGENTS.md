# naas-abi-cli — AGENTS.md

> Scope: `libs/naas-abi-cli/`. Canonical reference for agents working on the `abi` command.

## Purpose

The `abi` command: scaffolds projects and modules (`abi new ...`), runs a project
natively (`abi dev ...`) or in Docker (`abi stack ...`, `abi deploy local`),
deploys it (`abi deploy dokploy|naas`) and administers a running Nexus (`abi user`,
`abi org`, `abi workspace`). Every command and option: `README.md` and
`docs/site/docs/user-guide/reference/cli.md`.

## Files

| Path | Role |
|---|---|
| `naas_abi_cli/cli/__init__.py` | Click group; `main()` re-runs in the project's venv first |
| `naas_abi_cli/cli/bootstrap.py` | Inside a project, `abi ...` re-runs as `uv run --project <root> abi ...`: the project's own CLI version runs |
| `naas_abi_cli/cli/new/` | `abi new project/module/agent/app/...`; templates in `new/templates/` |
| `naas_abi_cli/cli/dev.py`, `dev_modules.py`, `dev_supervisor.py` | `abi dev up/down/status/logs/ports`: native processes, per-project port offsets, state in `<project>/.abi/dev/` |
| `naas_abi_cli/cli/stack*.py` | `abi stack ...`: the Docker Compose stack |
| `naas_abi_cli/cli/deploy/` | `abi deploy local/dokploy/naas`; templates in `deploy/templates/` |
| `naas_abi_cli/cli/utils/Copier.py` | Renders a template tree (Jinja in file names and contents) |

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

- Needs `uv`, `git`, `curl`, `python3`, `pnpm` (Node.js 20+) and, for `nats`,
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
