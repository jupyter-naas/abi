# X workflows

> Scope: `workflows/` of the remote X module (`applications.x`). The durable workflows
> and jobs the module declares (search, map, count, dataset, app), their triggers and
> their config mapping are in [`../AGENTS.md`](../AGENTS.md), with their bodies in
> [`../flows/`](../flows/).

The classes here are the X API calls those durable workflows build and run. They are
**plain classes**, not SDK `Workflow` subclasses: the SDK publishes every `Workflow`
subclass found under `workflows/` as `workflow.<slug>`, and these have a synchronous
`run` that the flows call in a worker thread, with the module's credentials, in a
journaled step. So they have no agent tools, no route and no durable workflow of their
own.

| Class | Calls | Used by |
|---|---|---|
| `XSearchRecentTweetsWorkflow` | X v2 recent search, incrementally from each query's `since_id`; saves each batch as a JSON envelope in object storage; keeps the daily and monthly spend ledger per filter | the `fetch` and `budget` steps of `search_recent_tweets` (`../flows/common.py`) |
| `XCountRecentTweetsWorkflow` | X v2 tweet counts per clock hour, from graph state: the missing complete hours below the newest mapped tweet, then the hour in progress as a partial | `count_recent_tweets` (`../flows/common.py`) |

Both take, in their configuration, the async `XIntegration`
(`integrations.XIntegration.x_integration_for(module)`), the blocking services of a
`services.SyncModule` (`object_storage`, and `triple_store` for the counts) and its
`run`, through which every X API call goes:

```python
sync = module.sync
workflow = XSearchRecentTweetsWorkflow(
    XSearchRecentTweetsWorkflowConfiguration(
        x_integration=x_integration_for(sync),
        object_storage=sync.engine.services.object_storage,
        run=sync.run,
        datastore_path=sync.configuration.datastore_path,
        budget_key=filter_config.name,
        # caps and save thresholds of the filter
    )
)
output = await asyncio.to_thread(
    workflow.run, XSearchRecentTweetsWorkflowParameters(queries=[query], options=...)
)
```

## Spend ledger

`<datastore_path>/_budget/<filter slug>.json` holds the tweets retrieved per UTC day and
per month (`{"daily": {"2026-06-22": 1234}, "monthly": {"2026-06": 56789}}`). Before a
run, a reached daily or monthly cap (tweets, or USD at `cost_per_tweet_usd`; the smaller
wins) returns `budget_blocked` without calling X. After it, the tweets returned are
recorded, also when a later batch failed (the batches saved before were billed). The X
agent's `x_search_recent_tweets` goes through the same ledger code, keyed `agent`
(`search_with_budget`, `../agents/XAgent.py`).

## Tests

```bash
cd libs/naas-abi-marketplace-modules
uv run --frozen --all-extras pytest naas_abi_apps/x/workflows
```
