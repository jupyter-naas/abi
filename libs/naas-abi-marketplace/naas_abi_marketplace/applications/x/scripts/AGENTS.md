# X scripts — AGENTS.md

> Catalog: [`README.md`](README.md). Module: `signals.x` + `naas_abi_marketplace.applications.x` (dataset sync config on marketplace module).

## When to use which script

| Goal | Script | Writes? |
|------|--------|---------|
| Check envelope lag before/after backfill | `audit_envelope_bookkeeping.py` | **No** |
| Catch up `envelopes_v1` / posts from storage | `backfill_x_datasets.py` | **Yes** |
| Validate Parquet cache vs dataset totals | `compare_x_dataset_cache.py` | **No** |

Steady-state ingest uses Dagster (`x_sensor_recent_tweets_put_search_recent_tweets`, files reprocess job) and `sync_envelope_paths` inside orchestrations—not these CLIs.

## `audit_envelope_bookkeeping.py`

- Lists `.json` envelopes under `--envelope-prefix` (default `x/search_recent_tweets`) via object storage `walk`.
- Compares to `envelope_path` rows in namespace **`x`**, table **`envelopes_v1`**.
- Fields: `pending_ingest`, `ingested_not_in_storage`, `in_sync`.
- `--strict`: exit 1 when out of sync.
- Fix lag with `backfill_x_datasets.py` (not the audit script).
- Logic: `signals.x.apps.x_proxy.dataset.envelope_bookkeeping`.

**Parquet cache:** `x/cache/processed_envelopes.json` is separate (columnar projection). Use `apps/x_proxy/dataset/count_audit.py` for a three-way envelope/cache/dataset sanity check.

## Running locally

```bash
docker compose exec -T abi uv run python src/signals/x/scripts/audit_envelope_bookkeeping.py --config config.local.yaml
```

Host `uv run` fails if config uses Docker service names (`fuseki`, `minio`, `postgres`).

## Do not

- Run `backfill_x_datasets.py --force` without user confirmation (re-ingests all listed paths).
- Confuse `envelopes_v1` with Fuseki `graph/x` (graph mapping is orchestration pipeline, not this audit).
