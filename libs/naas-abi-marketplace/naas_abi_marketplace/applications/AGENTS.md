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
| [`x/`](x/) | AIWPO | X (Twitter) search ingestion, x_proxy app | Port to a remote module tracked in sub-issues of #1423 |

Every other application (GitHub, LinkedIn, Google Search, PostgreSQL,
PowerPoint, Pennylane, Agicap, ArXiv, PubMed, SEC EDGAR, Sanax, Nebari, ...) is a
**remote module** in [`libs/naas-abi-marketplace-modules`](../../../naas-abi-marketplace-modules/README.md):
its own process, reaching the engine over NATS. The in-engine versions were
removed (jupyter-naas/abi#1423); `applications.openrouter` was replaced by
`naas_abi_marketplace.ai.openrouter`. The placeholder agents without tools
(Airtable, Gmail, Slack, Stripe and 23 others) were removed too.

**Migration.** A project that loads one of the removed modules in `modules:`
(e.g. `naas_abi_marketplace.applications.pennylane`) removes that entry and
runs the remote module instead (`dev.modules`, or a container built from
`libs/naas-abi-marketplace-modules/Dockerfile`; see its README). Credentials
move from the module's `config:` to engine secrets of the same name.

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
when it must run in the engine process, as the four above do:

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
uv run pytest libs/naas-abi-marketplace/naas_abi_marketplace/applications/x
uv run pytest libs/naas-abi-marketplace/naas_abi_marketplace/applications/git/agents/GitAgent_test.py -v
```
