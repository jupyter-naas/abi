# Building modules — AGENTS.md

> Canonical playbook for coding agents building or extending a module in this workspace.
> Copy the [Module checklist](#9-module-checklist) into the new module's own `AGENTS.md`
> and fill it in. Keep this file current as the platform evolves.

Two rules govern everything below:

1. **Cost must scale with the delta or the query window — never with total history.**
2. **Build on the services the platform already declares.** Never invent a parallel
   mechanism.

Everything else is how to honour those two under pressure.

---

## 1. Measure before you optimise

Do not guess which part is slow, and do not optimise from intuition about what "looks
expensive". Get a number first, from the real system.

The diagnostic that matters most:

> **Does a query that matches *nothing* cost about the same as one that matches a lot?**

If yes, you are paying for a scan, and the cost is O(total data) — it will grow every
week regardless of what the user is looking at. That single question separates "slow
today" from "broken in three months".

A real example from the X module:

```
count_tweets_in_window  24h window   1.27s  → 14,596 rows
count_tweets_in_window  7d-prev      1.58s  →      0 rows
```

The empty window cost *more*. That is the whole diagnosis: the window filter was
decorative, and every publish re-scanned the entire graph.

Record the baseline before touching anything (`mean`, `median`, `p90` over real runs —
Dagster's GraphQL API gives you this), so the "after" number means something.

---

## 2. Know which growth curve you are on

| pattern | cost | verdict |
|---|---|---|
| One scan per window / per column / per scenario | O(total) × N | broken; fix the multiplier *and* the curve |
| One scan for all windows (banded / shared aggregate) | O(total) | better, but still erodes weekly |
| Read a partitioned projection for the window | O(window) | correct |
| Refresh from an append-only log past a watermark | O(delta) | correct |

Removing a multiplier is worth doing and cheap — but say plainly that it is a one-off
saving, not a fix. Do not let "40 queries → 15 queries" be mistaken for scalability.

---

## 3. Use the platform's services

The `services:` block in `config.local.yaml` / `config.remote.yaml` is the roster. Reach
for these before adding anything:

| service | adapter | use it for |
|---|---|---|
| `object_storage` | s3 / MinIO (`abi`, prefix `abi/datastore`) | raw event envelopes, artifacts, snapshots, Parquet caches |
| `triple_store` | apache_jena_tdb2 (Fuseki) | ontology, source of truth, SPARQL |
| `kv` | redis | watermarks, locks, run state, cheap counters |
| `vector_store` | qdrant | embeddings, semantic search |
| `bus` | rabbitmq | event-driven fan-out between pipelines |
| `model_registry` | `default_chat_model` / `default_embedding_model` | **never hardcode a model id** |
| `email` | ses | notifications, digests |
| `secret` | dotenv | every credential — never inline one |

Why this matters beyond tidiness: these are **ports with swappable adapters**. Code
written against the service keeps working when the adapter changes between local and
remote. A local file, a hardcoded host, or a new database breaks that portability — and
in practice those shortcuts are also the ones whose cost grows with total data.

**Local disk is not a service.** Anything written to a container filesystem is gone on
the next deploy. If it must survive, it belongs in `object_storage`.

---

## 4. Source of truth vs. derived read model

The triple store is the source of truth: ontology, relationships, reasoning, ad-hoc
SPARQL. Keep it that way.

But SPARQL answers *aggregate* questions — counts per window, top values per column,
newest N, totals per author — by scanning. When a module's read path is aggregate-heavy
and runs on a schedule, give it a **projection**: a derived, columnar copy of the same
source data, shaped for those questions.

```
          ┌─────────────────┐
events ──►│  append-only    │──► triple store   (ontology, SPARQL, reasoning)
(raw)     │  log in object  │
          │  storage        │──► projection      (Parquet — counts, facets, pages)
          └─────────────────┘
```

Both are *derived views of the same log*. That is ordinary CQRS, and it is what makes the
projection safe: it is rebuildable from the log at any time, so it can never become a
second source of truth you are afraid to delete.

**Look for the log before building anything.** In the X module the ingest was already
persisting every API response as an immutable envelope in object storage — 4 GB of it,
with *more history than the graph exposed*. The projection needed no new ingestion
whatsoever. Check for this first; it is often already there.

---

## 5. The projection recipe

The replicable part. Six pieces, in this order:

**1. Pure parser** — `event dict → (fact rows, dimension rows)`. No services, no I/O, so
the semantics are directly testable. This is where you mirror whatever the authoritative
pipeline does; get it wrong and every number downstream is wrong.

**2. Incremental refresh** — list the log, skip anything at or before the watermark, parse
the rest, append. Watermark lives in `kv`. A refresh with nothing new must do **zero
writes** and return `{"skipped": True}`.

**3. Partition by month, not day.** Referenced/parent records are often years older than
the event that pulled them in — day partitions scatter a sparse tail across thousands of
near-empty files. Month keeps a 30-day window at two partitions. Sort each partition by
time and enable statistics so window filters skip row groups.

**4. Append a part file per run; never rewrite the partition.** An incremental run holds
only the new rows — overwriting deletes everything already projected. Compaction is a
separate, deliberate step.

**5. Dimensions are upserted, facts are appended.** Profiles/entities get one row per id
with the latest observation winning; events are an append-only log.

**6. Fail soft.** Missing projection, missing optional dependency, unreachable storage —
all fall back to the previous path. A projection is an optimisation, not a new hard
dependency. Always keep a `full=True` rebuild path: it is what makes schema changes and
suspected gaps recoverable.

---

## 6. Traps that have actually bitten

- **`ObjectStorageService.list_objects` is a directory listing, not recursive.** Nested
  prefixes come back with a trailing `/`. A naive call returns zero files and looks like
  "no data" rather than an error. Walk recursively.
- **`polars.DataFrame.write_parquet` has no "return bytes" mode** — write into an
  `io.BytesIO` and put those bytes.
- **Declare dependencies on the *deployed* project.** The Dagster container installs the
  outer project's extras, not the ABI monorepo's. Adding an extra only to
  `.abi/pyproject.toml` looks right and silently never ships.
- **`LOG_LEVEL` defaults to `WARNING`.** A service that does not set it drops every
  `logger.info`, so runs come back with zero captured stdout and you cannot see what
  happened. Set it in the compose service.
- **Two readings of one log drift.** If the authoritative pipeline changes what counts as
  a record, the parser must change with it. Pin the semantics with unit tests that state
  the rule in the test name.
- **Watermarks miss late arrivals.** A backfill writing events behind the watermark will
  be skipped. Document it and provide the full rebuild.

---

## 7. Verification discipline

Non-negotiable, in this order:

1. **Unit tests pin the semantics**, especially anywhere you mirror another component's
   rules. Fakes must reproduce the real API's *awkward* behaviour (e.g. non-recursive
   listing), or they will hide the bug that behaviour causes.
2. **Equivalence-check against the source of truth on real data.** Compare the new path
   and the old path over the same window, same instant. Explain every difference —
   staleness, richer history, or a bug. "Close enough" is not an explanation.
3. **Before/after on the same harness.** Stash your changes, run the baseline, restore,
   run again. Numbers from different harnesses are not comparable.
4. **Never write to production while evaluating.** Read real data, route writes to an
   in-memory store. You get the same numbers and touch nothing.
5. `make check` (ruff + mypy) and `make test` before opening the PR.

When you report results, separate *measured* from *estimated*, and name the thing that
made a measurement unrepresentative (a slow VPN link, a limited subset) rather than
quoting it as if it were production behaviour.

---

## 8. Architecture decisions get an ADR

New boundaries, cross-cutting config, a new dependency, a derived read model — write
`docs/adr/YYYYMMDD_topic.md` with **Status, Date, Context, Decision, Consequences**.
Put the measured numbers in Consequences, and list the costs and risks you accepted, not
only the wins. See `docs/adr/20260812_x_app_parquet_projection.md` for a worked example.

---

## 9. Module checklist

Copy into the new module's `AGENTS.md`:

```markdown
## Scalability contract

- [ ] Baseline measured and recorded (mean / median / p90 on real runs)
- [ ] Every scheduled read path is O(window) or O(delta) — no O(total) scans
- [ ] Checked: does an empty result cost the same as a full one?
- [ ] Incremental path does zero writes when nothing changed
- [ ] Full rebuild path exists and is documented

## Services

- [ ] Persistent state in `object_storage` — nothing important on local disk
- [ ] Watermarks / locks / run state in `kv`
- [ ] Source of truth in `triple_store`; derived views clearly labelled as derived
- [ ] Models via `model_registry` — no hardcoded model ids
- [ ] Credentials via `secret` — none inline
- [ ] Dependencies declared on the deployed project's extras

## Verification

- [ ] Unit tests pin semantics mirrored from other components
- [ ] Equivalence-checked against the source of truth on real data
- [ ] Before/after measured on the same harness
- [ ] `make check` and `make test` pass
- [ ] ADR written if this introduced an architectural boundary
```

---

## 10. Definition of done

A module change is done when: the numbers are measured rather than asserted, every
difference from the previous behaviour is explained, the failure path degrades to what
ran before, and someone else can rebuild the derived state from scratch using only what
is written down.
