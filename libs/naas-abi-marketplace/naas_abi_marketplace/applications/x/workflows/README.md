# X workflows

> Scope: `workflows/` of the X module. The module's flow (search, map, count, dataset,
> app) and its config mapping are in [`../AGENTS.md`](../AGENTS.md); the runtime is in
> `libs/naas-abi-core/naas_abi_core/module/AGENTS.md` (Workflows).

The X module has two kinds of workflow:

- **Durable workflows** (NATS mode, the default), declared on `ABIModule` in
  [`../__init__.py`](../__init__.py), with their bodies in [`../flows/`](../flows/). They
  are what runs the recent-tweets flow: the engine hosts them, they show in Nexus under
  System → Jobs, and their steps are journaled, so a retried run does not call the X API
  again for a fetch that finished.
- **Workflow classes**, in this folder: the X API calls those durable workflows (and the
  legacy Dagster orchestrations) build and run.

## Durable workflows and jobs

| Name | Kind | Input (`../flows/models.py`) | Trigger |
|---|---|---|---|
| `search_recent_tweets` | workflow, `max_attempts=3`, two slots per filter | `{"filter": <name>}` | one `Cron`/`Every` per `search_recent_tweets_workflow` entry (more than 16 entries: `search_recent_tweets_2`, …) |
| `map_tweet_envelope` | workflow, `max_concurrency=4`, `max_attempts=3` | `{"path", "persist", "force", "graph_name"}` | none: a child run of the two others, or started by hand |
| `reprocess_tweet_envelopes` | workflow, `max_concurrency=2`, `max_attempts=2` | `{"prefix", "persist", "force", "max_age_hours", "max_envelopes", "app_publish"}` | manual, plus one `Cron`/`Every` per `search_recent_tweets_files` entry |
| `count_recent_tweets` | workflow, `max_attempts=3` | `{"query"}` | none: called by a search run whose filter has `count_recent_tweets: true` |
| `build_app` | job | none | hourly |
| `compact_dataset` | job | none | every six hours, at :30 |

`search_recent_tweets` runs the steps `overlap` → `budget` → `fetch` → `map` (one
`map_tweet_envelope` child run per saved envelope) → `count` → `dataset` → `publish`. A
tick of a filter whose previous run is still going ends `SKIPPED`; a spent daily or monthly
cap ends it `SKIPPED` before any X call. What each step does on failure and on retry is in
[`../AGENTS.md`](../AGENTS.md).

### Start one by hand

The module id is `naas_abi_marketplace.applications.x`.

- **Nexus:** System → Jobs, **Workflows** filter, then the workflow and **Run now**. The
  form is built from the input model.
- **HTTP:** `POST /api/workflows/naas_abi_marketplace.applications.x/reprocess_tweet_envelopes/runs`
  with `Authorization: Bearer $ABI_API_KEY` and the input as the body (`?wait=<seconds>` to
  wait for the result).
- **Code:** `module.get_workflow("reprocess_tweet_envelopes")`, then
  `await proxy.run({"prefix": "..."})`, or `.start(...)` for a run to follow.

Envelopes that the X agent's tools or the scripts save are not mapped until a
`reprocess_tweet_envelopes` run, by hand or from a `search_recent_tweets_files` entry.

## Workflow classes

| Class | Calls | Used by |
|---|---|---|
| `XSearchRecentTweetsWorkflow` | X v2 recent search, incrementally from each query's `since_id`; saves each response as a JSON envelope in object storage; keeps the daily and monthly spend ledger | the `fetch` and `budget` steps of `search_recent_tweets` (`../flows/common.py`), and the Dagster search orchestration |
| `XCountRecentTweetsWorkflow` | X v2 tweet counts per clock hour: a 7-day backfill on the first run of a query, then only the hours completed since | `count_recent_tweets` (`../flows/common.py`) |

Both take an `XIntegration` and the object storage service in their configuration, which
the engine cannot supply, so the engine does not build them at startup: they have no agent
tools, no `POST /workflows/...` route and no `workflow.<slug>` durable workflow of their
own. The durable workflows above build them with the module's credentials and run them in
a journaled step.

Each file also runs on its own, against a running stack (`abi dev up`):

```bash
uv run python libs/naas-abi-marketplace/naas_abi_marketplace/applications/x/workflows/XCountRecentTweetsWorkflow.py \
    --queries '(python OR rust) lang:en -is:retweet'
```

`XSearchRecentTweetsWorkflow.py --help` lists its options (pages, time window,
`--no-persist`).

## Legacy: Dagster

Without NATS (`--without-nats`, with the `naas-abi-core[dagster]` extra), the Dagster
orchestrations in [`../orchestrations/`](../orchestrations/README.md) drive the same
classes and the same bodies in `../flows/`. They are removed in the next major.

## Tests

```bash
uv run --frozen pytest libs/naas-abi-marketplace/naas_abi_marketplace/applications/x/workflows
uv run --frozen pytest libs/naas-abi-marketplace/naas_abi_marketplace/applications/x/flows
```
