---
sidebar_position: 2
title: "Testing"
---

# Testing

What tests ABI has, how to run each kind, and which CI job runs what. The
conventions (where a test file lives, naming) are in [Contribute to ABI](/developer-guide/contributing/overview#conventions).
For Makefile targets, see [The Makefile](/developer-guide/toolchain/makefile).

---

## Unit tests

Plain `pytest`, no services. Tests sit beside their source (`*_test.py`) or in a module's
`tests/`.

```bash
make test                                         # uv run python -m pytest .
uv run pytest libs/naas-abi-core                  # one package
uv run pytest libs/naas-abi-cli
uv run pytest libs/naas-abi
uv run pytest libs/naas-abi-marketplace

# one file, one class, one test, a keyword
uv run pytest libs/naas-abi-core/naas_abi_core/services/keyvalue/adapters/secondary/PythonAdapter_test.py -v
uv run pytest libs/naas-abi-core -k "postgres or checkpointer" -v
```

`pytest.ini` turns on strict markers and coverage output. Tests that need an external service
carry the `integration` marker and say so; keep tests deterministic and isolate those
requirements explicitly.

The CLI suite (`libs/naas-abi-cli`) renders templates and stubs `subprocess`. It also holds
`cli_reference_test.py`, which walks the Click command tree and fails when a command or an
option is missing from the [CLI reference](/user-guide/reference/cli), or when a page of this
site shows an `abi` command or option that does not exist.

## The SDK and proto packages

`naas-abi-proto` and `naas-abi-sdk` are tested in isolation, without `naas-abi-core`, on
Python 3.10 to 3.12:

```bash
uv run --project libs/naas-abi-proto pytest libs/naas-abi-proto/tests -q
uv run --project libs/naas-abi-sdk pytest libs/naas-abi-sdk/tests -q
uv run --project libs/naas-abi-sdk --extra models pytest libs/naas-abi-sdk/tests/test_models.py -q
```

## NATS integration tests (nats-server)

Tests of the broker-facing code start a real `nats-server`. Install **2.14 or later** on `PATH`
(CI pins v2.14.7): a test that needs it is skipped when it is missing, and **fails** instead
when `ABI_REQUIRE_NATS_SERVER=1`, as in CI.

```bash
export ABI_REQUIRE_NATS_SERVER=1
uv run --project libs/naas-abi-core --all-extras pytest --import-mode=importlib -q \
  libs/naas-abi-core/naas_abi_core/engine/nats_rpc_integration_test.py \
  libs/naas-abi-core/naas_abi_core/services/discovery/discovery_integration_test.py
uv run --project libs/naas-abi-core --no-sync pytest -q \
  libs/naas-abi-sdk/tests/test_jobs_integration.py
```

The list CI runs (RPC, transfers, discovery, permissions, shutdown, the engine lease and
handover, module jobs, the kernel services over a real broker) is in
`.github/workflows/standalone_sdk.yml`, job `nats-integration`. Run the group that matches
what you changed.

## PostgreSQL suites: document, event and agent memory

The document service contract runs on SQLite always and on PostgreSQL when a DSN is set. The
event log, the activity log and the agent memory migration are the same. Start any PostgreSQL
(`docker run -e POSTGRES_PASSWORD=... -p 5432:5432 postgres:17`), then:

```bash
export DOCUMENT_TEST_POSTGRES_DSN=postgresql://user:password@localhost:5432/test
export EVENT_TEST_POSTGRES_DSN=$DOCUMENT_TEST_POSTGRES_DSN
make test-document-core         # document service and its adapter contract
make test-event-core            # event log and activity log adapters
make test-agent-memory-core     # agent memory jobs, checkpoint migration from PostgreSQL
```

Without the DSNs the PostgreSQL cases are skipped and the SQLite ones run.

## Testcontainers

`make test-integration-core` runs the triple store adapters (Apache Jena Fuseki and Oxigraph)
against containers started by [testcontainers](https://testcontainers.com): it needs a running Docker
daemon (`make check-docker` tries to start it).

```bash
make test-integration-core
```

## Nexus web

The web app has [Vitest](https://vitest.dev) tests beside its code and a TypeScript check:

```bash
cd libs/naas-abi/naas_abi/apps/nexus/apps/web
pnpm test            # vitest run
pnpm typecheck       # tsc --noEmit
pnpm lint            # next lint
pnpm build           # the production build, also run by `make check`
```

The Nexus API has Python tests beside its services under `libs/naas-abi/naas_abi/apps/nexus/apps/api`
(`uv run pytest libs/naas-abi`).

## The CLI smoke test

`scripts/cli_smoke.sh` runs the CLI for real, as the [Quickstart](/user-guide/get-started/quickstart)
does: it installs the CLI from the checkout, creates a project, adds modules, starts it with
`abi dev up -d`, checks the API, the remote module's discovery, Nexus and Nexus web, then stops
it. No Docker, no model.

```bash
scripts/cli_smoke.sh nats             # the default project; 5 to 10 minutes
scripts/cli_smoke.sh without-nats     # the legacy project
```

It needs `uv`, `git`, `curl`, `python3`, `pnpm` (Node.js 20 or later) and, for `nats`,
`nats-server` 2.14 or later. The project's `.abi` is a clone of the checkout's HEAD: commit
what you want tested. Details: `libs/naas-abi-cli/AGENTS.md`.

## Docs

```bash
cd docs/site
npm ci
npm run build              # broken links fail the build
npm run check:redirects    # every route of the pre-split site still resolves; needs a build
```

---

## Which CI job runs what

| Workflow, job | Runs |
|---|---|
| `pull_request.yml`, `document-tests` | `make test-document-core`, `make test-event-core` and `make test-agent-memory-core` on PostgreSQL 17, Python 3.11 and 3.12 |
| `pull_request.yml`, `check` | `make check` (ruff, mypy, bandit, the Nexus web build) and `make test-integration-core` (testcontainers), Python 3.11 and 3.12. The API tests and the container API initialisation test are disabled there. |
| `pull_request.yml`, `container-scan` | Builds the image and scans it with Trivy |
| `standalone_sdk.yml`, `packages` | proto and SDK tests on 3.10 to 3.12, the optional extras, and the wheel builds |
| `standalone_sdk.yml`, `nats-integration` | The NATS integration tests above, on nats-server v2.14.7 with `ABI_REQUIRE_NATS_SERVER=1` |
| `cli_e2e.yml` | `scripts/cli_smoke.sh` for `nats` and `without-nats`, on every PR into `main` |
| `docs.yml` | The docs build and `npm run check:redirects` when `docs/site` changes |

No workflow runs `make test` (the whole suite), `pnpm test` or the Nexus API tests: run
them yourself when you change those areas.
