# X scripts — AGENTS.md

> Catalog: [`README.md`](README.md). Module: `signals.x` + `naas_abi_marketplace.applications.x` (dataset sync config on marketplace module).

## When to use which script

| Goal | Script | Writes? |
|------|--------|---------|
| Check envelope lag before/after backfill | `audit_envelope_bookkeeping.py` | **No** |
| Catch up `envelopes_v1` / posts from storage | `backfill_x_datasets.py` | **Yes** |

Steady-state ingest uses Dagster (`x_sensor_recent_tweets_put_search_recent_tweets` for new puts, `x_reprocess_recent_tweets_files_schedule_*` for catch-up including dataset-only when graph ⊃ dataset) and `sync_envelope_paths` inside orchestrations—not these CLIs.

## `audit_envelope_bookkeeping.py`

- Lists `.json` envelopes under `--envelope-prefix` (default `x/search_recent_tweets`) via object storage `walk`.
- Compares to `envelope_path` rows in namespace **`x`**, table **`envelopes_v1`**.
- Fields: `pending_ingest`, `ingested_not_in_storage`, `in_sync`.
- `--strict`: exit 1 when out of sync.
- Fix lag with `backfill_x_datasets.py` (not the audit script).
- Logic: `signals.x.apps.x_proxy.dataset.envelope_bookkeeping`.

Use `apps/x_proxy/dataset/count_audit.py` or `dataset/api.graph_totals` for row-count sanity checks.

## Running locally

Compose sets `LOG_LEVEL=DEBUG` on the shared `abi` anchor; one-off CLIs are quieter with **`LOG_LEVEL=INFO`** (still shows backfill batch lines and `sync_envelope_paths` summaries).

```bash
docker compose exec -T abi env LOG_LEVEL=INFO uv run python \
  src/signals/x/scripts/audit_envelope_bookkeeping.py --config config.local.yaml

docker compose exec -T abi env LOG_LEVEL=INFO uv run python \
  src/signals/x/scripts/backfill_x_datasets.py --config config.local.yaml \
  --pending-from-audit --batch-size 8
```

Host `uv run` fails if config uses Docker service names (`fuseki`, `minio`, `postgres`).

**Pending ingest on prod:** build `/tmp/x_pending.txt` once (audit JSON), then backfill with `--paths-file` only — avoid re-running the full audit before every backfill.

## Do not

- Run `backfill_x_datasets.py --force` without user confirmation (re-ingests all listed paths).
- Confuse `envelopes_v1` with Fuseki `graph/x` (graph mapping is orchestration pipeline, not this audit).
