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

### Productivity & collaboration

| Module | Caps | Description |
|---|:---:|---|
| [`google_search/`](google_search/) | AIWO | Programmable Search engine |
| [`powerpoint/`](powerpoint/) | AIWO | `.pptx` slide-deck generation/edit |

### Developer tools

| Module | Caps | Description |
|---|:---:|---|
| [`git/`](git/) | A | Local git operations |
| [`github/`](github/) | AIO | GitHub REST + GraphQL (repos, issues, PRs, projects) |
| [`postgres/`](postgres/) | AI | PostgreSQL — query, schema introspection |
| [`nebari/`](nebari/) | AO | Nebari data-science platform |
| [`x/`](x/) | AIWPO | X (Twitter) search ingestion, x_proxy app |
| [`naas/`](naas/) | AIWO | Naas platform (workspaces, secrets, storage) |
| [`openrouter/`](openrouter/) | AI | OpenRouter LLM router |

### CRM, sales & marketing

| Module | Caps | Description |
|---|:---:|---|
| [`linkedin/`](linkedin/) | AIWO | Profiles, posts, company pages |
| [`sendgrid/`](sendgrid/) | AI | Transactional / marketing email |

### Finance & accounting

| Module | Caps | Description |
|---|:---:|---|
| [`agicap/`](agicap/) | AI | Cash-flow management |
| [`pennylane/`](pennylane/) | AI | French accounting platform |
| [`exchangeratesapi/`](exchangeratesapi/) | AI | FX rates |
| [`yahoofinance/`](yahoofinance/) | AI | Public market data |

### Research & data

| Module | Caps | Description |
|---|:---:|---|
| [`algolia/`](algolia/) | AI | Search-as-a-service |
| [`arxiv/`](arxiv/) | AIWO | arXiv academic papers |
| [`bodo/`](bodo/) | A | Bodo distributed compute |
| [`pubmed/`](pubmed/) | AIO | PubMed biomedical literature |
| [`sanax/`](sanax/) | AO | Sanax data source |
| [`sec_gov/`](sec_gov/) | I | SEC EDGAR filings |

Total: **21 application modules**. The placeholder agents without tools (Airtable, Gmail, Slack, Stripe and 23 others) were removed (jupyter-naas/abi#1423); most modules are being ported to remote modules in `libs/naas-abi-marketplace-modules`.

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
  - module: naas_abi_marketplace.applications.github
    enabled: true
    config:
      github_access_token: "{{ secret.GITHUB_ACCESS_TOKEN }}"
      datastore_path: "github"
```

## Adding a new application module

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
uv run pytest libs/naas-abi-marketplace/naas_abi_marketplace/applications/github
uv run pytest libs/naas-abi-marketplace/naas_abi_marketplace/applications/github/agents/GitHubAgent_test.py -v
```
