# X Orchestrations

Dagster orchestrations for the X (Twitter) application. They split the
"recent tweet search → knowledge graph" flow into three independent,
event-decoupled pieces. Each orchestration file exposes an `Orchestrations`
subclass that the module loader discovers automatically.

## The flow

```
                 fetch + save                         ObjectPut event
 X v2 API  ───────────────────────►  object storage  ───────────────────►  triple store
            XSearchWorkflow                  (JSON       XSearchRecentTweets
            Orchestration                  envelopes)    EventOrchestration
                                                         (XSearchRecentTweetsPipeline)
```

1. **`XSearchWorkflowOrchestration`** — *fetch + save only.*
   One (job, sensor) pair per `search_recent_tweets_workflow` config entry.
   Each sensor wakes every `interval_seconds` and (unless a run is already in
   flight) drives `XSearchRecentTweetsWorkflow`, which recovers the query's
   `since_id` from previously-saved envelopes, calls the X v2
   `search_recent_tweets` endpoint, and **persists each `{query, options,
   results, …}` response as a JSON envelope** in object storage. It does **not**
   touch the graph. A per-filter spend guard (daily / monthly tweet or USD caps)
   can stop fetches without an API call. Sensors are **STOPPED by default**.

2. **`XSearchRecentTweetsEventOrchestration`** — *map on file-put.*
   One (job, sensor) pair per `search_recent_tweets_event` config entry. Each
   sensor subscribes to `ObjectPut` events on the bus (durable consumer cursor
   keyed on the sensor name — every put seen exactly once) and, for each new
   envelope under its `prefix`, runs `XSearchRecentTweetsPipeline` in
   `file_path` mode to map the full SearchQuery / SearchResultSet /
   SearchRecentTweets / Tweet structure into the graph. No polling. This is the
   mapping half of the flow — saving an envelope in step 1 publishes the
   `ObjectPut` that triggers it. The watched-prefix filter is pushed down into
   the event query; the sensor also probes object storage and skips events
   whose file has since been deleted. Sensors are **STOPPED unless
   `enabled: true`** (the example config enables `search_envelopes`).

3. **`XSearchRecentTweetsFilesOrchestration`** — *manual bulk reprocess.*
   A single job, **no sensor / no schedule / no X API call**. Launch it from the
   Dagster launchpad with a `prefix` to sweep **every** envelope under that
   folder back through `XSearchRecentTweetsPipeline`. Use it to backfill or
   re-ingest the whole graph after a mapping change without re-querying X.
   Idempotent — the pipeline's label-based dedupe makes a re-run a no-op. (This
   is the file-by-file sibling of step 2 for one-shot, all-at-once runs.)

## Why decouple fetch from mapping

Previously the workflow job both fetched **and** mapped, while the event sensor
*also* mapped the same envelope — double work that only stayed correct thanks to
dedupe. Splitting them means: fetching is purely about spend / `since_id`
bookkeeping; mapping is purely about the graph and is retried independently per
file via the durable event cursor. Enable the workflow sensors to collect, keep
the event sensor enabled to map, and reach for the files orchestration when you
need a full re-ingest.

## Shared helpers (`utils/`)

- `safe_name` — sanitise a filter name into a Dagster-safe job/op/sensor id.
- `launchpad_override` — prefer a launchpad-supplied op value, else the ABI
  config default.
- `has_in_progress_run` — skip a workflow tick when its job is still running.
- `run_search_pipeline_for_file` — run `XSearchRecentTweetsPipeline` in
  `file_path` mode for one envelope (used by the event and files orchestrations).

## Configuration

See `XTweetSearchWorkflowConfiguration` (`search_recent_tweets_workflow`) and
`XSearchRecentTweetsEventConfiguration` (`search_recent_tweets_event`) in the
module `__init__.py` for the full set of config fields and a worked example.
