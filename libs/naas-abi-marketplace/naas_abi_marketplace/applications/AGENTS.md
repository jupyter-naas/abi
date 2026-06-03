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
| [`airtable/`](airtable/) | A | Spreadsheet-database (records, bases, views) |
| [`gmail/`](gmail/) | A | Google email (read, send, search) |
| [`google_calendar/`](google_calendar/) | A | Calendar events and scheduling |
| [`google_drive/`](google_drive/) | A | Drive files and folders |
| [`google_sheets/`](google_sheets/) | A | Spreadsheet read/write |
| [`google_search/`](google_search/) | AIWO | Programmable Search engine |
| [`google_maps/`](google_maps/) | A | Maps, geocoding, places |
| [`notion/`](notion/) | A | Notion databases and pages |
| [`sharepoint/`](sharepoint/) | A | Microsoft SharePoint |
| [`slack/`](slack/) | A | Workspace messaging |
| [`powerpoint/`](powerpoint/) | AIWO | `.pptx` slide-deck generation/edit |

### Developer tools

| Module | Caps | Description |
|---|:---:|---|
| [`git/`](git/) | A | Local git operations |
| [`github/`](github/) | AIO | GitHub REST + GraphQL (repos, issues, PRs, projects) |
| [`postgres/`](postgres/) | AI | PostgreSQL — query, schema introspection |
| [`aws/`](aws/) | A | AWS SDK surface |
| [`nebari/`](nebari/) | AO | Nebari data-science platform |
| [`naas/`](naas/) | AIWO | Naas platform (workspaces, secrets, storage) |
| [`openrouter/`](openrouter/) | AI | OpenRouter LLM router |

### CRM, sales & marketing

| Module | Caps | Description |
|---|:---:|---|
| [`hubspot/`](hubspot/) | A | HubSpot CRM |
| [`salesforce/`](salesforce/) | A | Salesforce CRM |
| [`zoho/`](zoho/) | A | Zoho CRM |
| [`linkedin/`](linkedin/) | AIWO | Profiles, posts, company pages |
| [`sendgrid/`](sendgrid/) | AI | Transactional / marketing email |

### Finance & accounting

| Module | Caps | Description |
|---|:---:|---|
| [`agicap/`](agicap/) | AI | Cash-flow management |
| [`mercury/`](mercury/) | A | Mercury banking |
| [`pennylane/`](pennylane/) | AI | French accounting platform |
| [`qonto/`](qonto/) | A | Qonto business banking |
| [`stripe/`](stripe/) | A | Payments, customers, subscriptions |
| [`exchangeratesapi/`](exchangeratesapi/) | AI | FX rates |
| [`worldbank/`](worldbank/) | A | World Bank economic indicators |
| [`yahoofinance/`](yahoofinance/) | AI | Public market data |

### Communication & social

| Module | Caps | Description |
|---|:---:|---|
| [`instagram/`](instagram/) | A | Instagram |
| [`spotify/`](spotify/) | A | Music search, playlists |
| [`twilio/`](twilio/) | A | SMS / voice |
| [`whatsapp_business/`](whatsapp_business/) | A | WhatsApp Business messaging |
| [`youtube/`](youtube/) | A | Video search and metadata |

### Research & data

| Module | Caps | Description |
|---|:---:|---|
| [`algolia/`](algolia/) | AI | Search-as-a-service |
| [`arxiv/`](arxiv/) | AIWO | arXiv academic papers |
| [`bodo/`](bodo/) | A | Bodo distributed compute |
| [`datagouv/`](datagouv/) | A | data.gouv.fr open data |
| [`newsapi/`](newsapi/) | A | News headlines |
| [`openalex/`](openalex/) | A | OpenAlex scholarly graph |
| [`openweathermap/`](openweathermap/) | A | Weather data |
| [`pubmed/`](pubmed/) | AIO | PubMed biomedical literature |
| [`sanax/`](sanax/) | AO | Sanax data source |
| [`sec_gov/`](sec_gov/) | I | SEC EDGAR filings |

Total: **47 application modules**.

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
