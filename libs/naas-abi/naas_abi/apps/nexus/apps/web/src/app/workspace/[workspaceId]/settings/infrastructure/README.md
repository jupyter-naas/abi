# ABI infrastructure

Workspace Settings → Infrastructure provides a 3D map of the shared ABI Python
codebase. It inherits the existing workspace authentication and
`settings.workspace` feature guard. It does not query workspace secrets, send
source to a model, or represent a workspace's actual deployment.

- Architecture and Inspector live in the shared Nexus feature column.
- File exports the snapshot; View contains fit, zoom, decomposition and dependency controls.
- Click a layer (in the map or sidebar) to isolate it and animate to a fitted,
  face-on view. Clicking it again restores framing after orbiting.
- Drag to orbit, scroll or use +/− to zoom; Fit view restores the current framing.
- Decompose separates the component tiles from their plate.
- Dependencies draws links between visible components. Selecting a component
  filters these lines and lists directed **Depends on** and **Used by** links in
  the inspector, including relationships to other layers.
- Every selection is also available through ordinary keyboard-accessible buttons.
  The inspector remains usable when WebGL is unavailable.

## Refresh the source snapshot

From the Nexus directory, with Python and `uv` installed:

```sh
python3 scripts/build_abi_architecture.py
```

The script resolves the parent ABI `libs` directory automatically; use `--libs`
for another checkout. It stages only Python source in a temporary directory and
runs pinned `graphifyy==0.9.57` with `--code-only --no-cluster`. Graphify's AST pass
runs locally. The first invocation may download the extractor from PyPI.
`--graph path/to/graph.json` can reuse a graph extracted from the **same corpus**.
The output contains relative file paths and aggregate metadata, never source
contents or environment configuration. Commit the generated JSON with changes
that should appear in the map. It is a build-time snapshot, not live indexing.

Layers follow deterministic package/service boundaries. Component dependencies
aggregate Graphify `EXTRACTED` imports, calls, references, uses, inheritance and
re-exports with both endpoints resolved to different components. Inferred and
unresolved links are excluded. The raw graph totals include internal symbols and
relationships, so they are larger than the component-level graph.

Files, physical lines (including blanks/comments), classes and functions come
from Python's AST/source scan. Test files are counted separately, not executed;
this count is not coverage. Migrations are excluded. Dynamic imports, runtime
registration and deployment wiring can be absent from the graph. Ontology TTL,
frontend TypeScript, running service health, latency, usage and costs are outside
this snapshot's scope.

## Checks

From Nexus:

```sh
python3 -m unittest discover -s scripts -p '*_test.py'
cd apps/web
pnpm typecheck
pnpm dlx vitest@3.2.4 run 'src/app/workspace/[workspaceId]/settings/infrastructure'
```

Camera tests check that both plane dimensions fit across portrait/landscape
viewports, including decomposition. Generator tests cover adapter separation,
metrics, and exclusion of inferred, unresolved and self dependencies.

## Layers and diagram views

Use the visible Layers / Diagram switch or the View menu. The diagram always shows
all components and directed dependencies; selecting a component highlights its
neighborhood without hiding cross-layer connections. Drag to pan and scroll to
zoom. The same sidebar inspector works in both views.

Hover close to a visible dependency in Layers view, or hover/focus a link in Diagram
view, for source → destination, relationship types and extracted counts. Enable
View → Dependencies to show links in Layers view. Diagram layout uses five labeled architectural columns with fixed card spacing.
Orthogonal links use row gaps and column gutters; layer/component selection hides
unrelated links. Layout is deterministic and derived from the existing snapshot; it does not add inferred relationships.
