# Cross-graph queries — design & decision record

Status: **decided** · Engine: **`GRAPH ?g` retained** (a `FROM`-union rewrite was evaluated and
rejected — see §5) · Related: AUDIT.md §7a/§7b.3.

## 1. The problem

The PHASES workspace splits data across named graphs: `Chunk` + its data properties live in
`…/papers`, while `ExtractedItem` and the `extracted_from_chunk` relation live in `…/extractions`.
A user on a `Chunk` grain who follows/​adds `← extracted_from_chunk → ExtractedItem.extracted_text`
saw nothing.

## 2. Root cause — it was never the query engine

Three things must hold for a cross-graph column to work:

1. **Discovery** — the relation is visible in the picker / Follow menu.
2. **Scope** — the far graph is in `spec.graph_uris` (what the query may touch).
3. **Engine** — the compiled SPARQL resolves the patterns.

Before this work it failed at **1 and 2**, not 3:

- *Discovery*: the old column-discovery query looked for the relation triple only in the grain's
  graph, so `extracted_from_chunk` (asserted in `extractions`) never appeared.
- *Scope*: the grain was anchored in `papers` only, so `spec.graph_uris = [papers]`; `extractions`
  was never in scope.

## 3. The fixes (shipped, engine-independent)

- **Discovery decoupling** (`column_discovery.py`): resolve the relation triple and the related
  type in their own `GRAPH` clauses spanning the workspace graphs → the cross-graph relation +
  its target class (tagged with `TargetClass.graph`) are discoverable.
- **Graph scoping** — *Follow* adds the followed class's graph; *Add column* (expanded relation)
  adds the relation's target-class graph. Both union into `state.graphUris → spec.graph_uris`.
  Scope only grows (never auto-shrinks; the graph picker is the manual narrow control) and
  round-trips through `stateFromSpec` on save/load.

## 4. Why `GRAPH ?g` already handles it

With the service's `single_valued_predicates` empty, **every path column compiles to a collapse
subquery**, e.g.:

```sparql
OPTIONAL { SELECT ?root (GROUP_CONCAT(?v) AS ?col_ex) WHERE {
  VALUES ?g { <papers> <extractions> }
  GRAPH ?g { ?ex <extracted_from_chunk> ?root . ?ex <extracted_text> ?v }
} GROUP BY ?root }
```

Both inner patterns live in the **same** graph (`extractions`), so a single `?g = extractions`
resolves them — no cross-graph *join* is needed inside the block. The only requirement is that
`extractions` be in `spec.graph_uris` (fix §3). Verified on the live store: the `GRAPH ?g` engine
returns the correct cross-graph rows.

This is plain, portable SPARQL 1.1 (`VALUES ?g` + `GRAPH ?g`) hitting TDB2's quad index
`(G,S,P,O)` directly. It needs **neither** `FROM` **nor** Fuseki's `tdb2:unionDefaultGraph` server
setting.

## 5. `FROM`-union: evaluated and rejected

We prototyped replacing `VALUES ?g { … } GRAPH ?g { … }` with a `FROM <g1> FROM <g2>` dataset
clause (default graph = RDF-merge → patterns join across graphs). It is correct, but **3.2× slower**
on the cross-graph page on the real ~240k-triple store:

| query | `GRAPH ?g` | `FROM`-union |
|---|---|---|
| page · 1 graph | 144 ms | 143 ms |
| count · 1 graph | 20 ms | 28 ms |
| facet · 1 graph | 72 ms | 80 ms |
| **page · cross-graph** | **212 ms** | **686 ms** |

**Why (root cause of the delay):** decomposition shows the cost is the `GROUP_CONCAT` subquery, and
it is the `FROM` *mechanism*, not the multi-graph union. Even a **single-graph** subquery is ~2×
slower as `FROM <E>` (931 ms) than `GRAPH <E>` (429 ms): TDB2 serves a named graph straight from
its quad index, but must **dynamically materialize** the `FROM`-defined default graph for every
pattern. Light queries (single-graph page/count/facet) barely move; the aggregation-heavy
cross-graph page compounds the per-pattern penalty into ~3×.

→ **Decision: keep `GRAPH ?g`.** It is faster and already covers the real cross-graph columns.

## 6. Known limitations / future work

- **True multi-hop cross-graph join** — a single path whose hops live in *different* graphs (rare;
  not the `chunk → extracted_text` shape, where both far patterns are in `extractions`). `GRAPH ?g`
  within one block can't join across graphs. The fast fix, if ever needed, is **per-pattern
  `GRAPH ?gN` variables** (each pattern still uses the named-graph index, but different patterns
  bind different graphs) — *not* `FROM`, and not the union-default-graph server config.
- **Aggregate-mode** group-by dimensions / measures and ad-hoc **branch filters** crossing graphs
  are not auto-scoped yet — tick the graph in the picker. A follow-up can mirror the
  follow/​add-column scoping.

## 7. Out of scope

- The broken `has_extracted_item` relation (points at the `abi/unknown` sentinel — a
  data/extraction-pipeline bug, not an engine bug).
- Per-graph provenance columns (which graph a value came from).
