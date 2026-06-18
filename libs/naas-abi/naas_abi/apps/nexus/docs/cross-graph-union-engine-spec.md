# Spec — Cross-graph query engine (union dataset)

Status: **proposed** · Owner: Composer/KG · Supersedes the single-`GRAPH ?g` scoping in
`apps/api/app/services/graph/query/compiler.py` · Related: AUDIT.md §7a/§7b.3.

## 1. Problem

The Composer query engine cannot join data that spans **named graphs**. In the PHASES
workspace the data is split: `Chunk` + its data properties live in
`http://ontology.naas.ai/graph/phases/papers`, while `ExtractedItem` and the
`extracted_from_chunk` relation live in `…/extractions`. A user on a `Chunk` grain who adds a
column reaching `ExtractedItem.extracted_text` (a cross-graph 2-hop) gets **blank cells**;
following into `ExtractedItem` from a `Chunk` grain returns **0 rows** unless the scope already
includes the other graph.

Verified against the live Fuseki:

```sparql
# Single-GRAPH (current engine) — returns 0
SELECT (COUNT(*) AS ?n) WHERE {
  VALUES ?g { <…/papers> <…/extractions> }
  GRAPH ?g { ?chunk a :Chunk . ?ext :extracted_from_chunk ?chunk . ?ext :extracted_text ?t }
}                                                                      # ?n = 0

# FROM-union (proposed) — returns the real rows
SELECT ?chunk ?t FROM <…/papers> FROM <…/extractions> WHERE {
  ?chunk a :Chunk . ?ext :extracted_from_chunk ?chunk . ?ext :extracted_text ?t
}                                                                      # rows ✓
```

## 2. Root cause

Every compiled query wraps its body in a single `VALUES ?g { …graphs… } GRAPH ?g { … }`. A
SPARQL solution binds `?g` to **one** graph, so **all** triple patterns in the block must match
**the same** graph. A row whose root is in graph A and whose column value is in graph B has no
single `?g` and is dropped. The scoping was chosen for workspace isolation (only query graphs
the workspace owns), not because the data is single-graph.

## 3. Proposed design — FROM-union dataset

Replace the `GRAPH ?g` wrapper with a SPARQL **dataset clause**: list each in-scope graph as
`FROM <g>`. The query's *default graph* then becomes the RDF merge (union) of those graphs, and
plain patterns (no `GRAPH`) match across all of them — so cross-graph joins resolve. Sub-SELECTs
inherit the outer query's dataset, so their patterns also match the union (they just drop their
own `GRAPH ?g` wrapper).

Isolation is preserved: `FROM` lists exactly `spec.graph_uris` (workspace-owned, already
ownership-checked in `GraphQueryService`). Nothing outside the spec's graphs is queried.

### Before / after (list mode page query)

```sparql
-- before
SELECT ?root ?col_text WHERE {
  VALUES ?g { <…/papers> <…/extractions> }
  GRAPH ?g { ?root a :Chunk . OPTIONAL { ?ext :extracted_from_chunk ?root . ?ext :extracted_text ?col_text } }
} ORDER BY ?root LIMIT 100

-- after
SELECT ?root ?col_text
FROM <…/papers> FROM <…/extractions>
WHERE { ?root a :Chunk . OPTIONAL { ?ext :extracted_from_chunk ?root . ?ext :extracted_text ?col_text } }
ORDER BY ?root LIMIT 100
```

## 4. Backend changes — `compiler.py`

All `GRAPH ?g { X }` sites collapse to `X`; the **outer** query of each compile path gains a
`FROM` clause built from `spec.graph_uris`. Inventory (current line refs):

| Site | Function | Change |
|------|----------|--------|
| 487–488 | `_graph_values(spec)` | Add sibling `_from_clause(spec) -> "FROM <g1>\nFROM <g2>\n…"`. Keep/relax `_graph_values` (only subqueries used it; they no longer need it). |
| 254–260 | `_agg_subquery` | Drop the `graphs` param + `VALUES ?g … GRAPH ?g { inner }` wrapper → emit `… WHERE { inner } GROUP BY …`. Subquery inherits the outer `FROM`. |
| 265, 302 | `_measure_fragment`, `_collapse_fragment` | Drop the now-unused `graphs` param threaded into `_agg_subquery`. |
| 610–616 | `compile_list` page | Insert `FROM` between SELECT and WHERE; remove the `VALUES ?g`/`GRAPH ?g` wrapper; inline `page_inner`. |
| 624–629 | `compile_list` count | Same; inline `count_inner` (note: it may embed measure subqueries — those are handled by the `_agg_subquery` change). |
| 767–773 | `compile_aggregate` page | Same. |
| 776–780 | `compile_aggregate` count `sub` | `sub` is itself a sub-SELECT inside `count_sparql`; drop its `GRAPH ?g`, add `FROM` to the **outer** `count_sparql`. |
| 855–858 | `compile_facet` | Same as list page. |

`_anchor_lines`, `_lower_path`, `_branch_block`, `_keyset_*`, the FILTER emitter and ORDER/LIMIT
emit plain patterns / outer clauses already — **no change**; they simply now resolve against the
union default graph.

Helper sketch:

```python
def _from_clause(spec) -> str:
    return "".join(f"FROM {sparql_iri(g)}\n" for g in spec.graph_uris)
# outer query:  f"SELECT {proj} {_from_clause(spec)}WHERE {{ {inner} }} ORDER BY … LIMIT …"
# subquery:     f"OPTIONAL {{ SELECT {start} ({agg} AS {raw}) WHERE {{ {inner} }} GROUP BY {start} }}"
```

## 5. Frontend changes — graph scope

For a cross-graph join the spec must actually *list* the graphs involved. Today `graphUris` is
usually a single graph (the grain's), so a cross-graph column would `FROM` only one graph and
still miss the other. **Make the Composer span all of the workspace's data graphs** so any
class/relation is reachable:

- `apps/web/.../use-explore.ts` / `explore-state.ts`: when graphs load (or a grain is set),
  default `graphUris` to **all** graph URIs from `/api/graph/list` (the workspace's data graphs;
  system graphs schema/nexus are already excluded server-side). Keep the graph picker
  (`toggleGraph`) as a **narrowing** control, not the source of truth.
- This makes the `follow`-time graph widening (already shipped) and the per-grain
  `discoverColumnsFor` widening redundant but harmless; can be simplified later.
- Saved views persist `spec.graph_uris`; existing single-graph views keep working (union of one
  graph == that graph). Optionally migrate-on-load to all data graphs.

Alternative (more conservative, not recommended): keep single-graph default and widen
`graphUris` whenever a cross-graph column/relation is added — more code paths, easy to miss one.

## 6. Semantics & correctness

- **Same-graph parity:** the union ⊇ each graph, and a single-graph view's triples all live in
  one graph ⊆ union → identical result set. No regression for existing views.
- **Duplicate triples across graphs:** RDF merge dedupes identical triples; `COUNT(DISTINCT
  ?root)` and keyset pagination are unaffected. A predicate asserted with *different* values in
  two graphs yields multiple values → handled by the existing to-many `collapse` (concat/first).
- **Isolation:** `FROM` enumerates only `spec.graph_uris` (ownership-checked). Equivalent to the
  old scoping; no new leakage. The ontology/schema graph is **not** added (data queries only).
- **Counts/pages consistency:** page and count share the same `inner`/`FROM`; the existing
  invariant (page rows ⊆ count) holds because both move to the union identically.

## 7. Risks & edge cases

1. **Performance:** union scans across graphs may plan differently than `GRAPH ?g`. Validate on
   the real dataset (papers≈110k + extractions≈127k triples) — page, count, facet, aggregate.
2. **Subquery dataset inheritance:** relies on sub-SELECTs inheriting the outer `FROM` (SPARQL
   1.1 §13). True for Fuseki/Oxigraph; add an integration test to lock it.
3. **Stores without a configured default graph:** `FROM` *defines* the default graph for the
   query, so this is robust on Fuseki/Oxigraph regardless of server default-graph config.
4. **`include_sparql` snapshots / count cache keys:** the emitted SPARQL text changes — bump/no-op
   any cached `resolved_sparql` and re-check `count_key` inputs (graph set still feeds the key).
5. **Mixed-graph multi-values** could surprise users (a value that only exists in one graph now
   appears). Acceptable / arguably correct; document in release notes.

## 8. Test plan

- **Unit (`compiler_test.py`):** update expected SPARQL to the `FROM …` shape; assert no
  `GRAPH ?g`/`VALUES ?g` remains; assert one `FROM` per `spec.graph_uris`; assert subqueries have
  no `GRAPH`. Cover list/aggregate/facet/measure/collapse/keyset.
- **Integration (`compiler_integration_test.py`, live store):** the cross-graph join
  (`chunk → extracted_text`) returns rows; a same-graph view returns identical rows to the old
  engine (golden compare); counts match page totals.
- **Discovery already covered** (`column_discovery_test.py`) — unchanged by this spec.
- **Manual / Fuseki:** the three queries in §1; follow Chunk→ExtractedItem and add a cross-graph
  column, confirm populated cells.

## 9. Rollout

1. Land compiler change behind the existing test suite (pure, no schema/migration).
2. Land frontend all-data-graphs scoping.
3. Verify against live Fuseki; spot-check existing saved views for parity.
4. Update AUDIT.md §7b.3 ("named-graph scoping") to document the union-dataset model.

## 10. Out of scope

- Fixing the broken `has_extracted_item` relation (points at the `abi/unknown` sentinel — a
  data/extraction-pipeline bug, not an engine bug).
- Per-graph provenance columns (which graph a value came from) — possible later via `GRAPH ?g`
  *binding* a projected var, independent of this change.
