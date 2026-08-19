# AGENTS — personnel utils

> Scope: `domains/personnel/utils/`. Pure helpers — no `ABIModule`, no services, no tests required unless behaviour changes.

## Purpose

Centralise cross-cutting personnel conventions that are too small for a pipeline or ontology
file but too important to copy-paste:

- minting UUID-based individual IRIs under `http://ontology.naas.ai/personnel/`
- compacting those IRIs for cockpit graph JSON (`personnel:{uuid}`)

## Files

| File | Role |
|---|---|
| `individual_uri.py` | IRI minting + compaction |
| `__init__.py` | Re-exports public API |
| `README.md` | Operator-facing notes |

## Public API

```python
PERSONNEL_ONTOLOGY   # "http://ontology.naas.ai/personnel/"
DEMO_UUID_NS         # uuid.UUID — namespace for uuid5 seeds

personnel_individual_uri(seed: str | None = None) -> str
uuid_part(uri: str | None) -> str | None
compact_personnel(uri: str | None) -> str | None
```

## Rules

1. **Keep utils pure.** No triple-store, object-storage, or FastAPI imports. Side effects belong in pipelines or apps.
2. **Seeded IRIs are stable.** `personnel_individual_uri("alice-dupont")` must stay identical across runs — changing `DEMO_UUID_NS` breaks committed demo TTL/JSON.
3. **Namespace stays in sync.** `PERSONNEL_ONTOLOGY` must match `ABIModule.Configuration.ontology_namespace` in `personnel/__init__.py`.
4. **Do not hand-edit compact ids in JSON.** Generate them via `compact_personnel` / `compact_graph_id` so exports stay consistent with the graph.
5. **Add a file here only when reused.** One-off script logic stays in `sandbox/` or `apps/cockpit/scripts/` (data exporters only) or the relevant pipeline.

## Consumers

| Consumer | Uses |
|---|---|
| `apps/cockpit/graph_payload.py` | `compact_personnel` via `compact_graph_id` |
| Demo graph / export scripts | `personnel_individual_uri(seed=…)` when minting deterministic individuals (import when needed) |

When adding a new consumer, import from `utils.individual_uri` (or `utils`) — not from a duplicated constant elsewhere.

## Adding a utility

1. Drop a focused module under `utils/` (one concern per file).
2. Re-export from `utils/__init__.py` if it is part of the stable public surface.
3. Document behaviour in `README.md` and list the consumer(s) in this file.
4. Add unit tests next to the module (`*_test.py`) when logic is non-trivial or easy to regress.
