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
| X | `naas_abi_apps.x` | `applications.x` | `X`; workflows `search_recent_tweets`, `reprocess_tweet_envelopes`, `map_tweet_envelope`, `count_recent_tweets`; jobs `build_app`, `compact_dataset`; app `x_proxy` | `naas_abi_marketplace.applications.x` |
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
engine secrets under the module's id: `applications.pennylane/PENNYLANE_API_KEY`,
read through the `secret` service. The engine lets a module account read only
the secrets under its own `<module id>/` prefix; a missing secret is logged at
start with its full name, and the agent runs without the tools that need it.
Other settings come from `<APP>_<FIELD>` variables (`PENNYLANE_CHAT_MODEL`,
`PENNYLANE_DATASTORE_PATH`, ...).

An agent on a credential the module holds for the whole deployment acts with
it for everyone who may use the agent, so it reads, and writes only where its
settings say:

| Module | Setting | Default |
| --- | --- | --- |
| GitHub | `GITHUB_AGENT_WRITE_TOOLS`: write tools the agent carries besides the read tools (comma-separated tool names) | none |
| GitHub | `GITHUB_REPOSITORIES`: the only repositories it reaches (comma-separated `owner/repo`) | any |
| SendGrid | `SENDGRID_ALLOWED_SENDERS`: the only addresses it sends from (comma-separated) | none: nothing is sent |
| PostgreSQL | `POSTGRES_READ_ONLY`: one statement that leaves the transaction and session alone, read-only, never committed | `true` |

No agent tool deletes a GitHub repository, writes an Actions secret, reveals a
Naas secret value or storage credentials, deletes a Naas workspace, plugin or
ontology, or changes workspace membership: those stay integration methods.
Google Search reads only pages on public addresses (every redirect checked,
5 MB and 30 s caps) and keeps no copy of them.

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

## X

`applications.x` has more configuration than `X_<FIELD>` variables carry
comfortably: point `X_CONFIG_FILE` at a YAML (or JSON) file holding the fields,
for example the `config:` block of the in-engine module's `modules:` entry,
copied as it is, without `bearer_token`. The bearer token is the engine secret
`applications.x/X_BEARER_TOKEN`.

```yaml
# x.yaml
search_recent_tweets_workflow:
  - name: ai_llms
    query: '(openai OR anthropic) lang:en -is:retweet'
    cron: "0 * * * *"          # or interval_seconds; one per entry
    max_pages: 1
    daily_max_usd: 20          # spend caps per filter (tweets or USD, day or month)
    monthly_max_usd: 250
search_recent_tweets_files:    # schedules reprocess_tweet_envelopes (optional)
  - name: reprocess_envelopes
    cron: "0,15,30,45 * * * *"
    max_age_hours: 24
count_recent_tweets_workflow:
  - name: ai_llms
    query: '(openai OR anthropic) lang:en -is:retweet'
    enabled: true
```

Each `search_recent_tweets_workflow` entry is one trigger of the
`search_recent_tweets` workflow; a tick of a filter whose previous run is still
going is SKIPPED. The Recent Tweets app opens in Nexus as
`remote/applications.x:x_proxy`. Coming from the in-engine module, run
`reprocess_tweet_envelopes` once with `force: true` to rebuild the dataset in
the module's namespace (see `naas_abi_marketplace/applications/AGENTS.md`).

## Develop

```bash
uv sync --all-extras
uv run pytest            # offline: no broker, no engine, third-party APIs mocked
uvx ruff check naas_abi_apps
```

See `AGENTS.md` for the conventions and the decisions behind this layout.
