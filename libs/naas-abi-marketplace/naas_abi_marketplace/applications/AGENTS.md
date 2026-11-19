# Application Modules — AGENTS.md

> Scope: `libs/naas-abi-marketplace/naas_abi_marketplace/applications/`. Quick index for third-party app integrations. See the [marketplace master guide](../../AGENTS.md) for module shape and conventions.

## What's here

Each subdirectory is a marketplace module wrapping a third-party service. Every module:

- Declares the LLM module it uses (typically `naas_abi_marketplace.ai.chatgpt`) in `ABIModule.dependencies.modules`.
- Exposes a `Configuration` with credentials (API keys, tokens) for the third-party service.
- Ships an `agents/<App>Agent.py` (`IntentAgent`) that exposes the integration as tools.
- Often ships `integrations/<App>Integration.py` — a typed Python wrapper over the third-party API.

## Capability legend

In the table below: **A** = agent, **I** = integration wrapper, **W** = workflows, **O** = ontologies.

## Application index

| Module | Caps | Description | Why in-engine |
|---|:---:|---|---|
| [`git/`](git/) | A | Local git operations | Runs `git`, `make` and `gh` in the CLI's working directory (`make commit`, `make pr`) |
| [`bodo/`](bodo/) | A | Bodo distributed compute | Runs Python that imports `bodo.pandas` in the engine process |
| [`naas/`](naas/) | IWO | Ontology YAML publishing to a Naas workspace | Workflows and triggers on the engine's triple store, used by `ontology_engineer` |

Every other application (GitHub, LinkedIn, Google Search, PostgreSQL,
PowerPoint, Pennylane, Agicap, ArXiv, PubMed, SEC EDGAR, Sanax, Nebari, X, ...) is a
**remote module** in [`libs/naas-abi-marketplace-modules`](../../../naas-abi-marketplace-modules/README.md):
its own process, reaching the engine over NATS. The in-engine versions were
removed (jupyter-naas/abi#1423); `applications.openrouter` was replaced by
`naas_abi_marketplace.ai.openrouter`. The placeholder agents without tools
(Airtable, Gmail, Slack, Stripe and 23 others) were removed too.

**Migration.** A project that loads one of the removed modules in `modules:`
(e.g. `naas_abi_marketplace.applications.pennylane`) removes that entry and
runs the remote module instead (`dev.modules`, or a container built from
`libs/naas-abi-marketplace-modules/Dockerfile`; see its README). Credentials
move from the module's `config:` to engine secrets named
`<module id>/<NAME>` (e.g. `applications.pennylane/PENNYLANE_API_KEY`): the
engine lets a module read only the secrets under its own id.

**Migration of `applications.x`** (jupyter-naas/abi#1425–#1428). The remote
module `naas_abi_apps.x` (id `applications.x`) replaces the in-engine module,
its Dagster orchestrations and its CLI scripts:

- **Configuration.** Copy the `naas_abi_marketplace.applications.x` entry of
  `config.yaml` (its `config:` block, or the whole entry) into a YAML file and
  point `X_CONFIG_FILE` at it; remove the entry from `modules:`. Its
  `search_recent_tweets_workflow` entries become the triggers of the
  `search_recent_tweets` workflow (one per entry, `{"filter": <name>}`), its
  `search_recent_tweets_files` entries the triggers of
  `reprocess_tweet_envelopes`; `count_recent_tweets_workflow` and `app` keep
  their meaning. `search_recent_tweets_event` is not used (each search run maps
  the envelopes it saved) and is only warned about. Delete `bearer_token`: the
  token is the engine secret `applications.x/X_BEARER_TOKEN`.
- **Dataset.** The tables move from the engine's `x` namespace to the module's
  own dataset namespace. Run `reprocess_tweet_envelopes` once (System → Jobs,
  with `force: true`) to rebuild them, and the graph mapping if needed, from
  the envelopes in object storage (`x/search_recent_tweets/`, unchanged).
- **App.** The Recent Tweets app is `remote/applications.x:x_proxy`, served by
  the module through Nexus (`/app-remote/...`) instead of `/app-html/x/apps/x_proxy/`.
- **Scripts and Dagster.** The orchestrations (`--without-nats` only) and the
  scripts are gone: `search_recent_tweets`, `reprocess_tweet_envelopes`
  (backfills, imports), `compact_dataset` and `build_app` are durable workflows
  and jobs, launched from System → Jobs or on their schedules.

## Module shape (recap)

```
applications/<app>/
├── __init__.py            # ABIModule(dependencies=ModuleDependencies(modules=[...], services=[...]))
├── agents/
│   ├── <App>Agent.py      # IntentAgent exposing integration tools
│   └── <App>Agent_test.py
├── integrations/          # (when present) typed wrapper(s) over the third-party API
│   └── <App>Integration.py
├── workflows/             # (when present) reusable multi-step automations
├── ontologies/            # (when present) RDF/OWL/TTL of the third-party domain
└── on_load_test.py        # smoke test for ABIModule.on_load()
```

## Configuration example

```yaml
modules:
  - module: naas_abi_marketplace.applications.git
    enabled: true
```

## Adding a new application module

A new third-party integration is a **remote module** in
`libs/naas-abi-marketplace-modules` (see its `AGENTS.md`). Add one here only
when it must run in the engine process, as the three above do:

1. Scaffold `applications/<app>/` with `__init__.py` declaring:
   - `dependencies.modules` — usually one `ai.<provider>` module.
   - `dependencies.services` — e.g. `[ObjectStorageService, TripleStoreService]`.
   - `Configuration` fields for every required credential.
2. Implement `integrations/<App>Integration.py` — pure Python wrapper, **no LLM calls**, returns typed Pydantic models when possible.
3. Implement `agents/<App>Agent.py` as an `IntentAgent`:
   - Bind the integration's methods as tools.
   - Define intents that route user prompts to the right tool.
4. Tests:
   - `<App>Agent_test.py` — calls `create_agent().invoke(...)` over canned scenarios.
   - `on_load_test.py` — verifies the module loads with a minimal config.
   - `<App>Integration_test.py` — unit tests for the API wrapper (mock the HTTP layer).
5. Add a `[applications-<app>]` optional-extra group in `pyproject.toml` if it pulls heavy deps.
6. Optionally add a `<App>Workflow.py` under `workflows/` for canonical automations.

## Tests

```bash
uv run pytest libs/naas-abi-marketplace/naas_abi_marketplace/applications
uv run pytest libs/naas-abi-marketplace/naas_abi_marketplace/applications/git/agents/GitAgent_test.py -v
```
