# Nexus Knowledge Graph — Explore Rework: Audit & Plan

> Living document. We update this as we work. It captures the current state of the
> Knowledge Graph **Explore** section, why it doesn't scale, the confirmed product
> requirements, and the target design.

**Status:** 🟡 Audit complete — design not yet started
**Scope of this effort:** the **Explore** section first (Network & Individuals come later).
**Last updated:** 2026-06-16

---

## 0. Confirmed requirements & decisions

These were confirmed with the product owner and drive the whole design:

1. **Scale is the headline constraint.** We must handle graphs with **millions of triples**.
   A brand-new project already has 100k+ triples and will keep growing. → **All
   filtering, search, sorting, pagination, and faceting must run on the backend.**
   Client-side filtering over a loaded page is not acceptable.
2. **Excel-like UX stays.** The spreadsheet experience (columns, per-column filters,
   sort, select rows) is the experience we want — but every operation must query the
   backend, not a loaded slice.
3. **Sharing = workspace-wide (for now).** Everyone in the workspace can see the views.
   No per-user / per-role / link sharing yet. (Keep the model simple; don't build
   personal-only visibility complexity.)
4. **Views are organized like a filesystem.** Users need a **folder hierarchy** to
   organize saved views.
5. **A view always re-runs its query → live data.** Opening a view re-executes against
   the current graph. **Snapshot/pinning is a later phase**: store the query result in
   the filesystem/object storage and have the backend serve that materialized result.
6. **End goal:** views answer questions and power curated experiences — specific
   audiences open a view and immediately see the information they need.
7. **Counts:** do a **real `COUNT`**, but **cache it with a ~10-minute TTL** (keyed by
   graph + filter signature) so it doesn't re-run on every interaction.
8. **Backends:** **production = Apache Jena (Fuseki/TDB2)**; **Oxigraph is local-dev
   only** (smaller graphs). → Queries must run on **both**, and the scale story is
   Jena's. Jena can have a **Lucene full-text index** (`text:query`) for fast label
   search — but only if the Fuseki dataset is configured with `jena-text` (a deployment
   concern). Oxigraph has no FTS, so search there falls back to `CONTAINS`.
9. **Folders = a path string on the view** (e.g. `Sales/Leads/Active`). Accepted
   tradeoff: **renaming a folder = a prefix-rewrite** across all views under that path
   (do it as one transaction). Revisit a folders-table if this gets painful.
10. **Every column must be filterable (true Excel behavior)** — properties *and*
    relation-derived columns, all server-side. Additionally, a view must be able to
    **anchor on a specific instance OR a class/type**, not just list a class. Driving
    use case: a view focused on one user that shows *what they do on the platform*
    (e.g. number of chats + messages) — i.e. **instance-anchored traversal +
    aggregation**, which is bigger than a flat instance table.

---

## 1. Architecture at a glance

- **Monorepo:** `libs/naas-abi/naas_abi/apps/nexus` — a Turborepo with:
  - `apps/web` — Next.js frontend (the UI).
  - `apps/api` — FastAPI backend.
- **Data store:** RDF **triple store**, queried with **raw SPARQL strings**. The store
  is pluggable (`naas_abi_core.services.triple_store`): Oxigraph (embedded + HTTP
  server), AWS Neptune, Apache Jena TDB2, Filesystem, ObjectStorage.
  - **Production = Apache Jena via Fuseki** (HTTP `/query` + `/update`,
    `ApacheJenaTDB2.py`). **Oxigraph is local-dev only** (`config.yaml:184`,
    `http://127.0.0.1:7878`). `config.local.yaml` also exposes an `fs` (in-memory)
    option that will **not** scale — never use it at this scale.
  - **Portability constraint:** every query we write must execute on **both** Jena
    (prod) and Oxigraph (dev). Jena-specific extensions (`text:query`) are not portable
    → search needs a backend-capability branch (Lucene `text:query` on Jena, `CONTAINS`
    fallback on Oxigraph) or a shared portable form. The query layer should hide this.
  - **Scale notes:** `OFFSET` paging re-scans from row 0 on both → prefer **keyset/
    cursor** pagination. Fast full-text needs Jena's **`jena-text` Lucene index**, which
    must be enabled in the **Fuseki dataset config** (deployment dependency, not in this
    repo).
- **Per-workspace isolation:** each workspace's data lives in named graphs; schema/
  ontology live in protected graphs (`…/graph/schema`, `…/graph/nexus`).

**Three graph sections** (`apps/web/src/components/graph/graph-section-nav.tsx`):
**Network**, **Individuals**, **Explore** (+ Import/Export utilities). We start with
**Explore**.

---

## 2. How "Explore" works today

**Entry point:** `apps/web/src/app/workspace/[workspaceId]/graph/explore/page.tsx`
— a single **4,147-line** file containing ~20 components, all data fetching, the tables,
the SPARQL-step recorder, and the import pane.

### Data flow

```
loadGraphs       GET  /api/graph/list                        → graphs in workspace
classes          GET  /api/graph/discovery/classes           → classes + counts   [cached 5 min]
 └ user ticks a class OR submits a search (≥2 chars, on Enter)   ← "filter-first" gate
properties       POST /api/graph/discovery/properties         → datatype props for selected classes
instances        POST /api/graph/discovery/instances          → rows (server-filtered: class + label search)
 └ enrich=True ALSO computes per row: properties, object_properties (in+out),
   domain_relations_count, range_relations_count, properties_count, bfo_bucket
relation-types   POST /api/graph/discovery/relation-types      → relation types for the working set
relations        POST /api/graph/discovery/relations           → domain/range relation rows
```

Backend routes: `apps/api/app/services/graph/adapters/primary/graph__primary_adapter__FastAPI.py`
Service/query builders: `apps/api/app/services/graph/service.py`

### What runs where today

- **Server-side (SPARQL):** class filter (`VALUES ?cls`), label search (`CONTAINS`),
  a `LIMIT`/`OFFSET` cap. Default page **500**, hard max **5,000** instances.
- **Client-side (in the browser, over the loaded page only):** BFO-bucket filter,
  per-column Excel filters, sorting, column facet value lists, client pagination
  (slicing), and the network canvas.
- **Network canvas is a 20-node / 20-edge preview** (`GRAPH_MAX_NODES/EDGES = 20`);
  the Individuals inline view only renders at ≤ 20 rows.

---

## 3. What works well (keep / build on)

- ✅ **Instance list is already filter-first**, not "load everything": class + label
  search are pushed into SPARQL; instances don't load until you tick a class or search
  (`explore/page.tsx:516`).
- ✅ **PowerQuery-style query model already exists:** `apps/web/src/lib/sparql-steps.ts`
  turns each user action (search → class filter → property filter → instance/relation
  select) into an executable SPARQL step. **This is the right backbone for "a view = a
  query."**
- ✅ **Views already persist server-side** in SQL table `graph_views` with a JSON `state`
  column (`apps/api/app/services/view/service.py`, `apps/api/app/models.py:491`).

---

## 4. Findings — Performance (why it's slow)

| # | Finding | Location |
|---|---------|----------|
| P1 | **Eager enrichment fan-out on every instance fetch.** `enrich=True` runs the main query **plus 5 query families** (property values, object-props in+out, domain counts, range counts, data-prop counts), each chunked by 500 subjects, for the whole page — and computes columns most users never look at. | `service.py` `_discover_instances_sync` |
| P2 | **No real pagination — "Load more" is O(n²).** It **doubles the `limit` and refetches from row 0**, re-enriching everything already loaded (500→1k→2k→4k→5k). No cursor/offset surfaced to the user. | `explore/page.tsx:1316` |
| P3 | **Relations scan the entire working set.** With no rows ticked, relation scope = **all loaded instances**; `/relations` chunks by 500 and runs domain+range queries per chunk (default limit 5k, **max 50k**). Thousands of instances → hundreds of queries. | `explore/page.tsx:629`, `service.py` |
| P4 | **N+1 label / BFO resolution.** `_get_ontology_label` and `_get_bfo_parent_for_class` are called per class / property / relation / row. Cached 1 day, but the cold path is many sequential round-trips to the schema graph. | `service.py` (many call sites) |
| P5 | **Filtering/sorting/faceting are client-side over the loaded page.** `uniqueValuesByColumn` iterates all loaded instances × all columns each render; `filteredInstances` re-filters+sorts the whole set on every keystroke. | `explore/page.tsx:586`, `:3254` |
| P6 | **Hard 5,000-row ceiling breaks the "Excel" promise.** Column filters/sort/buckets only search the rows that happened to load. Beyond the cap, data is invisible. At millions of triples this is fatal. | `explore/page.tsx` `INSTANCE_MAX_LIMIT` |
| P7 | **Only `/classes` is function-cached (5 min).** instances / properties / relations are recomputed on every request. | `service.py` |
| P8 | **No row virtualization** (partly mitigated by client page-slicing, but facet/filter passes still touch the full in-memory set). | `explore/page.tsx` `InstancesTable` |

**Root cause:** the spreadsheet UX implies "filter the whole table," but the architecture
only ever filters a truncated client page. This cannot scale to millions of triples.

---

## 5. Findings — Architecture & maintainability

- **A1 — One 4,147-line component.** Deeply interdependent `useEffect`s; the SPARQL-step
  recorder alone is 7 chained effects (`explore/page.tsx:965-1207`) with many
  `eslint-disable exhaustive-deps`. Fragile and racey.
- **A2 — Two parallel, partly-dead state models.** The zustand store
  `apps/web/src/stores/knowledge-graph.ts` still holds `nodes/edges`, a `runQuery`
  that's a `// TODO` stub doing client-side substring matching (`:438`), and a
  deprecated aviation demo — while the real flow uses local component state + the
  discovery API. Confusing source of truth; should be unified/retired.

---

## 6. Findings — Views system vs. the end goal

| Need | Today | Gap |
|------|-------|-----|
| Persist a view | ✅ `graph_views` table, JSON `state` | — |
| **Edit / rename** a view | ❌ only `create` + `delete` (`view.py:217-249`) | Edit = delete+recreate → new id, lost identity |
| View = a stable, re-runnable query | ⚠️ stores **UI filter state incl. baked-in selected instance URIs** (`DiscoveryViewState`) | Brittle: depends on client re-deriving the query; pinned URIs go stale as data changes |
| Backend executes the saved query | ❌ discovery endpoints rebuild queries from params; saved SPARQL isn't run server-side | "The view is the query" isn't the contract yet |
| **Folder hierarchy** for views | ❌ flat list | Need a path/folder model |
| Workspace sharing | ✅ `visibility` already supports `workspace` | Personal-only complexity can be dropped for now |
| Snapshot a result | ❌ | Later phase: materialize result to filesystem/object storage, serve it |

---

## 7. Target design (high level — to be detailed next)

> Direction only. API contracts and data-model changes get their own sections once we
> start designing.

1. **Backend-driven, paginated, filterable instance endpoint.** One query endpoint that
   accepts: `graph_uri`, **anchor** (class/type *or* specific instance(s) — see #8),
   `search`, **per-column filters with operators**, **sort (column + dir)**, and
   **keyset/cursor pagination** (not OFFSET). Returns rows + page info + **total count**
   served from a **~10-min TTL cache** keyed by (graph + filter signature).
2. **Facets endpoint.** Distinct values + counts for a given column under the *current*
   filter set, so the Excel column-filter dropdowns reflect the **whole** result, not a
   loaded page. (Facet enumeration itself can be capped/cached.)
3. **Lazy enrichment.** List returns cheap columns fast; relation counts / object
   properties / heavy columns load on demand (column expand or row inspect). Cache per
   endpoint like `/classes` already does.
4. **Portable search layer.** A query-builder seam that emits Jena `text:query` (Lucene)
   when available and `CONTAINS` on Oxigraph — callers don't branch. Depends on the
   Fuseki `jena-text` index being enabled in prod (deployment task).
5. **Every column filterable + operators.** Define a filter grammar over columns:
   `equals`, `contains`, `in (set)`, `range` (numbers/dates), `is empty`. Applies to
   datatype properties *and* relation-derived columns, all pushed to SPARQL.
6. **Instance/type anchoring + traversal.** The query model must express "anchor on this
   class" **or** "anchor on this instance and follow relations," including simple
   **aggregations** (e.g. count chats/messages for a user). This is the part that goes
   beyond today's flat table — likely needs a small structured query spec the backend
   compiles to SPARQL (the existing `sparql-steps` model is the seed).
7. **Views = first-class, server-executable, parameterized saved queries.** Persist the
   canonical query spec (not baked instance URIs); add **update/rename**; stable id;
   **workspace visibility**; **folder path** with prefix-rewrite rename; always re-run
   live. Snapshot (materialize result to filesystem/object storage) is a later phase.
8. **Decompose `explore/page.tsx`** into focused components + a single state model;
   retire the dead zustand graph state and the `runQuery` stub.
9. **Decide the result-set graph view** — keep the 20-node preview, or render the actual
   filtered result with virtualization/clustering.

---

## 7a. Step (a) — Canonical View Query Spec (design)

The **ViewQuerySpec** is the single, serializable definition of an Explore view. It
replaces today's ad-hoc `DiscoveryViewState` (which bakes in instance URIs). It **is**
the saved view's `state`, and the backend compiles it to **portable SPARQL** (Jena +
Oxigraph). The human-readable SPARQL preview is *generated from the spec* — one source
of truth (today's `sparql-steps` becomes a UI builder that emits a spec, not a separate
query path).

### Mental model: graph → table

- A view is a **table**. **One row per "root" entity.** **Each column is a projection**
  reachable from the root — a direct property, a related entity (1+ hops away), or an
  **aggregate/measure** over a traversal.
- **Anchor** decides the rows: a **class** (one row per instance of it) *or* a fixed set
  of **instances** (one row each). Filtering to a single instance is just an `instances`
  anchor (or an `is` filter on the root) → enables single-entity "dashboard" views.
- **Multihop** is first-class: a `Path` is a sequence of hops; measures aggregate over
  the set of nodes a path reaches (e.g. a user → chats → messages).

### Authoring model: a navigation pipeline (root is inferred, not asked)

Users don't pick a "root" abstractly. They **navigate**:

> **search → add filter → follow a relation → add filter → … (rinse & repeat)**

`follow a relation` is what changes the grain: Users → follow `hasChat` → rows are now
Chats → follow `hasMessage` → rows are now Messages. So **the root is *inferred* = the
pipeline's current terminal focus.** The UI just *reflects* it ("Now viewing: Messages
(1,240)"); it never asks "what is one row?". Earlier filters don't vanish — they become
**constraints on the final root via the inverse path** (message→chat→user `is Alice`).
Each `follow` is an explicit, typed choice (which relation + which **direction**), so
inference is safe — there's no guessing about the grain.

**Two layers, one truth:**
- **Pipeline = the authoring model AND the persisted source of truth** for a saved view
  (so "come back and filter again" = edit the ordered steps). Mirrors the existing
  `sparql-steps` model.
- **ViewQuerySpec (below) = the compiled form** the pipeline lowers to — `root` =
  terminal focus, upstream stages → filters, presentation → columns/sort. It's what
  executes, counts, and facets.

**Hard execution rule:** the pipeline is a *builder*. It MUST compile to **one SPARQL
query** over the final root — **never** execute stage-by-stage materializing
intermediate sets (that is the load-everything trap again at millions of triples).

### Branching (v1) — two kinds of "follow"

Branching IS supported in v1. The key is that **`follow` has two modes**:

- **Follow-to-navigate** → *changes the grain*; rows become the target type.
- **Follow-to-constrain (a branch)** → *stays on the current grain*; adds a "must have a
  related thing matching …" requirement (an EXISTS-style mini-traversal that returns as
  a **filter**, not a grain move).

So a branched query keeps a **single grain** while constraining it along several
independent paths, combined with `AND` / `OR` / `NOT`:

> *Users · age > 30 · **require** hasChat→topic = X · **require** authored→doc→topic = Y ·
> then navigate hasChat to view the chats.*

This is exactly the `FilterNode` boolean tree (each condition carries its own `Path`).
It compiles to one query — `FILTER EXISTS { …X… } && EXISTS { …Y… }`,
`NOT EXISTS { … }` for negation ("users with no open tickets"), `UNION` for `or`.
**Branching as filters (case 1) and as projections (columns from different paths, case 2)
are both v1.**

### Two modes: list & aggregate (group-by / pivot)

A view runs in one of two modes:

- **List mode** (default) — `mode: 'list'`. Grain = a single **root** entity; one row per
  entity; columns are attributes/measures/branches. (§ the `ViewQuerySpec` above.)
- **Aggregate mode** — `mode: 'aggregate'`. Grain = a **tuple of group-by dimensions**;
  one row per distinct combination; columns are the dimensions + **measures**. This is
  the Excel-PivotTable shape (group-by fields = rows, measures = values).

```ts
interface AggregateSpec {
  mode: 'aggregate';
  graphUris: string[];
  fact: RootAnchor;            // the thing being aggregated/counted (e.g. ExtractedItem)
  groupBy: Dimension[];        // row = distinct combination of these
  measures: Measure[];         // count / sum / avg / … over the fact or a path
  filters?: FilterNode; sort?: SortKey[]; page?: { limit: number; cursor?: string };
}
interface Dimension {
  id: string; label?: string;
  path?: Path;                 // fact → dimension node ([] = the fact itself)
  show: { property: string } | 'node-label' | 'node-uri';
}
interface Measure { id: string; label: string; fn: AggFn; of?: AggTarget; path?: Path; }
```

**Key scope rule:** group-by dimensions must be reachable from a **common fact** (so each
fact contributes one well-defined tuple). That's a cheap `GROUP BY` — **v1**. The thing
that stays **v2** is the **cartesian join of unrelated entity sets** (no common fact) and
**heterogeneous-type result rows**.

### Worked examples against the PHASES `documents.owl` ontology

Hierarchy: `PDFPaperFile —has_chunks→ Chunk —has_extracted_item→ ExtractedItem
—extracted_by→ Extraction`.

**(A) List + branch — "extracted items with 'solitude' AND 'sport', paper path contains
'pubmed'"** — grain = `ExtractedItem`; two `contains` filters on `extracted_text`; one
**branch** up `extracted_from_chunk → chunk_of → PDFPaperFile.path contains 'pubmed'`.
Compiles to a single query (up-path is to-one per SHACL, so a plain join, no EXISTS
needed). On Jena the word matches use Lucene `text:query`; on Oxigraph `CONTAINS`.

```sparql
SELECT ?root ?text ?paperPath WHERE {
  VALUES ?g { <…/graph/ws> } GRAPH ?g {
    ?root a doc:ExtractedItem ; doc:extracted_text ?text .
    FILTER(CONTAINS(LCASE(?text),"solitude")) FILTER(CONTAINS(LCASE(?text),"sport"))
    ?root doc:extracted_from_chunk ?c . ?c doc:chunk_of ?p . ?p doc:path ?paperPath .
    FILTER(CONTAINS(LCASE(STR(?paperPath)),"pubmed")) } } ORDER BY ?root LIMIT 100
```

**(B) Aggregate / pivot — "per paper, count extracted items grouped by Extraction"** —
`mode: aggregate`; fact = `ExtractedItem`; groupBy = [paper (via
`extracted_from_chunk/chunk_of`, show `path`), extraction (via `extracted_by`, show
`pipeline_name`)]; measure = `count`. Long-format (one row per paper×extraction) is v1; a
**wide** pivot (extractions as dynamic columns) is v2 (needs a value-enumeration pre-pass).

```sparql
SELECT ?paperPath ?pipeline (COUNT(DISTINCT ?item) AS ?items) WHERE {
  VALUES ?g { <…/graph/ws> } GRAPH ?g {
    ?item a doc:ExtractedItem ; doc:extracted_from_chunk ?c ; doc:extracted_by ?x .
    ?c doc:chunk_of ?p . ?p doc:path ?paperPath .
    OPTIONAL { ?x doc:pipeline_name ?pipeline } } }
GROUP BY ?paperPath ?pipeline ORDER BY ?paperPath LIMIT 100
```

**(C) Negation — "papers with NO extracted items from model 'gpt-5-mini'"** — grain =
`PDFPaperFile`; a `not` group around a downward branch `has_chunks → has_extracted_item →
extracted_by` requiring `model_name = "gpt-5-mini"`. To-many path ⇒ `NOT EXISTS`.

```sparql
SELECT ?root ?path WHERE {
  VALUES ?g { <…/graph/ws> } GRAPH ?g {
    ?root a doc:PDFPaperFile . OPTIONAL { ?root doc:path ?path }
    FILTER NOT EXISTS {
      ?root doc:has_chunks ?chunk . ?chunk doc:has_extracted_item ?item .
      ?item doc:extracted_by ?x . ?x doc:model_name "gpt-5-mini" . } } }
ORDER BY ?root LIMIT 100
```

### Filter semantics (decided from examples A–C)

- **To-many path filters are existential by default**: "has a related thing where …" →
  `EXISTS`; `not` → `NOT EXISTS`. (The *universal* "all related things …" reading is a
  separate v2 operator.) This is why a to-many branch compiles to `EXISTS`, never a join
  (a join would multiply rows / corrupt counts).
- **Negation includes the vacuous case**: "no items from gpt-5-mini" also returns papers
  with zero items. "Has items but none from gpt-5-mini" = `EXISTS{any} AND NOT
  EXISTS{gpt-5-mini}` — composable from the same primitives.
- **Anchor on the smaller set for negation/EXISTS**: evaluate `NOT EXISTS` over the small
  outer set (papers), probing the indexed large set (items) — not the reverse. Builder
  should hint/guard this.

### Schema

```ts
interface ViewQuerySpec {
  version: 1;
  graphUris: string[];          // named graphs to query (union)
  root: RootAnchor;             // what each ROW is
  columns: Column[];            // what each COLUMN shows (dimensions + measures)
  filters?: FilterNode;         // row constraints (boolean tree); omitted = none
  sort?: SortKey[];             // ordered sort keys
  page?: { limit: number; cursor?: string };  // keyset pagination
}

// ── Rows ──────────────────────────────────────────────────────────────────
type RootAnchor =
  | { kind: 'class';     classUris: string[] }      // union of classes
  | { kind: 'instances'; instanceUris: string[] };  // fixed set

// ── Multihop path: root → … → target node ────────────────────────────────
interface Hop {
  predicate: string;                     // predicate IRI
  direction: 'out' | 'in';               // ?from p ?to  |  ?to p ?from
  quantifier?: 'one' | 'plus' | 'star';  // one (default) | p+ | p*  (transitive)
  targetClassUris?: string[];            // optional rdf:type constraint on reached node
}
type Path = Hop[];                        // [] = the root itself

// ── Columns: dimensions (a value) and measures (an aggregate) ─────────────
interface Column {
  id: string;                            // stable; referenced by filters/sort
  label: string;
  datatype: 'string' | 'number' | 'date' | 'boolean' | 'iri';
  source: ColumnSource;
  visible?: boolean;                     // default true
}
type ColumnSource =
  | { kind: 'property';  path?: Path; predicate: string; collapse?: Collapse } // datatype value
  | { kind: 'node';      path: Path; show: 'label' | 'uri'; collapse?: Collapse } // related entity
  | { kind: 'aggregate'; path: Path; fn: AggFn; of?: AggTarget };              // measure

type AggFn = 'count' | 'countDistinct' | 'sum' | 'avg' | 'min' | 'max';
type AggTarget =
  | { kind: 'node' }                              // aggregate reached entities
  | { kind: 'property'; predicate: string };      // aggregate a value on reached node

// One row per root: a to-MANY dimension MUST collapse to one cell.
type Collapse = 'first' | 'concat' | 'count' | 'min' | 'max';

// ── Filters: boolean tree (AND/OR/NOT); EVERY column filterable; branches = paths ──
type FilterNode =
  | { op: 'and' | 'or'; children: FilterNode[] }
  | { op: 'not'; child: FilterNode }              // negation → NOT EXISTS
  | FilterCondition;
interface FilterCondition {
  // A condition can target a declared column OR an inline source whose `path` is a
  // BRANCH (follow-to-constrain): "the root must have a related thing matching this".
  target: { columnId: string } | { source: ColumnSource };
  operator: Operator;
  value?: unknown;   // scalar | [lo,hi] | string[]  — shape depends on operator
}
type Operator =
  | 'eq' | 'neq' | 'contains' | 'notContains' | 'startsWith' | 'endsWith' // string
  | 'lt' | 'lte' | 'gt' | 'gte' | 'between'                               // number/date
  | 'in' | 'notIn' | 'isEmpty' | 'isNotEmpty'                             // sets/presence
  | 'is' | 'isNot' | 'hasRelation';                                       // iri/relation

interface SortKey { columnId: string; dir: 'asc' | 'desc' }
```

### The root IS the grain ("what is one row?")

The root is not a restriction — it's the **grain selector**. Pick the root = the thing
you want one row per. Different questions over the same `user -< chat -< message` data:

| You want… | root | message column |
|-----------|------|----------------|
| All **users** + their message counts | `class: User` | `count` measure (multihop) |
| All **messages** of a user (one row each) | `class: Message`, filtered `message→chat→user is <alice>` | `property` on root |

So "show me all messages of Alice" = root **Message**, with a filter that traverses *up*
(`hasMessage` `in`, then `hasChat` `in`) to `user is <alice>`, and columns that read the
message's own properties + the parent chat. Traversing **up** a hierarchy is to-one, so
nothing collapses. **The user reaches this grain by navigating** (start on Alice → follow
`hasChat` → follow `hasMessage`), not by answering "what is one row?" — the root is the
pipeline's terminal focus (see *Authoring model* above).

### The one-row-per-root rule (why `collapse` exists)

The rule only bites when a column fans out **below** the chosen grain. RDF is many-valued
(a user has many chats), so with root = `User`, a column "chat titles" has many values
per row. To keep **exactly one row per root**:
- **Dimension over a to-one path** → projects directly (OPTIONAL). *(message→chat→user)*
- **Dimension over a to-many path** → MUST set `collapse` (concat / count / first / …),
  compiled as a per-root sub-aggregate. *(user→chats shown on the user row)*
- **Measures** are inherently per-root aggregates.

It never stops you from choosing the finer grain as the root — it stops *one* row from
silently exploding into many.

### Column discovery & type inference

Two distinct concerns, both resolved as "**ontology + data**":

1. **Which columns/relations are offered** for an anchored class = **union of**
   (a) properties/relations the **ontology** declares for that class (incl. inherited),
   and (b) predicates that **actually appear** on its instances. Ontology gives
   completeness — a *valid but empty* relation still shows up (not hidden = not
   confusing); data presence catches ad-hoc predicates the ontology omits. Tag each
   suggestion `ontology | data | both` (+ instance count) so the UI can hint "0 in data".
2. **A column's `datatype`** (drives the filter operators) = **ontology `rdfs:range`
   first**, with a **sampled-values fallback** when the range is missing/generic
   (`rdfs:Literal`) — real ontologies are loose here. Cache the inferred type.

### Worked examples

**(1) "All users with their chat & message counts"** — multihop measures:
```jsonc
{
  "version": 1, "graphUris": ["…/graph/<ws>"],
  "root": { "kind": "class", "classUris": ["…/User"] },
  "columns": [
    { "id": "name",     "label": "User",     "datatype": "string",
      "source": { "kind": "property", "predicate": "…/rdfs#label" } },
    { "id": "chats",    "label": "Chats",    "datatype": "number",
      "source": { "kind": "aggregate", "fn": "count",
                  "path": [ { "predicate": "…/hasChat", "direction": "out" } ],
                  "of": { "kind": "node" } } },
    { "id": "messages", "label": "Messages", "datatype": "number",
      "source": { "kind": "aggregate", "fn": "count",
                  "path": [ { "predicate": "…/hasChat",    "direction": "out" },
                            { "predicate": "…/hasMessage", "direction": "out" } ],
                  "of": { "kind": "node" } } }
  ],
  "filters": { "op": "and", "children": [
    { "target": { "columnId": "messages" }, "operator": "gt", "value": 0 } ] },
  "sort": [ { "columnId": "messages", "dir": "desc" } ],
  "page": { "limit": 100 }
}
```

**(2) "Single user activity dashboard"** — same spec, instance anchor → one row:
```jsonc
{ "root": { "kind": "instances", "instanceUris": ["…/user/alice"] }, "columns": [ /* same measures */ ] }
```

### SPARQL compilation strategy (portable, Jena + Oxigraph)

- **`?root`** is the row key. Anchor: `class` → `?root a ?cls. VALUES ?cls {…}`;
  `instances` → `VALUES ?root {…}`. Graphs via `VALUES ?g {…} GRAPH ?g { … }`.
- **Dimensions (to-one)** → `OPTIONAL { …path… ?col }` (missing ⇒ NULL, row kept).
- **Measures & to-many collapses** → **each in its own sub-`SELECT … GROUP BY ?root`**,
  joined back on `?root`. This is the key pattern that keeps independent multihop
  aggregates from cross-multiplying. e.g. messages:
  ```sparql
  { SELECT ?root (COUNT(DISTINCT ?m) AS ?messages) WHERE {
      VALUES ?g {…} GRAPH ?g { ?root <…hasChat> ?c . ?c <…hasMessage> ?m . } }
    GROUP BY ?root }
  ```
- **Filters / branches:** dimension condition → `FILTER`; a **branch** (condition over an
  inline path) → `FILTER EXISTS { …path + inner condition… }`; `not` group → `FILTER NOT
  EXISTS { … }`; `or` over patterns → `UNION`; **measure condition → `FILTER` on the
  aggregate var** (HAVING-equiv, after its subquery). The boolean tree maps directly onto
  nested `EXISTS`/`&&`/`||`/`UNION`. Each EXISTS is keyed by the bound `?root`, so the
  outer anchor+search prune candidates first.
- **Hops:** `out` = `?a p ?b`; `in` = `?b p ?a`; `plus`/`star` → property paths `p+`/`p*`
  (SPARQL 1.1, supported by both backends).
- **Count:** `SELECT (COUNT(DISTINCT ?root) AS ?n)` over the same WHERE minus
  projection/sort/page → **cached 10 min**, key = hash(spec without `sort`+`page`).
- **Pagination:** keyset — `ORDER BY <sortKeys>, ?root`; cursor encodes the last row's
  (sort values, root); WHERE adds a lexicographic "after cursor" filter. *v1 caveat:*
  multi-key keyset with NULLable sort columns is fiddly — fall back to `OFFSET` +
  cached count for custom sorts until keyset is hardened.
- **Portability seam:** only **search** differs — emit Jena `text:query` (Lucene) when
  available, `CONTAINS` on Oxigraph. Everything else (paths, subquery aggregation,
  EXISTS, GROUP_CONCAT) is standard SPARQL 1.1 on both.

### Guards (anti-footgun at millions of triples)

Max hops per path, max columns/measures per spec, max graphs, per-query timeout, and a
cap on facet cardinality. Unbounded `star`/`plus` on a hot predicate is the classic way
to melt the store — gate it.

---

## 7b. Step (b) — Backend API Contract (synthesized + adversarially reviewed)

> Produced by a 14-agent design+review pass (5 grounding readers, 5 designers, 4 adversarial
> reviewers) against the real code. This section is the **reconciled** contract: where the five
> designs diverged or the review found defects, the corrected decision is recorded here and the
> rationale in §7b.12 (Review blockers & resolutions). All file paths are under
> `libs/naas-abi/naas_abi/apps/nexus/apps/api/`.

### 7b.0 — Endpoints & top-level decisions

| Endpoint | Purpose |
|---|---|
| `POST /api/graph/query` | Compile a spec → **one** SPARQL query → `{columns, rows, page, count}` |
| `POST /api/graph/query/facets` | Distinct values + counts for **one** column under current filters (Excel dropdown) |
| `GET /api/graph/columns` | Column discovery (ontology ∪ data) + datatype inference for an anchored class |
| `PUT/PATCH /api/view/{id}` | **New**: update/rename/move/replace-spec a saved view |
| `GET /api/view/folders`, `PUT /api/view/folders/rename` | **New**: folder tree + folder rename (prefix-rewrite) |

**Reconciled decisions (these resolve cross-design conflicts — see §7b.12):**
1. **One canonical spec module.** A single Pydantic `ViewQuerySpec` with **tagged discriminated
   unions** (`Field(discriminator=...)`), imported by all endpoints. No three-way divergence.
2. **Wire = `spec` only for v1.** The view persists *both* pipeline (authoring truth) and the
   compiled `spec` in `state`; the **query endpoint takes `spec`**. Pipeline-on-the-wire + server
   lowering is deferred until the pipeline authoring UI lands. (Keeps the contract single-shaped.)
3. **`snake_case` wire, no aliases** — matches the 30+ existing models in
   `graph__primary_adapter__schemas.py`; the FE emits snake_case. (§7a authors it in camelCase TS;
   it maps field-for-field.)
4. **`page` lives only at the request top level**; the spec carries **no** `page` (it isn't
   persisted, and the count is page-invariant). `limit` default 100, hard cap 5000.
5. **`graph_uris` lives only in `spec`**; facets/columns read `spec.graph_uris` (no top-level dup),
   so the ownership guard and the query read the same union.
6. Errors: **422** malformed body (Pydantic) · **400** valid-but-unexecutable / guard exceeded
   (`GraphQuerySpecError`) · **403** workspace/graph ownership (`GraphAccessError`) · **504** query
   timeout (`GraphQueryTimeoutError`) · **500** store down (`GraphServiceUnavailableError`, matches
   every existing graph handler). Domain exceptions subclass `Exception`, live in `graph__schema.py`.

### 7b.1 — Canonical spec (shape)

`ViewQuerySpec = ListSpec | AggregateSpec`, discriminated on `mode`. Key sub-shapes (snake_case):
`Hop{predicate, direction:out|in, quantifier:one|plus|star, target_class_uris[]}`;
`ColumnSource = property|node|aggregate` (discriminated on `kind`);
`Column{id ^[A-Za-z0-9_]+$, label, datatype:string|number|date|boolean|iri, source, visible}`;
`FilterNode = {op:and|or, children[]} | {op:not, child} | FilterCondition` (discriminated on `op`,
leaf carries `op:"cond"`);
`FilterCondition{target: {column_id} | {source}, operator, value}`.
- `Column.id` is interpolated as the SPARQL var `?col_<id>` → the `^[A-Za-z0-9_]+$` pattern makes it
  **injection-proof by construction** (belt-and-suspenders: also map id→`?c0,?c1…` so the regex isn't
  the sole defense).
- **`value` is NOT `Any`.** Constrain to `str | int | float | bool | list[str|int|float] | None`
  with bounded list length (`MAX_IN_SET=1000` enforced at the Pydantic layer → 422), so no unvalidated
  dict/nested structure reaches the compiler or the cache-key hasher.
- `ListSpec{mode:list, version:1, graph_uris[≥1], root, columns[≥1], filters?, sort[]}`.
  `AggregateSpec{mode:aggregate, …, fact, group_by[≥1], measures[≥1], filters?, sort[]}`.

### 7b.2 — `POST /api/graph/query` response

`{ mode, columns: ColumnMeta[], rows: dict[column_id → Cell][], page: PageInfo, count: CountInfo,
resolved_sparql?, warnings[], took_ms }`.
- **Row = sparse `dict[column_id → Cell]`** (OPTIONAL miss ⇒ key absent). `Cell{value, uri?(node
  click-through), multi?, overflow?}`. Measure vacuous: `count`→0, others→null.
- `PageInfo{limit, next_cursor?, has_more, offset_fallback}`.
- `CountInfo{total, computed_at, status: exact|cached|stale|estimate, cache_key}`.
- `resolved_sparql` echo defaults **off** in prod (info-disclosure of schema-graph/predicate IRIs);
  gate behind a debug flag; never echo for a spec that failed ownership.

### 7b.3 — Compiler rules (CORRECTED — the review's main finding)

The single root-cause fix: **a column's join requiredness is a function of how it is used, not a
blanket "to-one ⇒ OPTIONAL".** Separate *display-nullability* from *filter/group participation*:

| Column usage | Emit as |
|---|---|
| Projection-only, to-one | `OPTIONAL { …path… ?col }` (nullable display) |
| **Positive** value filter (`eq/contains/in/is/lt…`), to-one | **REQUIRED** join + inline `FILTER` (matches §7a-A; pruning) |
| **Negative/presence** filter (`isEmpty/notContains/neq/notIn`), to-one | `OPTIONAL { …?col }` + explicit unbound handling (`!BOUND \|\| !…`) |
| To-many (any filter) | `FILTER [NOT] EXISTS { … }` — never a join |
| Measure referenced by a filter (HAVING) | **REQUIRED** inner `{ SELECT … GROUP BY ?root }`, predicate in same scope — **no** "push-HAVING-down" escape hatch (it isn't equivalent and de-syncs the count) |
| Aggregate group-by dimension whose relation is **optional** (`minCount 0`) | wrap the **whole hop** in `OPTIONAL` so the null group appears and `COUNT(DISTINCT ?fact)` stays complete |

Other corrected rules:
- **Measures** = independent `{ SELECT ?root (fn(arg) AS ?col) … GROUP BY ?root }` joined on `?root`
  (no cross-product). Projection-only measure → `OPTIONAL` + `COALESCE(?col,0)` for count; **filtered
  measure → required** (so page rows and the count agree).
- **`or` lowering:** leaf value conditions (same OR different columns) → **one** `FILTER(e1 || e2 …)`,
  never UNION. Arms with branches → `FILTER(EXISTS{…} || EXISTS{…})`. UNION only when unavoidable, and
  each arm forced to `{ SELECT DISTINCT ?root … }` so `?root` can't multiply.
- **`count` vs `countDistinct`:** the architecture needs `COUNT(DISTINCT)` to avoid path fan-out, so
  surface **`countDistinct`** as the measure default; only emit non-distinct `count` when the path is
  provably single-valued, else upgrade to distinct with a `warnings[]` note (don't silently mislabel).
- **`concat` collapse:** `GROUP_CONCAT(DISTINCT STR(?v);SEPARATOR=", ")` returns a scalar only →
  **drop `multi`/`overflow` from the contract for concat** (unrecoverable from the string); document
  concat as **order-unstable** across backends and never feed it into a snapshot `specHash`.
- **`first` collapse → `MIN(?v)`** (deterministic, portable), not `SAMPLE` (non-deterministic).
- Keyset pagination requires the sort key be **data-non-null** (emit it as a required triple when used
  as a keyset key) and a totally-ordered concrete datatype; otherwise **OFFSET fallback** (capped at
  `offset+limit ≤ 50000`). `offset_fallback` is surfaced in `PageInfo`.

Worked examples A/B/C from §7a re-derive correctly under these rules (example C / negation was already
correct; A and B needed the requiredness + optional-dimension fixes).

### 7b.4 — Safety layer (`graph/query/sparql_safe.py`, single source)

Replace **both** weak helpers (`graph/service.py:104` escapes only `\`+`"`; `view/service.py:46`
rejects only `<>"' space`) with one hardened module every endpoint imports:
- **`sparql_iri`** — whitelist-validate (reject anything matching `[\x00-\x20<>"{}|^`\\]`), then `<…>`.
- **`sparql_string_literal`** — escape `\ " \n \r \t` (+ C0 controls).
- **`sparql_typed_literal`** — **numbers: reject non-finite (`math.isfinite`)**, emit canonical decimal
  via `format(Decimal(str(v)),'f')` and regex-validate `^-?\d+(\.\d+)?$` (no `repr()`/exponent/inf/nan
  injection); dates via strict `xsd` regex; booleans exact.
- **Lucene/`text:query` term** — `_lucene_escape` **first** (backslash-prefix every Lucene metachar),
  **then** `sparql_string_literal`; **reject bare/leading `*`/`?`/empty** terms (→ fall back to
  `CONTAINS`) to kill full-index-scan DoS.
- **Cursor** — `base64url(json)`; validate `v==1`, `len(vals)==len(sort)`; bind it to the spec (embed
  the `count_cache_key`) so a cursor can't be replayed under a different sort to smuggle a typed value;
  `root` compared as a **string literal** (`sparql_string_literal`, not `sparql_iri`).

### 7b.5 — Portability (Jena/Fuseki, Oxigraph-HTTP, **embedded pyoxigraph**)

There are **three** execution paths, not two — embedded pyoxigraph has **no socket and can't be
interrupted**. Consequences:
- **Per-query timeout** via a real `IGraphQueryStore.select(sparql, *, timeout_ms)`: Jena → `?timeout=<ms>`
  on the `/query` URL + socket read-timeout; Oxigraph-HTTP → socket read-timeout; **embedded → cannot
  enforce** → the **static guards become mandatory & non-overridable** there (no unbounded `p*`/`p+`,
  caps enforced); don't advertise 504 as guaranteed on embedded.
- **`text:query` ≠ `CONTAINS`** (Lucene tokenized vs substring) — **not equivalent**. Make the
  capability flag **per-predicate** (jena-text is indexed per predicate), **fold `fts_backend` +
  per-predicate index capability into the count/facet cache key** (so Lucene-counts and CONTAINS-counts
  never collide), and surface a `SEARCH_LUCENE` warning when the Lucene path is taken.
- **`GROUP_CONCAT(DISTINCT;SEPARATOR)`** is greenfield + version-sensitive on Oxigraph and order-unstable
  across engines → real-engine test on the pinned `pyoxigraph`, document order-instability.
- **`asyncio.gather(rows,count)`** is genuinely concurrent on Jena/HTTP but **serializes on embedded**
  (global `RLock`) — so guards/row-caps are the real protection there; don't claim parallelism.
- Everything else (EXISTS/NOT EXISTS, sub-SELECT aggregation, VALUES, COUNT(DISTINCT), property paths,
  OPTIONAL, BIND/COALESCE) is portable SPARQL 1.1, already proven on the live backend.

### 7b.6 — Counts (cache + invalidation + safety)

- **One `count_cache_key`** (in `count_key.py`): `sha256` of the spec **minus sort/page/labels/visibility
  and non-filter-referenced projection columns**, **namespaced by `workspace_id` + the graph union**
  (so two workspaces never collide) + a `_COUNT_CACHE_SEMVER`. Used by the query endpoint AND the cache.
- **Invalidation uses the REAL `CacheService` API** — the generation-token design called non-existent
  methods. Correct calls: `_cache.set_json(key,val)` / `_cache.get(key)` wrapped in
  `try/except CacheNotFoundError` (get **raises** on miss; there is **no** `set(...)`/`DataType`-typed
  `get`). Fold a per-graph generation token (bumped in the existing `_invalidate_graph_cache`, which all
  9 write paths already funnel through) into the key — **or** the simpler precedent: fold the graph's
  current triple-count/`updated_at` signal into the key (no second cache round-trip on the hot path).
- **Cold-count DoS mitigation:** the count is **deferrable** — return the page immediately with
  `count.status:"estimate"`/`"stale"` and compute the real count async / rate-limited per workspace; add
  a capped-estimate path (`LIMIT 10001` → "10000+") so a cold count never scans the full result set.
- **Cost gate** beyond structural caps: weight UNION branches / EXISTS / measure-subqueries / `p+` and
  reject specs over a budget; default the `p*`/`p+` gate to **deny when the hot-predicate flag is
  unknown** (fail closed).

### 7b.7 — Facets & columns (essentials)

- **Facets:** the query with (a) the **target column's own filter stripped** (Excel "what could I still
  pick"), (b) `SELECT ?v (COUNT(DISTINCT ?root)) GROUP BY ?v ORDER BY DESC(?cnt) LIMIT cap+1`, (c) a
  null/blank bucket via a small `NOT EXISTS` count. **Refuse** faceting on measures and `high_cardinality`
  text columns (graceful `200 + faceted:false`, UI shows a search box). 10-min cache.
- **Columns:** union of ontology side (datatype + object props incl. inherited via `rdfs:subClassOf*` and
  OWL restrictions; inbound relations when asked) and data side (predicates actually on instances +
  per-predicate distinct counts + target classes). Each column tagged `source: ontology|data|both`,
  `instance_count`, `datatype` (ontology `rdfs:range` first → sampled fallback → default), `is_functional`
  (→ to-one, no collapse), `high_cardinality`, `facetable`, `direction`, `target_classes`. Ontology
  pieces lean on the existing 1-day caches; data pieces 10-min.

### 7b.8 — View persistence (extend, don't break)

- **Migration `0033_add_graph_view_path.sql`** (next after 0032): `ADD COLUMN IF NOT EXISTS path
  VARCHAR(1024) NOT NULL DEFAULT ''` + `(workspace_id, path)` index (review confirmed back-compatible;
  also add `graph_views` to `KNOWN_TABLES`). `GraphViewModel` gets the matching `path` column.
- **`state` envelope** (`stateVersion:2`): `{pipeline, spec, presentation}`. `kind="query"` discriminates
  from legacy `DiscoveryViewState`/`NetworkViewState` blobs (which keep loading). `page` is never
  persisted. Relax the `kind=="network"` selectedClassIds guard so it doesn't fire for `query`.
- **`PUT/PATCH /api/view/{id}`** → new `update_view` (rename / move folder / replace state / visibility),
  preserving `id`+`created_at`; `updated_at` auto-bumps. **Replace the dead `UpdateGraphView` DTO**, but
  **EXTEND `CreateGraphView` (keep its `filters` + `user_id` — the live handler uses them)**, only adding
  `path` + the `kind` pattern.
- **Folders** = distinct `path` values (implicit). `GET /folders` (tree + counts), `PUT /folders/rename`
  = **prefix-rewrite in one workspace-scoped transaction** (Python-per-row rewrite to stay
  Postgres/SQLite-portable, not `func.concat`); reject move-into-own-subtree; `(path,name)` collision →
  reject unless `merge=true`. Literal `/folders*` routes declared **above** the greedy `GET /{view_id}`.
- **Visibility** stays workspace-only (`pattern ^(workspace)$`); widening later needs no migration.
- **Snapshot (later)** plugs in additively: a `state.snapshot{status,location,specHash}` object (no schema
  change) where `specHash == count_cache_key`; the query service forks to stream materialized rows when
  `fresh`; the same `_invalidate_graph_cache` sweep flips it `stale`. **Nothing built now.**

### 7b.9 — Multi-tenancy (defense in depth)

Layer 1 `require_workspace_access(user, workspace_id)` (user↔workspace) on **every** handler. Layer 2
**`_validate_graph_ownership(workspace_id, spec.graph_uris)`** on **every** endpoint that takes graphs
(`/query`, `/query/facets`, `/columns`) — reject any graph not in the workspace's owned set or any
protected graph → **403**, before any SPARQL. The owned set comes from the same `list_graphs` source of
truth; resolve it **per-request (or ≤5s shared cache), never a 60s host-local cache** (authorization must
not lag). The schema graph is an internal read-only ontology source, **never** accepted in user-supplied
`graph_uris`. `VALUES ?g {…}` is always an enumerated validated list — never unbound `GRAPH ?g`.

### 7b.10 — Module layout (hexagonal)

New self-contained `graph/query/` sub-package (extend `graph`, don't add a top-level service):
`sparql_safe.py`, `guards.py`, `count_key.py`, `query__schema.py` (frozen-dataclass domain mirror),
`compiler.py` (pure: `compile_list/compile_aggregate/compile_count/compile_facet`), `column_discovery.py`,
`port.py` (`IGraphQueryStore` — justified **only** by the per-query-timeout seam; honestly new structure
for `graph/`), `service.py` (`GraphQueryService`), plus `adapters/primary/graph__primary_adapter__query.py`
(+ `_query_schemas.py`) mounted on the existing `/graph` router, and a secondary adapter for the
timeout-bearing store call. Each with `_test.py` (TDD: compiler worked-example tests first).

### 7b.11 — TDD implementation order

1. `sparql_safe.py` (+ injection property tests) → 2. `query__schema.py` domain dataclasses + exceptions
→ 3. `compiler.py` (write A/B/C assertions first, then green) → 4. `guards.py` + `count_key.py` (stability
tests) → 5. `service.py` over a `_FakeTripleStore` (count cache, gather, facets) → 6. primary adapter +
schemas + route tests → 7. view-persistence (migration, model, `update_view`/`rename_folder`, endpoints)
→ 8. resolve `fts_backend` from config (default `none` until jena-text confirmed in Fuseki).

### 7b.12 — Review blockers & resolutions (traceability)

| # | Severity | Finding | Resolution (above) |
|---|---|---|---|
| Correctness | Blocker | Blanket "to-one→OPTIONAL" breaks negative/presence filters & de-syncs count vs rows; aggregate required-dim drops facts | §7b.3 requiredness-by-usage table; optional dimension hops |
| Correctness | Major | `or` → UNION duplicates rows; `count` silently = `COUNT(DISTINCT)`; `concat` `multi/overflow` unfulfillable | §7b.3 or-lowering / countDistinct default / drop concat multi |
| Portability | Blocker | Per-query timeout doesn't exist on embedded pyoxigraph (no socket/interrupt) & unwired on Jena | §7b.5 real port method; mandatory guards on embedded |
| Portability | Major | `text:query` ≠ `CONTAINS`, flag global not per-predicate, absent from cache key | §7b.5 per-predicate flag + folded into cache key + warning |
| Security | Blocker | Two weak escaping helpers cited; numeric `repr()` inf/nan/exponent injection; Lucene escaping/​wildcard | §7b.4 single hardened `sparql_safe`; finite-number; Lucene order+wildcard ban |
| Security | Major | Ownership guard not on `/columns`+`/facets`; auth from 60s host cache; cursor replay; `value:Any` | §7b.9 ownership everywhere/fresh; §7b.4 cursor bound to spec; §7b.1 typed `value` |
| Security | Major | Cold-count DoS (cache bypass via varying filter values) | §7b.6 deferred/estimate count + per-workspace rate limit + cost gate |
| Architecture | Blocker | 5 designs disagree on spec JSON shape; count-cache calls non-existent `CacheService` methods | §7b.0/§7b.1 one tagged-union spec; §7b.6 real `set_json`/`get`+`CacheNotFoundError` |
| Architecture | Major | `graph_uris` dup; pipeline-vs-spec on wire; camelCase vs snake_case; `CreateGraphView` drops `filters` | §7b.0 single location / spec-only / snake_case; §7b.8 extend CreateGraphView |

---

## 8. Decisions made & remaining questions

**Resolved (see §0):** counts = real + 10-min TTL cache · prod backend = Jena/Fuseki,
Oxigraph local-only · folders = path string with prefix-rewrite rename · every column
filterable · views anchor on instance *or* class · **multihop from v1** · **authoring =
navigation pipeline** (search→filter→follow→…); **root is inferred** = pipeline's terminal
focus, never asked · **pipeline is the persisted source of truth**, compiles to one
ViewQuerySpec/SPARQL query (never stage-by-stage) · **branching IS v1** via two follow
modes (navigate vs constrain) + an AND/OR/NOT filter tree of path-conditions
(EXISTS/NOT EXISTS/UNION) · **two modes: list + aggregate (group-by/pivot)**; group-by
over dims sharing a **common fact** is v1, long-format; **v2 = cartesian join of
unrelated sets, wide dynamic-column pivots, heterogeneous-type rows** ·
**column discovery = ontology ∪ data**, **datatype = ontology range with sampled
fallback** (§7a).

**Still open / to design:**
- **Query spec shape.** What's the canonical, serializable representation of a view's
  query (anchor + filters + sort + projection)? Extend `sparql-steps`, or a new schema?
  It must compile to portable SPARQL and round-trip into the saved view `state`.
- **Filter operators per column type.** Lock the grammar (string vs. number vs. date vs.
  IRI/relation) and how the UI infers a column's type.
- **Aggregation scope for instance-anchored views.** How far do we go now — direct
  relation counts only, or multi-hop / grouped aggregations? (Start minimal.)
- **Facet cost at scale.** Distinct-value enumeration on a high-cardinality column over
  millions of rows is expensive — cap + cache, lazy-load on dropdown open, or only
  offer facets on low-cardinality columns?
- **Fuseki `jena-text` index** — confirm it's enabled in prod (or plan the config change)
  so label/keyword search is indexed rather than scanned.

---

## 9. Progress log

- **2026-06-16** — Completed audit of Explore (frontend `explore/page.tsx` + discovery
  backend + view service + triple-store backend). Created this document.
- **2026-06-16** — Locked key product decisions (§0 #7–10): real counts + 10-min TTL
  cache; **prod = Jena/Fuseki** (Oxigraph local-only) → dual-backend portability + Jena
  Lucene FTS; folders = path string with prefix-rewrite rename; **every column
  filterable**; views **anchor on instance or class** (instance-anchored traversal +
  aggregation is the big new requirement). Updated §1, §7, §8 accordingly.
- **2026-06-16** — **Step (a) done:** designed the **ViewQuerySpec** (§7a) — multihop
  from the start (paths, instance/class anchor, dimensions + aggregate measures, full
  filter grammar, one-row-per-root collapse rule) plus the portable SPARQL compilation
  strategy (subquery-per-measure, cached count, keyset pagination, Jena/Oxigraph search
  seam, guards).
- **2026-06-16** — **Branching promoted to v1** (§7a). Defined two `follow` modes
  (navigate = change grain · constrain = branch/EXISTS), an AND/OR/**NOT** filter tree of
  path-conditions compiling to `EXISTS`/`NOT EXISTS`/`UNION`. Only grain-spanning
  join/tuple (and heterogeneous-type) result rows remain v2.
- **2026-06-16** — Pressure-tested the model against the PHASES `documents.owl` ontology
  with two real queries (§7a worked examples A & B). Query A (list + branch) validated
  v1 unchanged. Query B ("per paper, items grouped by Extraction") added an explicit
  **aggregate / group-by (pivot) mode** (fact + dimensions + measures) and **moved the
  v1/v2 line**: group-by over dims sharing a common fact is v1 (long-format); cartesian
  joins / wide dynamic pivots / heterogeneous rows stay v2.
- **2026-06-16** — Added worked example C (negation: "papers with no items from
  gpt-5-mini" → `NOT EXISTS`). Locked three filter-semantics rules: to-many path filters
  are **existential** by default (`not` → `NOT EXISTS`); negation includes the **vacuous**
  case; **anchor on the smaller set** for negation/EXISTS. Model has now survived list,
  multihop measures, AND/OR/**NOT** branching, pivot, and negation — all single-query.
- **2026-06-16** — **Step (b) done (§7b):** API contract designed via a 14-agent
  grounding→design→adversarial-review pass, then **reconciled**. Locked the 3 query endpoints
  (`/query`, `/query/facets`, `/columns`) + view-persistence changes (path column + migration 0033,
  `PUT` update, folder rename, snapshot hook). The review caught and we resolved: the
  to-one-OPTIONAL-vs-required correctness root cause, `or`/`count`/`concat` lowering bugs, the
  embedded-Oxigraph timeout gap, SPARQL-injection hardening (single `sparql_safe`, finite numbers,
  Lucene escaping), cross-tenant guard coverage + cold-count DoS, and the broken count-cache API.
  Full traceability in §7b.12.
- **Next (step (c)):** either (1) **frontend rework plan** (decompose `explore/page.tsx`, the
  pipeline/Excel UI against the new endpoints, retire the dead zustand state), or (2) **start
  implementation** TDD-first per §7b.11 (`sparql_safe` → compiler → service → adapter → views).

### Implementation log (backend, TDD per §7b.11)

- **2026-06-16 — Step 1/8 DONE: `sparql_safe.py` (injection-safety layer).** 45 tests green.
  - `app/services/graph/graph__schema.py` — added domain exceptions `GraphQuerySpecError` (→400),
    `GraphAccessError` (→403), `GraphQueryTimeoutError` (→504).
  - `app/services/graph/__init__.py` — made `GraphService` **lazy** (PEP 562 `__getattr__`) so
    importing `graph.query.*` no longer triggers `service.py`'s import-time `ABIModule.get_instance()`
    call; this unblocks all co-located `graph/` tests (incl. the planned `compiler_test.py`). Public
    API unchanged; package now imports without full app init (strictly better).
  - `app/services/graph/query/{__init__,sparql_safe,sparql_safe_test}.py` — `sparql_iri`
    (whitelist-reject), `sparql_string_literal` (escape `\ " \n \r \t` + C0), `sparql_typed_literal`
    (numbers reject non-finite/exponent; strict date regex; bool/iri/string), `should_use_fulltext`
    + `lucene_query_literal` (Lucene-escape-then-SPARQL-escape, wildcard-scan safe). Review injection
    payloads pinned as tests.
  - Test cmd: `uv run python -m pytest <file> -o addopts=""` (the repo-root `pytest.ini` is the
    ABI-core one — its `--cov=lib` gate must be overridden when running a single nexus file).
- **2026-06-16 — Dev stack ready for integration testing.** Copied `.env` from the main worktree;
  `abi dev up --service oxigraph -d` brings the store up natively (no Docker) at a per-worktree port
  (`abi dev ports`; here oxigraph=7942, api=9943, web=12064) — verified it answers SPARQL. So the
  compiler's generated queries can be integration-tested against a real Oxigraph, not just
  asserted as strings. (Run `uv`/`abi` with the sandbox off.) Saved to session memory.
- **2026-06-16 — Steps 2 + 3 (list-mode core) DONE.** `query/query__schema.py` (frozen-dataclass
  spec mirror + `CompileContext`/`CompiledQuery`/`ColumnMeta`) and `query/compiler.py`
  (`compile_list` + count + `compile_query` dispatcher). Implements the **corrected requiredness
  rule** (positive conjunctive filter on a single-valued column → required join; projection-only →
  `OPTIONAL`), path lowering (incl. `p+`/`p*` + target-class), the AND/OR/NOT filter tree →
  `FILTER` / `FILTER EXISTS` / `FILTER NOT EXISTS` / `EXISTS||EXISTS`, inline-source branches, value
  operators, sort + `ORDER BY … ?root`, and the count query (drops projection-only bindings).
  - **`compiler_test.py`** — 8 unit tests: worked examples **A** (list+branch) and **C** (negation)
    assert the exact page **and** count SPARQL (whitespace-normalized) = the §7a targets; + sort,
    unknown-column rejection, aggregate-not-yet guard. Green.
  - **`compiler_integration_test.py`** — runs the compiled A/C SPARQL against the **live Oxigraph**
    with a fixture; A returns exactly `{item1,item4}` + count 2, C returns `{paper2,paper3}` (incl.
    the **vacuous** no-items paper) + count 2. Skipped unless `NEXUS_OXIGRAPH_URL` set. **Verified
    green** against `:7942`.
  - Note for the service layer: SPARQL result rows key columns by their var `col_<id>` → map back
    via `CompiledQuery.var_for_column`.
- **2026-06-16 — Measures + aggregate/pivot mode DONE.** Extended `compiler.py`:
  - **List-mode measures** → per-`?root` `OPTIONAL { SELECT … GROUP BY ?root }` subqueries +
    `COALESCE(…,0)` for count/sum; a measure filter is a HAVING-equiv `FILTER(?col_<id> op v)` on
    the coalesced var — **universally correct** for `>0`/`=0`/`between` (stronger than the review's
    "required join", which only works for existence-implying filters), and the count reuses the same
    subquery+filter so page and total never diverge.
  - **Aggregate/pivot mode** (`compile_aggregate`) → `GROUP BY` dimension tuples + measure aggregates;
    dimension paths are **`OPTIONAL`** (review B3 correction → facts lacking the relation still
    counted under a null group), `COUNT(DISTINCT ?fact)`, count = `COUNT(*)` over the grouped subquery.
  - **`compiler_test.py`** — +5 tests: §7a example **1** (multihop measures, page+count) and **B**
    (pivot, page+count) assert exact SPARQL; aggregate guards. **13 unit tests** green.
  - **`compiler_integration_test.py`** — +2 tests on the **live Oxigraph**: example 1 → `u1=(2,3)`,
    `u2=(1,1)`, Carol (0 msgs) filtered, ordered by messages desc, count 2; example B → the 3
    `(paper,pipeline,count)` tuples, count 3. **All 4 integration tests green** (`:7942`).
  - **Full query package: 62 passed.** Compiler now covers list (branch/negation/measures) + pivot —
    every shape pressure-tested in §7a, verified end-to-end as running SPARQL.
- **2026-06-16 — Compiler COMPLETE (list + aggregate, all features).** Added to `compiler.py`:
  - **To-many `collapse`** (concat/count/min/max/first) → per-`?root` GROUP BY subquery
    (`GROUP_CONCAT(DISTINCT …)` order-unstable per review; `first`→`MIN` deterministic); a collapsed
    column filters as HAVING-equiv.
  - **Keyset cursor pagination** + **OFFSET fallback**: keyset when every sort key is a single-valued,
    totally-ordered, non-aggregated column (sort keys then forced to **required** joins so the cursor
    compare is non-null — review M1); else OFFSET (capped by the service). `CompiledQuery` now carries
    `uses_offset_fallback` + `order_columns`; first page (no cursor) emits identical SQL to before.
  - **Aggregate-mode filters**: a conjunction of conditions → dimension/fact → `WHERE FILTER`/`EXISTS`,
    measure → `HAVING`; complex OR-across-WHERE/HAVING rejected (v1).
  - **`Page` dataclass** (request-level pagination, never in the spec).
  - **Tests:** `compiler_test.py` **19 unit** (collapse, keyset first/next/offset-fallback, aggregate
    WHERE+HAVING, complex-filter rejection) + `compiler_integration_test.py` **7 live-Oxigraph**
    (A/C/1/B + keyset 2-page walk `[u1,u2]→[u3]`, collapse count `{u1:2,u2:1,u3:0}`, aggregate HAVING).
  - **Full query package: 71 passed; ruff clean.** Deferred (perf only, not functional): the
    **jena-text** search seam — `CONTAINS` is already correct on both backends; jena-text needs a
    configured Fuseki Lucene index to verify, so it's a one-function follow-up.
- **2026-06-16 — Service layer + `POST /api/graph/query` endpoint DONE.**
  - `query/count_key.py` (workspace+graph-scoped sha256 of spec-minus-sort) + `count_key_test.py` (6).
  - `query/guards.py` (`QueryGuards` caps: graphs/columns/filter-depth/filter-nodes/in-set/page;
    `clamp_limit`, `validate_spec`) + `guards_test.py` (7).
  - `query/port.py` (`IGraphQueryStore` + `Binding`) and `query/adapters/secondary/…triplestore.py`
    (`GraphQueryTripleStoreAdapter` — shapes rdflib `ResultRow.labels` → `Binding`; `resolve_fts_backend`
    = the single backend switch, "none" until Fuseki jena-text lands). **This is the backend seam** the
    compiler stays pure behind.
  - `query/service.py` (`GraphQueryService.run_query`): ownership guard (workspace↔named-graph, async
    `list_graphs`) → guards → compile → **`asyncio.gather(rows, count)`** → assemble (row-map via
    `var_for_column`, cursor encode/decode, keyset/offset `next_cursor`, has_more via limit+1 probe).
    Count cache injectable (`NoCountCache` default; FS 10-min impl is a follow-up). + `service_test.py` (4).
  - `query/adapters/primary/…schemas.py` — full Pydantic transport (discriminated unions, recursive
    `FilterNode`) + `to_domain()`/`from_result()` + `…schemas_test.py` (4).
  - **Route**: `@router.post("/query")` added to the existing graph router in
    `graph__primary_adapter__FastAPI.py` + `_build_graph_query_service` DI (triple store + owned-graphs
    from `list_graphs` + protected graphs). Errors → 403 (`GraphAccessError`) / 400 (`GraphQuerySpecError`)
    / 500. Schemas live under the **lazy-safe** `graph/query/adapters/primary` (the eager
    `graph/adapters/primary/__init__` would drag in `ABIModule`).
  - **Verified:** query package **94 passed** (unit + live-Oxigraph), incl. a **full-chain service
    integration** (GraphQueryService → real triplestore adapter → compiler → Oxigraph: example A rows +
    count + ownership reject). ruff clean; route syntax-compiles + no import cycles.
  - **Live HTTP smoke test PASSED (2026-06-16).** Booted the stack via `abi dev up --service oxigraph
    --service api -d` (must **exclude dagster** — running it alongside the API makes the API worker
    busy-loop). The route registers in `/openapi.json`. Verified through real HTTP + Bearer auth + DB:
    **401** (no auth) · **403** (graph not owned by workspace — multi-tenancy guard) · **200** example A
    (list+branch) → item1+item4, count 2 · **200** example B (aggregate pivot) → 3 group tuples, count 3.
    The whole chain (auth → workspace access → ownership → spec lowering → compile → Oxigraph → response)
    works end-to-end. (Added `X_BEARER_TOKEN=dummy` to the worktree `.env` — an unrelated integration
    secret `config.yaml` requires; not used by the query path.)
- **2026-06-16 — `GET /api/graph/columns` + `POST /api/graph/query/facets` DONE (read API complete).**
  - `query/column_discovery.py` (ontology ∪ data): data-side predicate scan (datatype props +
    relations + target classes + per-predicate counts), **functional-from-data** (`COUNT(?o)==subjects`),
    sampled datatype + high-cardinality→facet-refusal, ontology-declared overlay (valid-but-empty
    columns, `rdfs:range` datatype). `discover_columns_test.py` (3) + live test.
  - `compile_facet` (compiler): strips the target column's own filter (Excel semantics), groups the
    column value, `COUNT(DISTINCT ?root)`, `LIMIT cap+1` truncation; refuses measures. `+_strip_column_filter`.
    2 unit tests.
  - `GraphQueryService.facets()` + `.discover_columns()` (ownership-guarded, threaded). Transport +
    routes `POST /query/facets`, `GET /columns` on the graph router; `MAX_FACET_CARDINALITY=200`.
  - **Live HTTP verified** (Alpha workspace / test_compiler graph): `/columns` → extracted_text
    (property/string/functional, facet=False) + extracted_by→Extraction + extracted_from_chunk→Chunk;
    `/query/facets` → extracted_by buckets `{gpt:1, other:3}`; measure facet → graceful `faceted:false`.
  - **Query package: 100 passed; ruff clean.** The full **read API** (`/query`, `/columns`,
    `/query/facets`) is built, unit+integration tested, and live-verified over real HTTP+auth.
- **2026-06-16 — View persistence DONE (save-views goal delivered).**
  - Migration **`0033_add_graph_view_path.sql`** (`path VARCHAR(1024)` + `(workspace_id,path)` index) —
    applied live on API boot. `GraphViewModel.path` column added.
  - `view/service.py`: `_normalize_path`; `create_view(path=…)` + `kind="query"` guard (state.spec);
    `update_view` (rename/move/replace-state/visibility, **preserves id+created_at**); `list_views(path,
    recursive)`; `list_folders` (implicit ancestor folders + counts); `rename_folder` (prefix-rewrite
    across the subtree, per-row → Postgres/SQLite-portable, collision guard, no move-into-own-subtree).
    `_model_to_dict` carries `path`.
  - `endpoints/view.py`: `GraphViewInfo.path`; extended `CreateGraphView` (kept `filters`/`user_id`, added
    `path` + kind pattern); **replaced** the dead `UpdateGraphView`; new `FolderNode`/`FolderListResponse`/
    `RenameFolder*`; routes `PUT|PATCH /{view_id}`, `GET /folders`, `PUT /folders/rename` (declared before
    the greedy `GET /{view_id}`); `list` gained `path`/`recursive`. Workspace-only visibility kept.
  - **Live HTTP verified** end-to-end: create query view in `Research/Papers` → list (path shown) → folder
    tree (implicit ancestors) → update (rename+move, id preserved) → folder rename `Research→Studies`
    (prefix-rewrite, view path → `Studies/Active`) → delete. ruff clean.
  - **🎯 BACKEND COMPLETE & LIVE-VERIFIED.** The full Explore API — read (`/query`, `/columns`,
    `/query/facets`) + view persistence (CRUD + folders) — is built, tested, and verified over real
    HTTP+auth+DB. This is everything the frontend Explore UI needs.
- **2026-06-16 — Frontend test harness established + verified.** Two layers exist in `apps/nexus`:
  **vitest** unit (`apps/web/src/lib/*.test.ts`, run via `pnpx vitest run`) and **Playwright** e2e
  (`e2e/`, `playwright.config.ts`, `WEB_URL`-overridable). Gotchas in this env: the pnpm mirror
  (`pkg.creativengine.com`) is VPN-only and Playwright's bundled chromium (1208) can't be downloaded —
  but **system Chrome works via `test.use({ channel: 'chrome' })`**, and the public npm registry is
  reachable. Wrote `e2e/smoke.spec.ts` (admin-login helper + 2 tests) and ran it **green against the
  live stack**: `CI=1 WEB_URL=http://127.0.0.1:12064 node_modules/.bin/playwright test e2e/smoke.spec.ts
  --project=chromium`. (The old `e2e/auth.spec.ts` is stale — ignore it.) **This means the rework is
  verifiable**: build new Explore components with `data-testid`s + e2e specs (and vitest for the pure
  pipeline→spec client logic, installing vitest from the public registry when that module lands).
- **Next:** **wire the frontend Explore UI** to these endpoints (decompose `explore/page.tsx`, the
  navigation-pipeline + Excel-table against `/query`+`/facets`+`/columns`, save/load/organize views,
  retire the dead zustand graph state), built test-first against the e2e harness. Backend optimizations
  to fold in later: FS 10-min count cache; feed `/columns` `is_functional` into the compiler ctx.

### Frontend Explore rework — Slice 1 (list mode end-to-end)

- **2026-06-16 — New Explore workbench built (list mode), wired to the new backend.** Built as a fresh,
  decomposed component tree at a parallel route `graph/explore-next/page.tsx` (runs alongside the legacy
  4,147-line `graph/explore/page.tsx` so they can be compared before the swap; the legacy page is
  untouched).
  - **Pure, framework-free core** under `apps/web/src/lib/graph-query/` (all unit-tested with vitest):
    `types.ts` (TS mirror of the snake_case transport), `columns.ts` (discovered→spec column mapping +
    per-datatype operator vocab), `filters.ts` (Excel per-column state → `FilterNode` tree, value
    coercion/validation), `spec.ts` (draft→`ListSpec`/`AggregateSpec` + client-side guards mirroring
    `QueryGuards`), `paths.ts` (pure URL builders), `client.ts` (typed `runQuery`/`fetchColumns`/
    `fetchFacets` + views CRUD over `authFetch`), `explore-state.ts` (the reducer + `specFromState` +
    `stateFromSpec`/`filtersFromNode` for loading saved views). Tests: `*.test.ts` next to each module.
  - **React layer** under `apps/web/src/components/graph/explore/`: `use-explore.ts` (graphs/classes
    discovery via the existing `/discovery/classes` + new `/columns`, debounced auto-run query with an
    out-of-order guard, cursor "Load more", on-demand facets), `BuilderPanel` (graph + anchor-class +
    column picker), `ResultsTable` (sortable headers, per-column filter popover, cell uri/literal
    rendering, count + keyset/offset pagination), `ColumnFilterPopover` (facet checkboxes + free-form
    condition row), `ViewsSidebar` (saved views grouped by folder), `SaveViewDialog`, and
    `ExploreWorkbench` (composition + views CRUD + default-column auto-seed).
  - **Verification (the live e2e was blocked by machine load — see below; everything else is green):**
    - `tsc --noEmit -p tsconfig.json`: **0 errors project-wide**.
    - **Pure logic**: compiled the lib to CJS with the repo's `tsc` and ran the assertions on node —
      **35 checks pass** (columns/filters/spec/paths/reducer + saved-view round-trip). (vitest couldn't
      be installed locally: the user `.npmrc` forces the VPN-only mirror and the public registry was too
      flaky for a full install here; the committed `*.test.ts` run via `pnpm test` in the normal env/CI.)
    - **Backend contract proven with the client's exact wire format**: built the request the TS client
      produces for `ExtractedItem` (3 discovered columns) and POSTed to `/api/graph/query` → **4 correct
      rows + exact count + compiled SPARQL**. `/columns` and `/discovery/classes` confirmed against the
      `test_compiler` graph (PHASES fixture) in workspace `ws-3e360b19bb96`.
    - **e2e** `e2e/explore-next.spec.ts` (3 tests: anchor→rows, sort, save-view→sidebar→delete) reaches
      **login → nav → workbench render → graph select → class select** in live runs; the remaining
      assertions were blocked only by the dev box being saturated (load ~10, a `com.apple.Virtualization`
      VM at ~56% CPU + the user's Chrome), which made the single-threaded Next dev server time out on
      navigation. Re-run when the box is quiet: `CI=1 WEB_URL=http://127.0.0.1:<web-port>
      node_modules/.bin/playwright test e2e/explore-next.spec.ts --project=chromium --workers=1`.

- **2026-06-16 — Fixed a real local-stack bug: the dev oxigraph HTTP server wedging under load.**
  `libs/naas-abi-core/.../triple_store/oxigraph_server.py` had **`async def` handlers calling synchronous,
  blocking pyoxigraph `store.query`/`serialize`/`update`/`dump`/`bulk_load` inline** → those calls ran on
  the single uvicorn event loop, so under any concurrency (the new UI fires classes + columns + auto-run
  together; the user browses at the same time) the loop starved and the server stopped accepting
  connections ("alive but HTTP down" — it was already wedged at the start of this session). Fix: dispatch
  every blocking Store op to a worker thread via `run_in_threadpool`. **Critical subtlety**: pyoxigraph's
  query result (`QuerySolutions`/`QueryTriples`) is *unsendable* (thread-bound — panics if touched from
  another thread), so `query` + `serialize` must run on the **same** thread → combined into one
  `_query_sync(query, accept)` helper. Verified with a 60-concurrent-query stress test: **all pass
  (avg 59ms), server stays healthy**; previously this wedged or crashed. (Local dev only; prod uses Jena.)
  - **Dev-stack note (per-worktree ports shuffle):** `abi dev down` stops the parent PID but orphaned
    uvicorn/next children can briefly hold the port, so the next `up` bumps to the next port (api 9943→9944,
    web 12064→12065). Web's API URL is wired at *its* startup, so after an api port change the web must be
    restarted too. A full `abi dev down` + kill orphans on the ports + single `up` gives a consistent set.
