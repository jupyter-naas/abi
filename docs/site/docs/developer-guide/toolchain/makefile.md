---
sidebar_position: 1
---

# The ABI Makefile

The `Makefile` at the root of the [ABI repository](https://github.com/jupyter-naas/abi) is a set of shortcuts for working on ABI itself: install, run, test, check and build. A project made with `abi new project` has no such Makefile; it uses the [`abi` CLI](/user-guide/reference/cli) instead.

`make help` prints a summary. It is written by hand and has drifted from the targets: it lists some that do not exist (`test-coverage`, `test-ci`, `test-abi`, `ftest`, `abi-add`), and misses others. This page follows the Makefile.

Packages are managed with [uv](https://docs.astral.sh/uv/) (Python 3.11 is pinned in `.python-version`). Nothing runs inside a Docker container unless the target says so.

## Which targets need NATS

The repository runs on [NATS](/developer-guide/architecture/nats) by default, as a generated project does. Its root `config.yaml` has a `nats:` block that names a broker at `127.0.0.1:4222`, which is the broker of the Docker stack (`abi stack start`). Anything that builds an `Engine()` from that config therefore needs a broker there: `make api`, `make chat` and the other `chat-*` targets, `make mcp`, and tests that load the engine.

- Start a broker with `make local-up` (the whole Docker stack) or `docker compose up -d postgres fuseki nats`. The `nats` service refuses to start until `NATS_ENGINE_PASSWORD`, `NATS_AUTH_PASSWORD` and `NATS_AUTH_CALLOUT_ISSUER` are in `.env`; `abi stack start` (so `make local-up`) generates them.
- Without Docker, `make dev-up` runs the same engine on a native `nats-server` (2.14 or later on `PATH`) and its own ports, so `make api` is not needed there.
- To load the engine in-process with no broker, point `ABI_CONFIG_OVERLAY` at a YAML file that holds `nats: null`. The engine then keeps the in-process wiring of 2.x, and the bus is the `python_queue` adapter.

## Default target

```bash
make
```

Runs `deps`, `local-up` and `airgap`, then `uv run abi chat naas_abi AbiAgent`: install, start the Docker stack on NATS, and open the terminal chat with the main agent. `airgap` only prints a note when `.env` contains `AI_MODE=airgap`. `make help` calls the default target "help"; it is not.

## Environment and dependencies

| Target | What it does |
|---|---|
| `deps` | `uv`, `git-deps`, `.venv` and `.env`: what almost every other target depends on. |
| `.venv` | `uv sync --all-extras`, then `pnpm install` in the Nexus web app (`libs/naas-abi/naas_abi/apps/nexus/apps/web`); it only warns when `pnpm` is missing. |
| `deps-upgrade` | `uv sync --all-extras --upgrade`. |
| `.env` | Does nothing: `abi dev up` and `abi stack start` create and fill `.env` on first run. |
| `git-deps` | Writes `.git/hooks/pre-commit`, which runs `make check`. Skipped when `.git` is not a directory (a git worktree). |
| `uv` | Fails with a link when `uv` is not installed. |
| `lock` | `uv lock`. |
| `local-build` | `docker compose build`. |

`make install` is broken: it depends on a target `dep` that does not exist. Use `uv sync --all-extras`.

## Chat with an agent

Each target runs `uv run abi chat <module> <agent>` and, like the CLI, needs a broker (see above).

```bash
make chat module_name=naas_abi agent_name=AbiAgent
make chat-abi-agent
```

`chat` takes `module_name` and `agent_name` (`make help` shows `agent=`, which the target ignores) and runs at `LOG_LEVEL=DEBUG`. Most of the others use `log_level` (default `INFO`; `make chat-qwen-agent log_level=DEBUG`); the DeepSeek and Gemma targets always run at `DEBUG`.

There is one target per agent of the marketplace: `chat-<name>-agent` for the AI providers (`chatgpt`, `claude`, `deepseek`, `gemini`, `gemma`, `grok`, `llama`, `mistral`, `perplexity`, `qwen`), for the applications (`github`, `gmail`, `hubspot`, `linkedin`, `notion`, `slack`, `stripe` and dozens more, plus `gmail-draft`), and for the domain agents (`chat-support-agent`, `chat-ontology-engineer-agent`, `chat-process-ontology-engineer-agent`). The list is in the Makefile, under "CHAT WITH MARKETPLACE". A target can start the agent only when its module is enabled in the config and its extra is installed.

Four targets pipe a sentence to the Git agent (`naas_abi_marketplace.applications.git`):

| Target | Sentence |
|---|---|
| `pull-request-description` | Generate the pull request description. |
| `commit` | Commit the changes. |
| `push` | Commit the changes, if there are any, and push them. |
| `pr` | Open the pull request, or update it if it exists. |

## Run servers and tools

| Target | What it does |
|---|---|
| `api` | `python -m naas_abi_core.apps.api.api` at `LOG_LEVEL=DEBUG`: the API in the foreground (port 9879). Needs a broker. |
| `api-prod` | Builds `docker/images/Dockerfile.linux.x86_64` as `abi-prod` and runs it with `.env`, `ENV=prod`, port 9879. |
| `api-local` | The same image, as `abi-local`, with `./storage` mounted and `ENV=dev`. |
| `mcp` | `uv run mcp-server`: the [MCP server](/user-guide/build/applications/mcp-server) over STDIO. |
| `mcp-http` | The same with `MCP_TRANSPORT=sse` (the message says port 8000). |
| `mcp-test` | Runs `libs/naas-abi-core/naas_abi_core/apps/mcp/mcp_server_test.py`. |
| `oxigraph-explorer` | Prints `http://localhost:7878/explorer/` and opens it with `open` where that command exists. Does not start anything. |

`sparql-terminal` and `oxigraph-admin` run modules under `src.core.abi.apps`, a path that no longer exists: they fail. Query the knowledge graph with the SPARQL workbench (YasGUI, `http://localhost:3000` in the Docker stack) or through Nexus.

`oxigraph-up`, `oxigraph-down` and `oxigraph-status` run `docker compose --profile local ... oxigraph`, but the root `docker-compose.yml` has no `oxigraph` service. They fail; `make dev-up` starts an Oxigraph server natively.

## Tests

```bash
make test                                # uv run python -m pytest .
uv run pytest libs/naas-abi-core         # one package (see below)
```

| Target | What it runs |
|---|---|
| `test` | `uv run python -m pytest .` from the root: every test of every package. |
| `test-api` | `libs/naas-abi-core/naas_abi_core/apps/api/api_test.py -v -s`. |
| `test-local-embedded-core` | The no-Docker embedded-engine end-to-end test (`EngineConfiguration_LocalEmbeddedE2E_test.py`). |
| `test-integration-core` | Triple store integration tests (Apache Jena TDB2, Oxigraph) with testcontainers, `-m integration`. Starts Docker if needed. |
| `test-document-core` | Document service tests, with the PostgreSQL adapter contract when `DOCUMENT_TEST_POSTGRES_DSN` is set. |
| `test-event-core` | Event and activity log tests, on PostgreSQL when `EVENT_TEST_POSTGRES_DSN` and `DOCUMENT_TEST_POSTGRES_DSN` are set. |
| `test-agent-memory-core` | Agent memory jobs and the checkpoint migration, from PostgreSQL when `DOCUMENT_TEST_POSTGRES_DSN` is set. |
| `test-api-init` | `python -m naas_abi_core.apps.api.test_init`: API initialisation with `uv run --no-dev`. |
| `test-api-init-container` | Builds the image, then runs the same check in it with the API keys taken from your shell. |
| `test-sdk` | The test suites of `libs/naas-abi-proto` and `libs/naas-abi-sdk` (their own Makefiles). |
| `demo-sdk` | `make demo` in `examples/standalone_module`. |

How to write and select tests is in [Test Python scripts](./test_python_scripts).

## Code quality

| Target | What it does |
|---|---|
| `check` | `deps`, then `check-core`, `check-marketplace` and `check-nexus`. The pre-commit hook runs it. |
| `check-core` | `ruff check` on `naas-abi-core`, `naas-abi-cli` and `naas-abi`; `mypy` on `naas_abi_core` and `naas_abi_cli`; `bandit` on the three. |
| `check-marketplace` | `ruff check` and `mypy` on `naas-abi-marketplace` (domains, demos and sandboxes are excluded). |
| `check-nexus` | `pnpm build` of the Nexus web app, to catch frontend errors. |
| `fmt` | `uvx ruff format`. |
| `bandit` | The bandit run of `check-core` alone. |
| `trivy-container-scan` | Builds the image, saves it to `abi.tar` and scans it with `trivy` (must be installed). |
| `onto2py`, `onto2py-force`, `onto2py-clean`, `onto2py-list` | Generate the Python classes next to every `.ttl` under `libs` (`onto2py-force` removes them first). `RUFF` sets the ruff command (default `uvx ruff`). |

## Add a dependency

```bash
make add dep=requests              # root pyproject.toml
make add-abi dep=numpy             # libs/naas-abi
make add-core dep="uvicorn[standard]"
make add-cli dep=...               # libs/naas-abi-cli
make add-marketplace dep=...       # libs/naas-abi-marketplace
```

`make help` and older docs call the second one `abi-add`; the target is `add-abi`. See [Managing dependencies](./manage_dependencies).

## Build

| Target | What it does |
|---|---|
| `build`, `build.linux.x86_64` | `docker build . -t abi -f docker/images/Dockerfile.linux.x86_64 --platform linux/amd64`, then prints the image size. |

## Docker stack, on NATS

The stack is the root `docker-compose.yml`. `abi stack` drives it (see the [CLI reference](/user-guide/reference/cli)).

| Target | What it does |
|---|---|
| `check-docker` | Fails unless Docker runs; tries to start it on macOS and Linux (`sudo` on Linux). |
| `docker-cleanup` | Runs `docker/scripts/cleanup.sh` to clear conflicts and stuck containers. |
| `local-up` | `uv run abi stack start`: Postgres, Fuseki, Qdrant, Redis, MinIO, NATS, the API, Nexus web and the rest. On failure it runs the cleanup script and retries once. |
| `local-logs` | `docker compose --profile legacy logs -f`. |
| `local-stop` | Stops the containers, keeps them. |
| `local-down` | Stops and removes the containers. |
| `local-clean` | `local-down` and removes the volumes. |
| `local-reload` | Removes the containers **and the volumes**, then runs `make local-up`. |
| `container-up`, `container-down` | `docker compose --profile container up -d` and `down`. The compose file has no `container` profile, so this is the same as `docker compose up -d` for the default services. |
| `model-up`, `model-down` | Print a note: Docker AI models start and stop with the services that declare them. `model-status` also lists `docker model ls`. |

`local-logs`, `local-stop`, `local-down`, `local-clean` and `local-reload` pass `--profile legacy`, so they also act on the legacy containers when those run.

## Dev runtime, without Docker

| Target | What it does |
|---|---|
| `dev-up` | `uv run abi dev up -d`: Oxigraph, NATS, the API and Nexus web as native processes, plus the modules of `dev.modules`. Needs `nats-server` 2.14 or later on `PATH`. |
| `dev-down` | `abi dev down`. |
| `dev-status` | `abi dev status`. |

Ports are offset per git worktree; `uv run abi dev ports` lists them.

## Legacy: Dagster, RabbitMQ and the engine without NATS

:::warning Legacy
Dagster, the RabbitMQ bus and `--without-nats` are legacy opt-ins, removed in the next major. On NATS, [module jobs](/developer-guide/architecture/remote-modules#module-jobs) replace Dagster and JetStream replaces RabbitMQ.
:::

| Target | What it does |
|---|---|
| `local-up-legacy` | `abi stack start --legacy`: the stack with Dagster and the RabbitMQ bus, and the engine without NATS. |
| `dev-up-legacy` | `abi dev up -d --without-nats`: the engine in-process, with Dagster when `naas-abi-core[dagster]` is installed. |
| `dagster-dev` | `docker compose --profile legacy up dagster` in the foreground. |
| `dagster-up`, `dagster-down`, `dagster-logs` | Start in the background (UI on port 3001), stop, follow the logs of the `dagster` service. |
| `dagster-ui` | Prints the UI address, then starts the service in the foreground. |
| `dagster-status`, `dagster-materialize` | `dagster asset list` and `dagster asset materialize` in the container, on `src.marketplace.__demo__.orchestration.definitions`, a module path that no longer exists: they fail. |

Next to the engine on NATS, Dagster joins as a client (`ABI_ENGINE_ROLE=client`) and never competes for the serving lease. See [Dagster (legacy)](/user-guide/build/applications/dagster) and [the repository on NATS](https://github.com/jupyter-naas/abi/blob/main/docs/adr/20261015_repository-runs-on-nats.md).

## Data operations

| Target | What it does |
|---|---|
| `ollama-models` | `ollama pull qwen2.5:3b` and `ollama pull nomic-embed-text`: the local-first models. Fails if `ollama` is missing. |
| `dvc-login` | Runs `scripts/setup_dvc.py` to set up DVC authentication. |
| `datastore-pull`, `datastore-push` | Run `scripts/datastore_pull.py` and `scripts/datastore_push.py` (push pulls first). |
| `storage-pull`, `storage-push` | Run `scripts/storage_pull.py` and `scripts/storage_push.py` inside the `abi` container (`docker compose run`). |
| `triplestore-prod-pull` | Pulls the production triple store, in the `abi` container. |
| `triplestore-prod-override` | Overrides the production triple store with local data. |
| `triplestore-prod-remove` | Removes the production triple store. |
| `triplestore-export-excel`, `triplestore-export-turtle` | Export the triple store with `scripts/export_triplestore_excel.py` and `scripts/export_triplestore_turtle.py`. |

The `triplestore-prod-*` targets change production data: read the scripts in `scripts/` before running them.

## Documentation and publishing

| Target | What it does |
|---|---|
| `docs` | `npm install` and `npm run start` in `docs/site`: this site, with live reload, on `http://localhost:3003`. |
| `docs-build` | `npm install` and `npm run build` in `docs/site`. |
| `docs-clean` | Clears the Docusaurus cache and removes `docs/site/build`. |
| `docs-ontology` | `scripts/generate_docs.py`: the ontology documentation. |
| `publish-remote-agents`, `publish-remote-agents-dry-run` | Run `scripts/publish_remote_agents.py`. See [Publish remote agents](/user-guide/deploy/publish_remote_agents): the script currently fails on import. |

## Cleanup

```bash
make clean
```

Removes `__pycache__`, `.pytest_cache`, `build`, `dist`, `*.egg-info`, **`.venv`** and `.mypy_cache`, deletes `*.pyc` and `__pycache__` folders with `sudo find`, runs `docker compose down` and `docker compose rm -f`, and removes `dagster.pid` and `dagster.log`. After it, run `make deps` again.
