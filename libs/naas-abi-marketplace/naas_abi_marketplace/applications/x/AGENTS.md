# X module — AGENTS.md

> Scope: `libs/naas-abi-marketplace/naas_abi_marketplace/applications/x/`. The recent-tweets flow of the X
> application: fetch, map into the graph, project into the dataset, publish the Recent Tweets app. Read the
> [marketplace guide](../../AGENTS.md) for the module shape and [`scripts/AGENTS.md`](scripts/AGENTS.md) for the CLI scripts.

## Two engines, one set of bodies

| Engine | Where | Runs when | Entry points |
|---|---|---|---|
| **Durable NATS workflows and jobs** | `flows/`, declared on `ABIModule` (`__init__.py`) | the engine runs on NATS (the default); `abi dev up` hosts them, no Dagster process | System → Jobs |
| **Dagster orchestrations** (legacy) | `orchestrations/` | `--without-nats`, with the `naas-abi-core[dagster]` extra; removed in the next major | the Dagster UI |

The orchestration files are kept and unchanged in behaviour. Both engines call the **same** functions: the shared
bodies live in `flows/common.py` (graph, envelopes, counts, app), `flows/envelopes.py` (listing and age filter of
envelopes) and `flows/maintenance.py` (media batch, compaction), none of which imports Dagster.
`orchestrations/utils/_common.py` re-exports them next to what only Dagster needs (run statuses, sensor and schedule
contexts, the report-window deferral). Put a new shared body in `flows/`, never in `orchestrations/`.

## The NATS flow

```
                      ┌ map_tweet_envelope  (child run per saved envelope, ≤ 4 at a time)
 Cron / Every ─► search_recent_tweets ─┤
 {"filter": name}   overlap · budget ·  └ count_recent_tweets (when the filter follows counts)
                    fetch · map · count · dataset · publish
 manual, or  reprocess_tweet_envelopes ─► overlap · plan · map (children) · dataset · publish
 files entry

 hourly     build_app        (job)  app rebuild + one media batch
 6-hourly   compact_dataset  (job)  DuckLake compaction
```

None of it depends on `ObjectPut` events: `OnEvent` is at-most-once (events are lost while no host runs), whereas the
Dagster sensor had a durable cursor. The search run knows which envelopes it just saved and maps exactly those.

| Name | Kind | Input | Trigger | Body |
|---|---|---|---|---|
| `search_recent_tweets` | workflow, `max_concurrency` = 2 per filter, `max_attempts=3` | `{"filter": <name>}` | one `Cron`/`Every` per `search_recent_tweets_workflow` entry, input `{"filter": name}` | `flows/search.py` |
| `map_tweet_envelope` | workflow, `max_concurrency=4`, `max_attempts=3` | `{"path", "persist", "force", "graph_name"}` | none (child of the two above; launchable by hand) | `flows/mapping.py` |
| `reprocess_tweet_envelopes` | workflow, `max_concurrency=2`, `max_attempts=2` | `{"prefix", "persist", "force", "max_age_hours", "max_envelopes", "app_publish"}` | manual, plus one `Cron`/`Every` per `search_recent_tweets_files` entry (none by default) | `flows/reprocess.py` |
| `count_recent_tweets` | workflow, `max_attempts=3` | `{"query"}` | none (called by a search run whose filter has `count_recent_tweets: true`) | `flows/count.py` |
| `build_app` | job, `max_concurrency=2` | none | `Cron("0 0 * * * *")` UTC (hourly) | `__init__.py`, `flows/maintenance.py` |
| `compact_dataset` | job, `max_concurrency=2` | none | `Cron("0 30 */6 * * *")` UTC (every 6 h at :30) | `__init__.py`, `flows/maintenance.py` |

Inputs and outputs are pydantic models in `flows/models.py` (no module import, so `__init__.py` can use them).
Handlers are thin: `ABIModule.<name>` imports its body from `flows/` and calls `run_<name>(module, ctx, inp)`; the
bodies take the module and a `SyncFlowContext`, so tests drive them with fakes (`flows/conftest.py`).

The two jobs skip a tick whose previous run is still going, like the search (a second slot lets the overlapping tick
start and skip; their guard is `flows/guard.py: earlier_active_runs_sync`).

### `search_recent_tweets` — one tick of one filter

Steps, each journaled (`ctx.step`): `overlap` → `budget` → `fetch` → `map` (`ctx.map_call` of `map_tweet_envelope`, one
child per saved envelope) → `count` (`ctx.call`, only for a filter with `count_recent_tweets`; a failure is logged and
does not fail the run) → `dataset` (`sync_x_dataset_paths_batched`) → `publish` (only for a filter with `app_publish`).
- **Overlap.** A tick of a filter whose previous run is still `RUNNING` (or `RETRYING`) ends **SKIPPED** with the older
  run's id; it is never queued behind it. Different filters run independently. `max_concurrency` is two per filter: a running tick
  and the overlapping one, which needs a slot of its own to start and skip (with one slot it would queue). The check reads the job's run records (`flows/guard.py`); only a run that **started earlier**
  blocks, so two ticks that start together do not both skip, and a run never skips itself on a retry (the decision is
  a journaled step). A crashed host's run blocks until the upkeep fails it (heartbeats stop).
  The check reads the host's run records (`module._job_host()`: `documents`, `collection`; fields `job`, `status`,
  `sequence`, `payload`), which is internal to the jobs runtime. It checks itself: the host saves a run as `RUNNING`
  before its handler starts, so the lookup must find the run's own record, else the run fails with `OverlapCheckBlind`
  instead of guessing "no overlap" (which would double-fetch and double-spend). A proper `skip_if_running` trigger option in
  the SDK would replace it (follow-up).
- **Spend guard.** `budget` asks the workflow's ledger (`XSearchRecentTweetsWorkflow.budget_exhausted_reason`); a spent
  daily or monthly cap ends the run SKIPPED with the reason, no X call. `fetch` checks again inside the workflow.
- **Retry.** `fetch` is journaled: a run that dies after it and retries does **not** call the X API again, and the
  mapping re-attaches to the child runs it started (the ADR's "child runs"). A run that dies *inside* `fetch` fetches
  again from the `since_id` cursor, as a Dagster re-run did. The mapping is idempotent, so is everything after.
- **Children.** `map_tweet_envelope` ends SKIPPED when the envelope is gone or already in the graph **and** the
  dataset; when only the graph has it, it does not run the pipeline (`status: dataset_only`) and the parent's
  `dataset` step catches the dataset up. `force` maps regardless. A skipped child has no output and is not synced.
- **A stage that fails does not stop the others** (`flows/fanout.py`, `flows/search.py`). Under Dagster one bad
  envelope only affected itself, and the `ObjectPut` sensor mapped whatever a failed fetch had saved. So:
  - A fetch that fails **part-way** (a 429 on a later batch) has saved the earlier batches. The step does not raise: it
    returns the paths saved so far (`XSearchRecentTweetsWorkflow.saved_file_paths`) with the error, they are mapped
    like any other, and the run ends FAILED at the end. The spend of the tweets saved is recorded in the ledger.
  - The mapping is `call_each`, not `ctx.map_call` (which raises on the first failed child and stops the rest): every
    envelope gets its run, the failures are collected, and the dataset sync, the count follow-up and the publish go on
    with the envelopes that mapped.
  - A failed **dataset sync** is collected too (Dagster's op failed on it as well); the publish still runs.
  - A failed **app publish** is only logged and returned as `app: {"failed": true, ...}`: it never fails the run,
    as `publish_app_after_search` and `republish_x_app_after_pipeline` never did; the hourly `build_app` catches up.
  - Then, if the fetch, a mapping run or the dataset sync failed, the run raises `FlowIncomplete`: FAILED, with
    *what worked* (`saved N envelope(s), mapped M`) and what did not in its error, so the failure does not hide the work.
    A retry re-runs only what failed: a child that failed starts again (`map[i]` is FAILED in the journal), the finished
    ones are replayed, and the dataset and publish steps are keyed by the number of envelopes mapped (`dataset[n]`), so
    a retry that mapped more syncs again. A run whose *fetch* failed replays the journaled fetch (it does not call X
    again, by design) and fails again; the next tick continues from the `since_id` cursor.

### `reprocess_tweet_envelopes` — every envelope under a prefix

`plan` lists the envelopes (recursively, optional `max_age_hours`) and sorts them with two bulk probes (the graph's
`x:file_path`s and `envelopes_v1`): not in the graph → map; in the graph, not in the dataset → dataset only; both →
nothing. Then it maps the first ones as child runs, syncs the dataset and (with `app_publish`) republishes the app.
A **second run finds nothing to do**: no child, no sync. A mapping run that fails does not stop the dataset sync of the
others (`FlowIncomplete` at the end, as for the search), and a later run maps only what failed. `force` re-maps everything. One run takes at most
`max_envelopes` (default 1000, at most 1500: the plan is a journaled step, 256 KiB); launch it again for the rest
(`truncated` in the output). Launch it by hand from System → Jobs, `/api/workflows`, or `module.get_workflow("reprocess_tweet_envelopes")`.

**Envelopes saved by other callers are not mapped automatically.** The X agent's tools and the scripts save envelopes
without going through `search_recent_tweets`; the Dagster `ObjectPut` sensor mapped them, and nothing does under NATS.
Run this workflow, or **schedule it** with a `search_recent_tweets_files` entry (below): one tick per entry, with
`prefix`, `persist`, `max_age_hours` (e.g. 24, to keep the listing short), `skip_existing: false` as `force`, and
`app_publish`. A tick whose previous sweep of the same prefix is still running is SKIPPED, like the search.

### Config mapping

| Config | Under NATS |
|---|---|
| `search_recent_tweets_workflow[]` | one trigger of `search_recent_tweets` per entry. `cron` → `Cron` (UTC), `interval_seconds` → `Every`, neither → `Every(60 s)`; both still raises at config load. Query, page and save thresholds, spend caps, `persist` (→ the mapping children), `count_recent_tweets`, `app_publish`: as in Dagster. More than 16 entries (a descriptor's trigger limit): `search_recent_tweets_2`, … |
| `search_recent_tweets_event[]` | **not used**: mapping is not event-driven. (`prefix`, `events_per_tick`, `max_concurrent_runs`, `persist`, `app_publish` have no NATS counterpart; the search run maps what it saved.) |
| `search_recent_tweets_files[]` | one trigger of `reprocess_tweet_envelopes` per entry (`cron` or `interval_seconds`, default every 1 h 30), carrying `prefix`, `persist`, `max_age_hours`, `app_publish` and `force` = `not skip_existing`. No entry, no schedule: the workflow is then manual only. |
| `count_recent_tweets_workflow[]` | the dashboard catalog only, as before |
| `app.publish`, `app.dataset.*` | as before |

**Cron dialect.** The configuration keeps Dagster's: 5 fields (`min hour dom mon dow`), or 6 with the seconds *last*
(croniter), or an `@` macro. NATS takes 6 fields with the seconds *first*: `flows/triggers.py` converts
(`"0 * * * *"` → `"0 0 * * * *"`). An entry NATS cannot schedule is logged and left out.

### What is not ported

- Envelopes saved by **other callers** are not mapped until a `reprocess_tweet_envelopes` run: see its section.
- Dagster's launchpad overrides (per-run `max_pages`, caps…), the `enabled` flags, and the deferral of the dataset
  sync and of the hourly rebuild while a `report_*` Dagster job runs (that is a Dagster-only concept).
- A downstream `signals.x` subclass does not declare the jobs a second time (as for the orchestrations).

## Tests

```bash
uv run --frozen pytest libs/naas-abi-marketplace/naas_abi_marketplace/applications/x/flows          # handlers with fakes
uv run --frozen pytest libs/naas-abi-marketplace/naas_abi_marketplace/applications/x/tests          # what the module declares
ABI_REQUIRE_NATS_SERVER=1 uv run --frozen pytest \
  libs/naas-abi-marketplace/naas_abi_marketplace/applications/x/flows/flows_integration_test.py   # real nats-server
uv run --frozen pytest libs/naas-abi-marketplace/naas_abi_marketplace/applications/x/orchestrations  # Dagster, unchanged
```

`flows_integration_test.py` hosts the real `ABIModule` on a `nats-server` (skipped when it is not installed): a search
run fans out the mapping, the host is killed after the fetch, and the retry maps without calling X again and starts
no new child; a fetch that fails after saving still gets its envelope mapped; one unmappable envelope does not stop the
others; an overlapping tick is SKIPPED while another filter runs; reprocess twice is a no-op; the jobs run.
Some orchestration and artifact tests fail on `main` already (date-dependent fixtures, an uninitialised module at
import in `XIntegration_test.py`); they are unrelated.

## Adding to the flow

1. A new shared body goes in `flows/common.py` (or a sibling), with no Dagster import; call it from the Dagster op and
   from the handler.
2. A new step is `ctx.step("<stable key>", fn, *args)`: its result is JSON, at most 256 KiB, and the key must be the
   same on every attempt. Keep a large list out of a step result (store it, return a reference).
3. A new workflow is a method on `ABIModule` with `@workflow`, its models in `flows/models.py`, its body in `flows/`,
   and a test with `FakeFlowContext`. Document it in the table above.
4. See `docs/adr/20261025_durable-workflows-on-nats.md` for the runtime, and `libs/naas-abi-core/naas_abi_core/module/AGENTS.md`.
