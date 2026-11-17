# X module — AGENTS.md

> Scope: `libs/naas-abi-marketplace-modules/naas_abi_apps/x/`, the remote module `applications.x`
> (`python -m naas_abi_apps.x`). The recent-tweets flow of the X application: fetch, map into the graph,
> project into the dataset, publish the Recent Tweets app. Read the [package guide](../../AGENTS.md) (rules, port
> checklist, and its "Decision (2026-11-17): x") and the SDK's README (Jobs, Workflows) first. The app's own code
> (`x_proxy/`) is described in [`x_proxy/README.md`](x_proxy/README.md).

## One process, async handlers, synchronous bodies

The module reaches the engine only over NATS (SDK services). Its large bodies (graph mapping, dataset projection,
app snapshots) stay synchronous, as they were in-engine, and run on the module's **own thread pool**:

- `services.py: SyncModule` (`module.sync`, built in `on_initialized`) is what the synchronous code takes as
  `module`: `configuration`, `engine.services.<svc>` with the SDK's method names, each call blocking until it finished
  on the module's loop, and `run(coro)` for the async `XIntegration`. A blocking call made **on** the loop raises.
- **The pool.** `SyncModule` owns a `ThreadPoolExecutor` (`SYNC_THREADS` = 32 threads named `x-sync_<n>`), shut down
  in `on_unloaded`. `await module.sync.call(fn, *args)` runs a body there (in a copy of the caller's context);
  `module.sync.threaded(fn)` is `fn` as an async function running there. A body must **never** go to the loop's
  default executor (`asyncio.to_thread`, or a bare sync function given to `ctx.step`, which the SDK runs with
  `asyncio.to_thread`): a body blocks waiting on the loop, and the loop resolves host names (httpx) on that same
  executor, so many bodies at once starve the very calls they wait for.
- The workflow and job handlers are async. A workflow hands each synchronous piece to
  `ctx.step(key, module.sync.threaded(fn), ...)`; the probes that are not steps and the jobs call
  `await module.sync.call(fn, ...)`, and so does each request of the app (`x_proxy/app.py`). Never call a
  `module.sync` service from a handler directly.
- The domain classes (`workflows/`, `pipelines/`) are plain synchronous classes built by `flows/common.py` from
  `module.sync`: `x_integration_for(module)` (the bearer token is the engine secret
  `applications.x/X_BEARER_TOKEN`, read in `on_initialized`), the blocking `object_storage` / `triple_store`, and
  `run=sync.run`.

## The flow

```
                      ┌ map_tweet_envelope  (child run per saved envelope, ≤ 4 at a time)
 Cron / Every ─► search_recent_tweets ─┤
 {"filter": name}   budget · fetch ·    └ count_recent_tweets (when the filter follows counts)
                    map · count · dataset · publish
 manual, or  reprocess_tweet_envelopes ─► plan · map (children) · dataset · publish
 files entry

 hourly     build_app        (job)  app rebuild + one media batch
 6-hourly   compact_dataset  (job)  flush + compact of each dataset table
```

None of it depends on `ObjectPut` events: `OnEvent` is at-most-once (events are lost while no host runs). The search
run knows which envelopes it just saved and maps exactly those.

| Name | Kind | Input | Trigger | Body |
|---|---|---|---|---|
| `search_recent_tweets` | workflow, `skip_if_running`, `max_concurrency` = 2 per filter (≤ 64), `max_attempts=3` | `{"filter": <name>}` | one `Cron`/`Every` per `search_recent_tweets_workflow` entry | `flows/search.py` |
| `map_tweet_envelope` | workflow, `max_concurrency=4`, `max_attempts=3` | `{"path", "persist", "force", "graph_name"}` | none (child of the two above; launchable by hand) | `flows/mapping.py` |
| `reprocess_tweet_envelopes` | workflow, `skip_if_running`, `max_concurrency=2`, `max_attempts=2` | `{"prefix", "persist", "force", "max_age_hours", "max_envelopes", "app_publish"}` | manual, plus one `Cron`/`Every` per `search_recent_tweets_files` entry (none by default) | `flows/reprocess.py` |
| `count_recent_tweets` | workflow, `max_attempts=3` | `{"query"}` | none (called by a search run whose filter has `count_recent_tweets: true`) | `flows/count.py` |
| `build_app` | job, `skip_if_running`, `max_concurrency=2` | none | `Cron("0 0 * * * *")` UTC (hourly) | `flows/maintenance.py` |
| `compact_dataset` | job, `skip_if_running`, `max_concurrency=2`, 5 h timeout | none | `Cron("0 30 */6 * * *")` UTC (every 6 h at :30) | `flows/maintenance.py` |

`map_tweet_envelope`, `count_recent_tweets` and the two jobs are methods of `ABIModule` (`@workflow`, `@job`).
`search_recent_tweets` and `reprocess_tweet_envelopes` take their triggers from the configuration, so
`ABIModule.on_load` declares them (`flows/__init__.py: declare_configured_workflows`, `module.declare_workflow`). Inputs
and outputs are pydantic models in `flows/models.py` (no module import). Handlers are thin: they call
`run_<name>(module, ctx, inp)` in `flows/`, which tests drive with fakes (`flows/conftest.py`).

### Overlap: `skip_if_running`

The SDK's `skip_if_running`, on the four declarations above, is an **input claim** (`naas_abi_sdk/job_host.py:
_claim_input`). Before a run starts (before its `RUNNING` record is saved), the host claims the run's input: a
document per job and input in a collection of its own, taken as the module (never with a manual trigger's user
delegation). Then:

- a run whose input **another active run** holds (`RUNNING` with live heartbeats, or `RETRYING`, or claimed just
  now and not saved yet) ends **SKIPPED**, naming that run, instead of queueing behind it. The first run to claim
  goes ahead, whatever the order of the triggers;
- **every attempt** checks, and a run always passes its own claim: a **retry holds its own claim** and never skips
  itself, and nothing runs unchecked;
- a claim whose holder **finished**, or whose **heartbeats stopped** (a crashed host, `lost_after_seconds`), is taken
  over; a finished run also releases its claim (best effort);
- a store error while claiming defers the delivery (redelivered later) without using an attempt.

The skipping tick takes a slot to start, hence two slots (`max_concurrency`) per input that can overlap. Different
filters have different inputs and run independently.

### `search_recent_tweets` — one tick of one filter

Steps, each journaled: `budget` → `fetch` → `map` (`call_each` of `map_tweet_envelope`, child `map[i]` per saved
envelope) → `count` (`ctx.call`, only for a filter with `count_recent_tweets`; a failure is logged and does not fail
the run) → `dataset[n]` (`sync_x_dataset_paths_batched`) → `publish[n]` (only for a filter with `app_publish`).

- **Spend guard.** `budget` asks the workflow's ledger (`XSearchRecentTweetsWorkflow.budget_exhausted_reason`); a spent
  daily or monthly cap ends the run SKIPPED with the reason, no X call. `fetch` checks again inside the workflow (and a
  cap reached in between ends the run SKIPPED too).
- **Retry.** `fetch` is journaled: a run that dies after it and retries does **not** call the X API again, and the
  mapping re-attaches to the child runs it started. A run that dies *inside* `fetch` fetches again from the
  `since_id` cursor. The mapping is idempotent, so is everything after.
- **Children.** `map_tweet_envelope` ends SKIPPED when the envelope is gone or already in the graph **and** the
  dataset; when only the graph has it, it does not run the pipeline (`status: dataset_only`) and the parent's
  `dataset` step catches the dataset up. `force` maps regardless. A skipped child has no output and is not synced.
  With the dataset sync off, nothing is in the dataset: a mapped envelope is `dataset_only`, never SKIPPED.
- **A stage that fails does not stop the others** (`flows/fanout.py`, `flows/search.py`):
  - A fetch that fails **part-way** (a 429 on a later batch) has saved the earlier batches. The step does not raise: it
    returns the paths saved so far (`XSearchRecentTweetsWorkflow.saved_file_paths`) with the error, they are mapped
    like any other, and the run ends FAILED at the end. The spend of the tweets saved is recorded in the ledger.
  - The mapping is `call_each` (asyncio, over `ctx.call`, a semaphore of `MAP_CONCURRENCY`), not `ctx.map_call`
    (which raises on the first failed child and stops the rest): every envelope gets its run, the failures are
    collected, and the dataset sync, the count follow-up and the publish go on with the envelopes that mapped. A
    cancel (or anything but a failed child) stops the children still waiting and goes up.
  - A failed **dataset sync** is collected too; the publish still runs.
  - A failed **app publish** is only logged and returned as `app: {"failed": true, ...}`: it never fails the run;
    the hourly `build_app` catches up.
  - Then, if the fetch, a mapping run or the dataset sync failed, the run raises `FlowIncomplete`: FAILED, with
    *what worked* (`saved N envelope(s), mapped M`) and what did not in its error. A retry re-runs only what failed:
    a child that failed starts again (`map[i]` is FAILED in the journal), the finished ones are replayed, and the
    dataset and publish steps are keyed by the number of envelopes mapped (`dataset[n]`), so a retry that mapped more
    syncs again. A run whose *fetch* failed is **not retried**: it raises `FetchFailed` (a `FlowIncomplete` that is
    also `NonRetryable`), because the journaled fetch would be replayed and fail the same way while the RETRYING run
    made the next ticks of the filter skip. What it saved is mapped first; the next tick fetches again from the
    `since_id` cursor. (An envelope whose mapping failed in such a run is caught up by `reprocess_tweet_envelopes`.)

### `reprocess_tweet_envelopes` — every envelope under a prefix

`plan` lists the envelopes (recursively, optional `max_age_hours`) and sorts them with two bulk probes (the graph's
`x:file_path`s and `envelopes_v1`): not in the graph → map; in the graph, not in the dataset → dataset only; both →
nothing. Then it maps the first ones as child runs, syncs the dataset and (with `app_publish`) republishes the app.
A **second run finds nothing to do**: no child, no sync. A mapping run that fails does not stop the dataset sync of the
others (`FlowIncomplete` at the end, as for the search), and a later run maps only what failed. `force` re-maps
everything. One run takes at most `max_envelopes` (default 1000, at most 1500, and at most 200 KiB of paths, whichever
comes first: the plan is a journaled step, 256 KiB); launch it again for the rest (`truncated` in the output). Launch
it by hand from System → Jobs, or `module.get_workflow("reprocess_tweet_envelopes")`.

**Envelopes saved by other callers are not mapped automatically.** The X agent's tools save envelopes without going
through `search_recent_tweets`. Run this workflow, or **schedule it** with a `search_recent_tweets_files` entry: one
tick per entry, with `prefix`, `persist`, `max_age_hours` (e.g. 24, to keep the listing short), `skip_existing: false`
as `force`, and `app_publish`. A sweep whose previous tick (same input) is still running is SKIPPED.

**Coming from the in-engine module**, the dataset tables live in the module's own namespace and start empty: run this
workflow once with `force: true` to rebuild them from the envelopes, which stay where they were in object storage.

### `build_app` and `compact_dataset`

`build_app` republishes the app (`publish_x_app`, with module `app.publish`: the JSON snapshots only with
`app.dataset.read_enabled`, the web export whatever it says) then downloads one batch of pending media
(`app.dataset.media_batch_size`); a failed publish fails the run.

**The web export at start.** `on_initialized` starts a background task (`flows/maintenance.py:
publish_web_export_at_start`) that uploads the Next export this image carries (`x_proxy/build.py: publish_web_export`,
`required=False`: no export, nothing uploaded) on the module's threads, unless `app.publish` is false. READY does not
wait for it, a failure is only logged, unchanged files are not uploaded again (the export's manifest), and
`on_unloaded` cancels it before it closes the pool. Without it, an upgraded installation would keep serving the
export an earlier version published: the export is replaced only by a publish. Until then the app also rewrites the
in-engine export's base path (`/app-html/x/apps/x_proxy`, plain and `\/`-escaped) to the request's root, as it does
the placeholder of its own build (`x_proxy/app.py: rewrite_root`). `compact_dataset`
flushes then compacts each X table (`x_proxy/dataset/maintenance.py: compact_x_datasets`), a no-op while
`app.dataset.sync_enabled` is off. Expiring old snapshots and deleting unread files is the engine's `dataset_cleanup`.

## Config mapping

Configuration: `X_CONFIG_FILE` (YAML or JSON; the `config:` block of an in-engine `modules:` entry is accepted as it
is, without `bearer_token`, which is refused), then `X_<FIELD>` variables (lists as JSON).

| Config | Remote module |
|---|---|
| `search_recent_tweets_workflow[]` | one trigger of `search_recent_tweets` per entry. `cron` → `Cron` (UTC), `interval_seconds` → `Every`, neither → `Every(60 s)`; both raises at config load. Query, page and save thresholds, spend caps, `persist` (→ the mapping children), `count_recent_tweets`, `app_publish`: as in-engine. More than 16 entries (a descriptor's trigger limit): `search_recent_tweets_2`, … |
| `search_recent_tweets_event[]` | **not used**: mapping is not event-driven (a warning names the entries). The search run maps what it saved; `search_recent_tweets_files` covers the rest. |
| `search_recent_tweets_files[]` | one trigger of `reprocess_tweet_envelopes` per entry (`cron` or `interval_seconds`, default every 1 h 30), carrying `prefix`, `persist`, `max_age_hours`, `app_publish` and `force` = `not skip_existing`. No entry, no schedule: the workflow is then manual only. |
| `count_recent_tweets_workflow[]` | the dashboard catalog only |
| `app.publish`, `app.dataset.*` | as in-engine; the dataset is the module's own namespace |

**Cron dialect.** The configuration keeps the in-engine one: 5 fields (`min hour dom mon dow`), or 6 with the seconds
*last* (croniter), or an `@` macro. NATS takes 6 fields with the seconds *first*: `flows/triggers.py` converts
(`"0 * * * *"` → `"0 0 * * * *"`). An entry NATS cannot schedule is logged and left out.

## What differs from the in-engine module

- **Overlap** is the SDK's `skip_if_running`, which compares whole inputs. In-engine, a sweep blocked another sweep of
  the same **prefix** whatever its other fields; now a manual launch (`{}`) and a scheduled tick of the same prefix
  (with `persist`, `force`, …) do not see each other. Two scheduled ticks of one entry still do. The overlap step and
  `flows/guard.py` (which read the host's run records) are gone, and so is the `overlap` step key.
- **No downstream hook after a mapping.** In-engine, a persisted mapping enqueued pending location extractions
  (`intelligence.utils.OsintPipelinePendingWork`, when that package was importable). A remote module cannot import
  it; a consumer of those envelopes has to pick them up on its own.
- **No Dagster**: no orchestrations, no launchpad overrides, no `enabled` flags, no deferral while a `report_*`
  Dagster job runs; the CLI scripts that booted an engine are retired (the workflows and jobs cover them). A
  downstream `signals.x` subclass is not a concern here (it extended the in-engine class).
- The dataset probes of the mapping (`envelopes_v1`) only run while `app.dataset.sync_enabled` is on; with it off the
  dataset holds nothing anyway.

## Tests

```bash
cd libs/naas-abi-marketplace-modules
uv run --frozen --all-extras pytest naas_abi_apps/x/flows naas_abi_apps/x/tests naas_abi_apps/x/configuration_test.py
uv run --frozen --all-extras pytest naas_abi_apps/x      # the whole module, offline
```

- `flows/*_test.py`: the handler bodies with `FakeFlowContext` (async; journals steps by key with the SDK's JSON and
  size rules, runs a bare sync step as the SDK does, with `asyncio.to_thread`, and records in `off_loop[key]` whether
  the body ran on the module's `x-sync` threads, records child calls), the module's sync view from `x_module`
  (`x_proxy/testing.py: ThreadedSync`, whose `call` / `threaded` run on an `x-sync` pool), and the domain classes or
  `x_proxy` calls stubbed. Running a handler twice on one `journal` shows what a retry does not repeat.
  `count_test.py` runs the bodies on the real `SyncModule` pool.
- `flows/declare_test.py`: what the real `ABIModule` declares from its configuration (descriptors, triggers, cron
  conversion, shards, `skip_if_running`, `max_concurrency`, handlers), without a broker.
- `tests/module_test.py`: the module's id, agent, services, ontologies, configuration (`X_CONFIG_FILE` with an
  in-engine entry, variables) and that nothing imports `naas_abi_core`.

## Adding to the flow

1. A synchronous body goes in `flows/common.py` (or a sibling), takes `module` = the `SyncModule`, and runs on the
   module's threads, never on the loop nor on its default executor: `ctx.step(key, module.sync.threaded(fn), ...)`
   (a workflow) or `await module.sync.call(fn, ...)` (a job, a probe that is not a step). Never `asyncio.to_thread`,
   never a bare sync `fn` given to `ctx.step`.
2. A new step is `await ctx.step("<stable key>", module.sync.threaded(fn), *args)`: its result is JSON, at most
   256 KiB, and the key must be the same on every attempt. Keep a large list out of a step result (store it, return a
   reference).
3. A new workflow is a method on `ABIModule` with `@workflow` (or, when the configuration gives its triggers, a
   `declare_workflow` in `flows/__init__.py`), its models in `flows/models.py`, its body in `flows/`, and a test with
   `FakeFlowContext`. A poller whose ticks must not pile up gets `skip_if_running=True` and two slots per input.
   Document it in the table above.
