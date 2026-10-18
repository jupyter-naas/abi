---
sidebar_position: 1
title: "Contribute to ABI"
---

# Contribute to ABI

How to set up the ABI repository, run it, and follow its conventions. To fork and keep
your fork up to date, see [Setup Git remote](/developer-guide/contributing/setup_git_remote).
To test, see [Testing](/developer-guide/contributing/testing); to release,
[Releasing](/developer-guide/releasing/release-process).

---

## Set up

You need [git](https://git-scm.com/), [uv](https://docs.astral.sh/uv/getting-started/installation/),
Node.js 18.17 or later with [pnpm](https://pnpm.io/installation) (for Nexus web), and, to run the
repository natively, `nats-server` 2.14 or later on `PATH`
([install](/user-guide/get-started/install)).

```bash
git clone https://github.com/jupyter-naas/abi.git
cd abi
uv sync --all-extras
uv pip install greenlet                    # SQLAlchemy's asyncpg needs it
cd libs/naas-abi/naas_abi/apps/nexus/apps/web && pnpm install && cd -
```

`make deps` does the same (`uv sync --all-extras` and the web app's `pnpm install`). It does not create `.env`: the first `abi dev up` or `abi stack start` does. The repository is a Python monorepo
managed by `uv`:

| Package | Path | What |
|---|---|---|
| `naas-abi-proto` | `libs/naas-abi-proto` | The protobuf contracts of the kernel services |
| `naas-abi-sdk` | `libs/naas-abi-sdk` | The SDK of remote modules (no `naas-abi-core` import) |
| `naas-abi-core` | `libs/naas-abi-core` | The engine, the kernel services and their adapters |
| `naas-abi-marketplace` | `libs/naas-abi-marketplace` | AI providers, integrations, domain agents |
| `naas-abi` | `libs/naas-abi` | The default agents and Nexus (API and web) |
| `naas-abi-cli` | `libs/naas-abi-cli` | The `abi` command |

## Run it

The repository runs on NATS by default, like a generated project
([ADR](https://github.com/jupyter-naas/abi/blob/main/docs/adr/20261015_repository-runs-on-nats.md)).

```bash
uv run abi dev up -d        # oxigraph, nats-server, api, nexus-web, no Docker
uv run abi dev status
uv run abi dev down
```

Ports are offset per git worktree (`abi dev ports`). `.env` is created on the first run with
the admin login, `ABI_API_KEY` and the NATS secrets. The root `config.yaml` also names
`OPENAI_API_KEY`, `OPENROUTER_API_KEY` and `GITHUB_ACCESS_TOKEN` in active YAML, so a fresh
clone needs them set; a placeholder lets the API boot. The first API boot takes two to three
minutes: watch `abi dev logs api`, it is ready when `/docs` answers.

With Docker, the same stack as a project's:

```bash
uv run abi stack start      # Postgres, Fuseki, Qdrant, MinIO, Redis, NATS, API, Nexus web
uv run abi stack status
uv run abi stack stop
```

For `abi stack`, point `.env` at `localhost`, not at the Docker service names (`POSTGRES_HOST=localhost`).
The web UI is then at http://localhost:3042; the admin password is `NEXUS_USER_ADMIN_EXAMPLE_COM_PASSWORD`
in `.env`.

:::info Legacy
Dagster and RabbitMQ sit behind the `legacy` Compose profile: `abi stack start --legacy`
runs them and the engine without NATS, and `abi dev up --without-nats` runs the in-process
engine. They are removed in the next major.
:::

`abi chat`, `make api` and tests that build an `Engine()` from the root config need a
broker at `127.0.0.1:4222` (the Docker stack's). To load the engine in-process without one,
point `ABI_CONFIG_OVERLAY` at a YAML file that holds `nats: null`.

## Read the nearest `AGENTS.md`

Every service and domain has an `AGENTS.md`: its purpose, files, port, public API, adapters,
factory, tests and how to add an adapter. They are in-tree and kept current. Before you work
somewhere, read the closest one walking up from the file; if the scope has none, create one
with the same structure. The map is in the root [`AGENTS.md`](https://github.com/jupyter-naas/abi/blob/main/AGENTS.md):

- `libs/naas-abi-core/naas_abi_core/services/<service>/AGENTS.md` for each kernel service
  (activity log, agent, bus, cache, document, email, event, keyvalue, model registry, object
  storage, ontology, secret, triple store, vector store);
- `libs/naas-abi-marketplace/AGENTS.md` for modules (AI providers, applications, domains);
- `libs/naas-abi-cli/AGENTS.md` for the CLI; `libs/naas-abi/naas_abi/apps/nexus/AGENTS.md` for Nexus.

## Conventions

- **Hexagonal architecture.** Domain logic depends on ports, never on infrastructure. A
  domain is self-contained: interfaces, domain, primary and secondary adapters, factories,
  tests. **Every secondary adapter implements every abstract method of its port**, raising
  `NotImplementedError` with a clear message for what it does not support.
- **Tests beside their source**, or in the module's `tests/`. A test of one file sits next to
  it (`users.py` and `users_test.py`). A test with no single natural neighbour (module-wide
  behaviour, something defined in `__init__.py`) goes in the module's `tests/`, which also
  holds shared `artifacts/` fixtures. Both forms are intentional. Test-driven development is
  preferred; keep tests deterministic and isolate integration requirements explicitly.
- **Style.** `ruff format` is the formatter (`make fmt`); absolute imports from package roots;
  type hints on new public APIs, with modern generics (`list[str]`). In `naas_abi_core`, many
  production files use `PascalCase.py`: keep the style of the directory.
- **Errors.** Raise specific exceptions at domain and service boundaries; catch them at adapter
  or API boundaries to translate; never swallow one silently.
- **Decisions.** A change to a boundary, an ownership, cross-cutting configuration or a major
  trade-off gets an ADR in `docs/adr/`, named `YYYYMMDD_topic.md`, with Status, Date,
  Context, Decision and Consequences. See the [ADR index](/developer-guide/adr).
- **Commits** follow Conventional Commits (`feat:`, `fix:`, `docs:`, ...): the type drives the
  release. A breaking change carries a `BREAKING CHANGE:` footer.
- **Docs.** A change to a command, a config key or a behaviour updates its page of this site in the
  same PR. `abi docs sync --fail-on-stale` checks the library reference.

Quality gates before you push: `make check` (ruff, mypy, bandit, the Nexus build) and the
tests of what you touched ([Testing](/developer-guide/contributing/testing)).
