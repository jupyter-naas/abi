# X signal CLI scripts (`signals.x.scripts`)

Manual ops for envelope → Dataset Service projection and diagnostics. Run from repo root:

`uv run python src/signals/x/scripts/<name>.py --config config.local.yaml`

On Docker Compose hosts, prefer **`docker compose exec -T abi env LOG_LEVEL=INFO uv run python …`** so MinIO, DuckLake, and Fuseki hostnames resolve (`config.local.yaml`) without DEBUG engine noise.

| Script | Added | Purpose |
|--------|-------|---------|
| `audit_envelope_bookkeeping.py` | 2026-09-22 | Read-only diff: `x/search_recent_tweets` JSON vs `x.envelopes_v1`. |
| `backfill_x_datasets.py` | 2026-09 (dataset mirror) | Stream envelopes into Dataset Service (`sync_envelope_paths`). |
| `import_x_dataset_batches.py` | 2026-09 | Import staged batch manifests into datasets. |
| `XIntegration_diagnose_account.py` | — | X API account diagnostic CLI. |

Agent notes: [`AGENTS.md`](AGENTS.md).
