# naas-abi-marketplace-modules

The marketplace application modules (`naas_abi_marketplace.applications.*`)
ported to **remote modules** ([#1423](https://github.com/jupyter-naas/abi/issues/1423)).
Each one runs in its own process, registers itself through discovery, and
reaches the engine only over NATS with `naas-abi-sdk`. None imports
`naas_abi_core`, `naas_abi` or `naas_abi_marketplace`.

| Application | Package | Module id | Agents / workflows | Replaces (removed) |
|---|---|---|---|---|
| Agicap | `naas_abi_apps.agicap` | `applications.agicap` | `Agicap` | `naas_abi_marketplace.applications.agicap` |
| Algolia | `naas_abi_apps.algolia` | `applications.algolia` | `Algolia` | `naas_abi_marketplace.applications.algolia` |
| ArXiv | `naas_abi_apps.arxiv` | `applications.arxiv` | `ArXivAgent`; pipeline `ar_xiv_paper_pipeline` | `naas_abi_marketplace.applications.arxiv` |
| ExchangeRatesAPI | `naas_abi_apps.exchangeratesapi` | `applications.exchangeratesapi` | `ExchangeRatesAPI` | `naas_abi_marketplace.applications.exchangeratesapi` |
| GitHub | `naas_abi_apps.github` | `applications.github` | `GitHub` | `naas_abi_marketplace.applications.github` |
| Google Search | `naas_abi_apps.google_search` | `applications.google_search` | `Google_Search`; workflows `search_linked_in_profile_page_workflow`, `search_linked_in_organization_page_workflow` | `naas_abi_marketplace.applications.google_search` |
| LinkedIn | `naas_abi_apps.linkedin` | `applications.linkedin` | `LinkedIn`, `LinkedIn_KG`; workflow `create_class_embeddings_workflow` | `naas_abi_marketplace.applications.linkedin` |
| Naas | `naas_abi_apps.naas` | `applications.naas` | `Naas` (agent and integration only) | `naas_abi_marketplace.applications.naas` |
| Nebari | `naas_abi_apps.nebari` | `applications.nebari` | `Nebari` (+ ontologies) | `naas_abi_marketplace.applications.nebari` |
| Pennylane | `naas_abi_apps.pennylane` | `applications.pennylane` | `Pennylane` | `naas_abi_marketplace.applications.pennylane` |
| PowerPoint | `naas_abi_apps.powerpoint` | `applications.powerpoint` | `PowerPoint`; workflow `create_presentation_from_template_workflow`, pipeline `add_power_point_presentation_pipeline` | `naas_abi_marketplace.applications.powerpoint` |
| PostgreSQL | `naas_abi_apps.postgres` | `applications.postgres` | `PostgreSQL` | `naas_abi_marketplace.applications.postgres` |
| PubMed | `naas_abi_apps.pubmed` | `applications.pubmed` | `PubMedAgent`; pipeline `pub_med_pipeline` | `naas_abi_marketplace.applications.pubmed` |
| Sanax | `naas_abi_apps.sanax` | `applications.sanax` | `Sanax`; pipeline `sanax_linked_in_sales_navigator_extractor_pipeline` | `naas_abi_marketplace.applications.sanax` |
| SEC EDGAR | `naas_abi_apps.sec_gov` | `applications.sec_gov` | none; workflows `download_company_tickers_workflow`, `get_company_submissions_workflow` | `naas_abi_marketplace.applications.sec_gov` |
| SendGrid | `naas_abi_apps.sendgrid` | `applications.sendgrid` | `SendGrid` | `naas_abi_marketplace.applications.sendgrid` |
| Yahoo Finance | `naas_abi_apps.yahoofinance` | `applications.yahoofinance` | `YahooFinance` | `naas_abi_marketplace.applications.yahoofinance` |

## Run one

```bash
uv sync --extra pennylane      # the extra of the application (sec-gov for sec_gov)
ABI_NATS_URL=nats://127.0.0.1:4222 \
ABI_SERVICE_KEY=abi_sk_... \
ABI_DISCOVERY_PROJECT=<project> \
uv run python -m naas_abi_apps.pennylane
```

Each module runs as the service account `module/<project>/<module id>` (here
`module/<project>/applications.pennylane`), on its own key: create it in the
project with `abi iam service-account create module/<project>/applications.pennylane --key`
(shown once). The URL carries no login: the key logs in to the broker. At start
the module submits its permission manifest (derived from its declared services)
and waits for `abi iam module approve module/<project>/applications.pennylane`;
`abi dev up` creates the key and approves by itself.

It is up when it logs `READY`; its agent then appears in Nexus. Credentials are
engine secrets (e.g. `PENNYLANE_API_KEY`), read through the `secret` service.
Other settings come from `<APP>_<FIELD>` variables (`PENNYLANE_CHAT_MODEL`,
`PENNYLANE_DATASTORE_PATH`, ...).

In a project, add it to `dev.modules` (for `abi dev up`):

```yaml
dev:
  modules:
    - name: pennylane
      module: naas_abi_apps.pennylane
      module_id: applications.pennylane
```

and, for Docker, a service built from this folder:

```yaml
services:
  pennylane:
    build:
      context: ./.abi/libs/naas-abi-marketplace-modules
      additional_contexts:
        abi_proto: ./.abi/libs/naas-abi-proto
        abi_sdk: ./.abi/libs/naas-abi-sdk
      args: { APP: pennylane }
    restart: unless-stopped
    environment:
      - ABI_NATS_URL=nats://nats:4222
      - ABI_SERVICE_KEY=${ABI_SERVICE_KEY_PENNYLANE:?abi iam service-account create module/<project>/applications.pennylane --key}
      - ABI_DISCOVERY_PROJECT=<project>
    depends_on: { abi: { condition: service_healthy } }
    networks: [abi-network]
```

and remove `naas_abi_marketplace.applications.pennylane` from `modules:` if an
older configuration still lists it: the in-engine modules were removed.

## Develop

```bash
uv sync --all-extras
uv run pytest            # offline: no broker, no engine, third-party APIs mocked
uvx ruff check naas_abi_apps
```

See `AGENTS.md` for the conventions and the decisions behind this layout.
