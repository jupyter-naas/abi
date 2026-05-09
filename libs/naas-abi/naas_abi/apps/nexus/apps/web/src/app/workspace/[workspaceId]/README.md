# Workspace Pages — Graph & Ontology

> Architectural reference for the `graph/` and `ontology/` features under
> `src/app/workspace/[workspaceId]/`. Read this before adding code, requesting
> changes, or debugging anything graph- or canvas-related.

## 1. What lives here

Two feature pages sharing one canvas runtime:

- `graph/` — instance graph (individuals, triples) for the current workspace
- `ontology/` — class/relationship browser for the active ontology

Backed by a shared canvas (`src/components/graph/vis-network/`) and a shared
infra layer (`src/lib/api/`, `src/lib/schemas/`, `src/lib/bfo.ts`,
`src/providers/query-provider.tsx`).

Built on:

- **Next.js 14** App Router, all pages are client components (`'use client'`)
- **TanStack Query 5** — server state (queries + mutations + cache)
- **Zod 3** — API contract validation at the boundary
- **vis-network 9** — interactive canvas
- **Radix UI** — dialogs / dropdowns
- **Tailwind CSS** — styling

## 2. Architecture at a glance

```
┌──────────────────────────────────────────────────────────────┐
│                    Page (graph|ontology/page.tsx)            │
│   • UI mode + URL state                                      │
│   • Composes _components/* and _hooks/*                      │
│   • No fetch, no cache, no business state                    │
└──────────────────┬───────────────────────────────────────────┘
                   │ uses
       ┌───────────▼─────────────┐ ┌─────────────────────────────┐
       │  _components/*.tsx      │ │  _hooks/use-*-queries.ts    │
       │  Presentational +       │ │  TanStack Query hooks       │
       │  view-local state       │ │  (queries + mutations)      │
       └─────────┬───────────────┘ └────────────┬────────────────┘
                 │                              │ calls
                 │                   ┌──────────▼──────────────┐
                 │                   │  lib/api/{graph,        │
                 │                   │     ontology}.ts        │
                 │                   │  Typed API + query keys │
                 │                   └──────────┬──────────────┘
                 │                              │ validates with
                 │                   ┌──────────▼──────────────┐
                 │                   │  lib/schemas/*.ts (Zod) │
                 │                   │  + lib/api/client.ts    │
                 │                   └──────────┬──────────────┘
                 │                              │ HTTP via authFetch
                 │                              ▼
                 │                       Backend API
                 │
       ┌─────────▼──────────────────────────────────────────────┐
       │  components/graph/vis-network/  (shared canvas)        │
       │  index.tsx → use-vis-network → layout / use-node-logos │
       └────────────────────────────────────────────────────────┘
```

## 3. Folder & file map

### 3.1 Pages

| File | Concern | Owns |
|------|---------|------|
| `graph/page.tsx` | Top-level orchestrator for the instance-graph feature. | Active mode, selected graph/view, selected node/edge. |
| `ontology/page.tsx` | Same shape, for the read-only ontology view. | View mode, ontology path, selected term. |

Pages **never** fetch directly. They call `useGraph*` / `useOntology*` hooks
and render `_components/*`.

### 3.2 `graph/_components/`

| File | Purpose |
|------|---------|
| `types.ts` | `GraphNode`, `GraphEdge`, `GraphOption`, `FilterOption`, `OntologyClassOption`, `ViewFilterDraft`, `GraphPageMode`. Single source of truth for page-local types. |
| `FilterOptionDropdown.tsx` | Searchable URI/label dropdown for view filter values. |
| `ClassOptionDropdown.tsx` | Searchable ontology-class dropdown for "create individual". |
| `StatCard.tsx` | One-stat tile with icon. |
| `IndividualDetailPanel.tsx` | Right-pane detail for a selected individual: data props + object props. |
| `IndividualsSplitView.tsx` | Class-grouped list + detail panel for the `graph` mode. |

### 3.3 `ontology/_components/`

| File | Purpose |
|------|---------|
| `types.ts` | `ViewMode`, `OntologyOverviewGraphNode/Edge`, `OntologyOverviewStats`. |
| `resolveNodeBucket.ts` | Thin wrapper over `lib/bfo.ts:resolveBucket` so ontology types convert without ceremony. |
| `OntologyOverviewView.tsx` | Stats + filterable lists of classes/relationships. Owns its search query state. |
| `OntologyNetworkView.tsx` | Main canvas view. Owns BFO/restrictions/object-properties filters, layout direction, inspector. Pulls subclass-of via `useOntologyHierarchy`. |
| `OntologySplitView.tsx` | Hierarchical class/relationship browser with detail panel. |
| `EntityDetailView.tsx` | Inline editor for a class or relationship. |

### 3.4 Hooks — `_hooks/use-*-queries.ts`

`graph/_hooks/use-graph-queries.ts`:

- **Queries**: `useGraphList`, `useGraphNetwork`, `useGraphOverview`,
  `useGraphViews`, `useGraphParents`, `useOntologyClasses`,
  `useViewFilterOptions`, `useTriplePreview`
- **Mutations**: `useCreateGraph`, `useUpdateNode`, `useDeleteNode`,
  `useCreateView`, `useUpdateView`, `useDeleteView`
- **Internal**: `useUserScope` — namespaces query keys by user (prevents
  cross-account cache leaks)

`ontology/_hooks/use-ontology-queries.ts`:

- **Queries**: `useOntologyOverviewGraph`, `useOntologyOverviewStats`,
  `useOntologyHierarchy`, `useOntologySubclassOptions`,
  `useOntologySubpropertyOptions`
- **Mutations**: `useExportOntology`

These are the **only** place pages should fetch. Components never call
`apiFetch` directly.

### 3.5 API client — `src/lib/api/`

| File | Purpose |
|------|---------|
| `client.ts` | `apiFetch<T>(path, schema, options)` — `authFetch` + Zod validation. `apiFetchRaw` for blobs. `buildQuery` for query strings. `ApiError` (HTTP) + `ApiSchemaError` (validation). |
| `graph.ts` | Typed function per graph endpoint, plus `graphKeys` (query-key factory). Applies schema-optional defaults at the call site. |
| `ontology.ts` | Same shape, for ontology endpoints. |

### 3.6 Schemas — `src/lib/schemas/`

| File | Purpose |
|------|---------|
| `graph.ts` | `ApiNodeSchema`, `ApiEdgeSchema`, `NetworkResponseSchema`, `OverviewSchema`, view/filter/triple schemas. |
| `ontology.ts` | `OverviewGraphResponseSchema`, `OverviewStatsResponseSchema`, `OntologyTermsResponseSchema`, `HierarchyResponseSchema`. |

> **Convention**: optional fields use `.optional()`, NOT `.default()` — Zod's
> type inference loses the default for nested arrays/objects in `z.infer<>`.
> Defaults are applied at the boundary in `lib/api/*.ts` (e.g. `?? []`).

### 3.7 Shared canvas — `src/components/graph/vis-network/`

| File | Lines | Purpose |
|------|-------|---------|
| `index.tsx` | ~200 | `VisNetwork` orchestrator. Builds `toVisNode` / `toVisEdge`, mounts the container. Re-exports `BFOBucketFilters`, `BFOLegend`, `BFO_BUCKET_DEFS`. |
| `layout.ts` | ~255 | Pure helpers (no React, no DOM): `computeHierarchicalPositions` (Reingold-Tilford), `computeSpreadPositions` (sunflower spiral), `nodeCardSvgDataUri`. |
| `use-vis-network.ts` | ~507 | Canvas runtime — 14 refs, 8 effects, position memory, viewport memory per `viewStateKey`. **The risky module.** |
| `use-node-logos.ts` | ~92 | Async `/api/image-data` fetch + URL→data-URI cache. |
| `bfo-panels.tsx` | ~183 | `BFOBucketFilters` (interactive) + `BFOLegend` (static). |

External callers import from `'@/components/graph/vis-network'` — resolves to
`index.tsx`. **Don't import internals (`./layout`, `./use-vis-network`) from
outside this folder.**

### 3.8 Shared infra

| File | Purpose |
|------|---------|
| `lib/bfo.ts` | Single source of truth for the BFO 7-buckets: `BfoBucket`, `BFO_COLORS`, `BFO_BUCKET_DEFS`, `resolveBucket`, `resolveBucketColors`, `wrapLabelTwoLines`. Internal IRI/label maps live here too. |
| `providers/query-provider.tsx` | App-wide TanStack Query client. Auth-aware retry (skips retries on 401/403). Listens for `graph-cache-refresh` window events for legacy invalidation. Mounted in `workspace/[workspaceId]/layout.tsx`. |

## 4. Data flow

### Read

```
Component
   └─ useGraphNetwork({ graphId, viewId })          ← _hooks/
         └─ fetchNetwork(graphId, viewId)            ← lib/api/graph.ts
               └─ apiFetch('/api/.../network', NetworkResponseSchema)
                     ├─ authFetch (cookie auth)
                     └─ Zod validate
TanStack Query caches result by `graphKeys.network(...)` for 30 s.
```

### Write

```
Component
   └─ useUpdateNode().mutateAsync({ ... })           ← _hooks/
         └─ updateNode(...)                          ← lib/api/graph.ts
               └─ apiFetch('PATCH /node', schema)
On success
   └─ queryClient.invalidateQueries({ queryKey: graphKeys.network(...) })
         └─ Affected queries refetch automatically
```

### Canvas

```
nodes/edges from hooks → page.tsx → <VisNetwork />
   └─ index.tsx builds toVisNode/toVisEdge
         (closes over logoDataByUrl + hierarchicalPositions)
         └─ useVisNetwork:
              • diff DataSet (add / update / remove)
              • preserve positions (nodePositionsRef)
              • restore zoom/pan if viewStateKey unchanged (savedFilterViewsRef)
              • selection / centring with double-RAF
```

## 5. Playbooks — how to evolve

### A. Add a new query (read-only)

1. Add the response schema to `lib/schemas/graph.ts` (or `ontology.ts`).
2. Add a typed fetcher in `lib/api/graph.ts`:
   ```ts
   export async function fetchFoo(workspaceId: string, options: RequestOptions = {}) {
     const data = await apiFetch(`/api/workspaces/${workspaceId}/foo`, FooSchema, options);
     return { items: data.items ?? [] };
   }
   ```
3. Add a query-key entry to `graphKeys` (next to existing keys; keep the
   shape consistent — `[scope, ...args]`).
4. Add a `useFoo` hook in `_hooks/use-graph-queries.ts`:
   ```ts
   export function useFoo(workspaceId: string) {
     const scope = useUserScope();
     return useQuery({
       queryKey: graphKeys.foo(scope, workspaceId),
       queryFn: () => fetchFoo(workspaceId),
       enabled: Boolean(workspaceId),
     });
   }
   ```
5. Consume from a component.

### B. Add a new mutation

1. Schema → `lib/schemas/`.
2. Typed mutation in `lib/api/graph.ts`.
3. `useFooMutation` hook with explicit cache invalidation:
   ```ts
   export function useFooMutation() {
     const qc = useQueryClient();
     const scope = useUserScope();
     return useMutation({
       mutationFn: fooApi,
       onSuccess: () => {
         qc.invalidateQueries({ queryKey: graphKeys.network(scope, ...) });
         qc.invalidateQueries({ queryKey: graphKeys.overview(scope, ...) });
       },
     });
   }
   ```
4. Use `mutateAsync` from a component handler.
5. For destructive actions, call `useConfirm` from `components/ui/dialogs.tsx`
   first — never `window.confirm`.

### C. Add or edit a BFO bucket

Edit **only** `lib/bfo.ts`:

- Extend the `BfoBucket` union type
- Add to `BFO_COLORS`
- Add to `BFO_BUCKET_DEFS` (label + description)
- Update the internal IRI/label maps (`BFO_URI_TO_BUCKET`, `LABEL_TO_BUCKET`)

Legend, filters, and canvas read from this file — no other change needed.

### D. Add a presentational component to a page

1. Create `_components/<PascalCase>.tsx`.
2. Receive data as props; **no `useQuery` inside** (keep it pure).
3. Local state for view-only concerns (open/closed, search query) is fine.
4. Add types to `_components/types.ts` if shared with other components.
5. Import from `page.tsx` or another `_components/*` file.

### E. Change canvas behaviour

Decision tree:

| Change | Edit |
|--------|------|
| Pure layout math | `vis-network/layout.ts` |
| Logo handling | `vis-network/use-node-logos.ts` |
| Visual style of nodes/edges | `toVisNode` / `toVisEdge` in `vis-network/index.tsx` |
| Selection / pan / zoom / physics | `vis-network/use-vis-network.ts` |
| BFO panels UI | `vis-network/bfo-panels.tsx` |

#### Caution: `use-vis-network.ts`

The eight effects in this hook run in a specific order vis-network depends on.
**Do not reorder, merge, or split effects without a regression note.**

1. `useLayoutEffect` for `viewStateKey` — captures viewport BEFORE the next paint
2. Network init — empty deps, runs once
3. Physics toggle — must run before "Update nodes"
4. Update nodes — preserves positions, applies hierarchy, schedules stabilization
5. Update edges — separate so edge-only changes don't restart physics
6. `stabilizeKey` — targeted re-stabilization
7. `selectedNodeId` — pan-to-centre with double-RAF (waits for canvas resize)
8. `centerOnNodeId` — re-fit with double-RAF

If you change anything here:

- Smoke-test all four flows: graph mode, view mode, ontology overview,
  ontology network with subclass-of toggle.
- Watch for: position drift, viewport reset, physics-not-disabled-after-stabilize,
  double-fit on inspector close.

### F. Add a new page mode

Example: a new "import CSV" mode in the graph page.

1. Extend `GraphPageMode` in `_components/types.ts`.
2. Plumb URL/state in `page.tsx`.
3. Create `_components/ImportCsvView.tsx` (presentational; loads its own
   data via a new hook if needed).
4. Add queries/mutations per Playbooks A/B.
5. Render conditionally on `mode === 'import-csv'`.

Mode-local state belongs in the mode's component, not in `page.tsx`.

### G. Replace vis-network with a different canvas library

The public surface is small:

- `<VisNetwork>` props in `index.tsx`
- `BFOBucketFilters` / `BFOLegend` are vis-network-free

Steps:

1. Build a new `index.tsx` against the new library, keeping the prop surface.
2. Reuse `layout.ts` (pure) and `use-node-logos.ts` (vis-network-free).
3. Replace `use-vis-network.ts` with the new lib's lifecycle hook.
4. Consuming pages don't change.

## 6. Anti-patterns

| Don't | Do |
|-------|-----|
| `useEffect(() => { fetch(...) }, [])` in a page or component | Add a hook in `_hooks/use-*-queries.ts` |
| Call `apiFetch` directly from a component | Always go through a query hook |
| New BFO color literal in a component | Add to `lib/bfo.ts` |
| `window.confirm` / `prompt` / `alert` | `useConfirm` / `usePrompt` from `components/ui/dialogs.tsx` |
| `Math.min(...arr)` / `Math.max(...arr)` on graph data | Manual `for` loop (avoids stack overflow at ~100k args) |
| Manual `Map`-cache for fetched data | TanStack Query (already configured) |
| Mutate Zustand for server data | Server state in TanStack Query, only UI state in Zustand |
| Add view-specific props to `VisNetwork` | Compose at the page level, keep `VisNetwork` generic |
| Import `vis-network/use-vis-network` from outside the folder | Import from `'@/components/graph/vis-network'` only |
| Return `undefined`-typed Zod fields without `?? defaultValue` | Default at the boundary in `lib/api/*` |

## 7. How to ask for an evolution

When requesting a change, fill out this template:

```
Goal:        <one sentence — what should be possible after the change>
Scope:       <which page / which file / which playbook>
Inputs:      <new props, new endpoints, new schema fields>
Outputs:     <what should the user see / be able to do>
Out of scope:<explicit non-goals>
Risk:        <data loss? canvas regression? auth?>
```

This maps directly to the playbooks above.

### Worked examples

| Request | Playbook(s) | Files touched |
|---------|-------------|---------------|
| "Add a `last modified` filter to the graph view dropdown" | A + D | `lib/schemas/graph.ts`, `lib/api/graph.ts`, `_hooks/use-graph-queries.ts`, `_components/FilterOptionDropdown.tsx` |
| "Bulk-delete selected individuals" | B | `lib/api/graph.ts`, `_hooks/use-graph-queries.ts`, page handler |
| "Show a different node shape per BFO bucket" | E (visual) | `vis-network/index.tsx` only |
| "Migrate the canvas to Sigma.js" | G | `vis-network/index.tsx`, `use-vis-network.ts` |
| "Add an 'analytics' tab to the ontology page" | F + A | `ontology/_components/types.ts`, new `OntologyAnalyticsView.tsx`, hooks |
| "The viewport jumps when I close the inspector" | E (caution) | Smoke-test first; then look at the `selectedNodeId` and `centerOnNodeId` effects in `use-vis-network.ts` |

If a request crosses 3+ playbooks, ask for a written plan first
(switch to plan mode) before coding.

## 8. Testing strategy

No tests exist yet. When you touch a file, add tests where the table says.

| Layer | Tool | What to test |
|-------|------|--------------|
| `lib/bfo.ts` | vitest | `resolveBucket` resolution; `wrapLabelTwoLines` edge cases |
| `lib/schemas/*.ts` | vitest | Accepts known good responses; rejects malformed |
| `lib/api/*.ts` | vitest + msw | Each function: happy path + Zod failure path |
| `vis-network/layout.ts` | vitest | `computeHierarchicalPositions` on tree fixtures (empty, single, deep, multi-root) |
| `_hooks/*.ts` | vitest + RTL | Cache key stability, mutation invalidations |
| `_components/*.tsx` | RTL | Render paths, user interactions |
| `vis-network/use-vis-network.ts` | manual + Playwright | Effect ordering is too vis-network-specific for unit tests; rely on smoke + E2E |
| Pages | Playwright | E2E flows: select graph, create individual, filter buckets, switch modes |

## 9. Quick command reference

```bash
cd libs/naas-abi/naas_abi/apps/nexus/apps/web

pnpm dev                          # local dev server
pnpm lint                         # next lint
./node_modules/.bin/tsc --noEmit  # typecheck
pnpm test                         # tests (when added)
```

## 10. References

- TanStack Query — https://tanstack.com/query/latest
- vis-network — https://visjs.github.io/vis-network/docs/network/
- Zod — https://zod.dev/
- BFO — https://basic-formal-ontology.org/
- Repo-wide conventions — `AGENTS.md` at repo root

---

**Owner**: anyone touching `graph/` or `ontology/`.
Update this file in the same PR as any structural change. If a playbook
becomes wrong, fix it here first — the README is the contract.
