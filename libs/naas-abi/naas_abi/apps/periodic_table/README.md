# Periodic Table of Software

Interactive pyvis graph of the ABI Periodic Table ontology.

Registered like Nexus Analytics: a folder under `naas_abi/apps/` with `manifest.json`. The catalog URL is bundled HTML (`html:periodic_table_graph.html`), which Nexus rewrites to `/app-html/naas_abi/periodic_table/periodic_table_graph.html` and can iframe later. This pass does not add a first-party Nexus React page.

## Ontology

Loads `naas_abi.ontologies.periodic_table` (catalog TTL plus BFO/ABI labels). Named graph: `http://ontology.naas.ai/graph/abi-periodic-table`.

## Standalone

```bash
uv run python -m naas_abi.apps.periodic_table
```

Opens http://127.0.0.1:5007/periodic_table_graph.html

Regenerate the bundled HTML after ontology edits:

```bash
uv run python -c "from naas_abi.apps.periodic_table.graph import write_graph_html; print(write_graph_html())"
```

Optional HoloViz Panel grid (needs `panel`):

```bash
uv run python -c "from naas_abi.apps.periodic_table.app import serve; serve()"
```

## Nexus catalog

`naas_abi` is already loaded. Restart the API so discovery picks up the new manifest. Enable the app per workspace in the Apps catalog. Embed uses the existing `/app-html/` iframe path; no new embed mechanism.
