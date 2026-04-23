# ontology_interface

## What it is
A Streamlit app that discovers Turtle (`.ttl`) files in the repository, parses them with `rdflib`, and renders an interactive knowledge-graph visualization using NetworkX + PyVis (VisJS).

## Public API
This module is primarily a Streamlit script (executed on import/run). It exposes these reusable functions:

- `discover_ttl_files() -> list[dict]`
  - Recursively finds `*.ttl` files under the project root (relative to this file), skipping hidden paths.
  - Returns file metadata: `path`, `full_path`, `name`, `module`, `category`, `size`.

- `get_module_from_path(path: str) -> str`
  - Extracts the module name from a path containing `modules/<module>/...`; otherwise returns `"core"`.

- `get_category_from_path(path: str) -> str`
  - Categorizes TTL files based on path patterns:
    - `"domain-experts"` → `Domain Experts`
    - `"core/modules"` → `Core Modules`
    - `"marketplace"` → `Marketplace`
    - else → `Other`

- `parse_ttl_file(file_path: str) -> dict` *(cached via `@st.cache_data`)*
  - Parses a Turtle file and returns:
    - `triples`: list of dicts with `subject`, `predicate`, `object`, `subject_type`, `object_type`
    - `namespaces`: namespace prefix map
    - `count`: triple count
  - On error, returns `error` plus empty results.

- `get_node_type(node) -> str`
  - Classifies RDF nodes: `URI`, `Literal`, `BlankNode`, or `Unknown`.

- `create_knowledge_graph(selected_files: list[dict], max_nodes: int = 500) -> tuple`
  - Builds a NetworkX graph from parsed triples (skips triples whose object is a `Literal`).
  - Limits processing roughly to `max_nodes * 3` triples and stops when nodes exceed `max_nodes`.
  - Returns `(net, file_stats, node_count, edge_count)` where:
    - `net` is a `pyvis.network.Network` ready to export to HTML
    - `file_stats` maps file name → `{triples, category}`

- `get_short_name(uri: str) -> str`
  - Shortens a URI by taking the fragment after `#` or the last path segment after `/`.

- `get_node_color(uri: str, category_colors: dict) -> str`
  - Returns a hex color based on simple substring checks for namespaces (e.g., `abi:`, `rdf:`, `owl:`).
  - Note: `category_colors` is accepted but not used in the current implementation.

## Configuration/Dependencies
- Runtime environment:
  - `streamlit`
  - `pandas`
  - `rdflib`
  - `networkx`
  - `pyvis`
- Filesystem assumptions:
  - The “project root” is computed as `Path(__file__).parent.parent.parent.parent` and scanned recursively for `*.ttl`.
  - Optional `SOP.md` is expected alongside this script for the SOP page.
- Streamlit settings:
  - `st.set_page_config(page_title="ABI Ontology Explorer", layout="wide")`
  - Session keys used: `ontology_data`, `selected_files`, `graph_html`, `page`.

## Usage
### Run as a Streamlit app
From the repository context, run Streamlit pointing at this file:

```bash
streamlit run libs/naas-abi-marketplace/naas_abi_marketplace/__demo__/apps/ontology-mode/ontology_interface.py
```

### Reuse core functions (non-UI)
You can import and call functions, but note that importing executes Streamlit UI code in this module.

```python
from naas_abi_marketplace.__demo__.apps.ontology_mode.ontology_interface import (
    discover_ttl_files, create_knowledge_graph
)

ttl_files = discover_ttl_files()
net, file_stats, node_count, edge_count = create_knowledge_graph(ttl_files[:2], max_nodes=100)
net.save_graph("graph.html")
print(node_count, edge_count, file_stats)
```

## Caveats
- This file is a Streamlit script; importing it will run UI setup and page logic.
- Visualization omits triples where the object is a `Literal` (for a “cleaner” graph).
- Graph size is bounded by `max_nodes` and an internal triple processing limit (`max_nodes * 3`), which may truncate larger ontologies.
- `Network(directed=True)` is set, but the underlying NetworkX graph is `nx.Graph()` (undirected), so directionality is not represented in the NetworkX structure.
