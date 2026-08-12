# ontology_interface

## What it is
A Streamlit app that:
- Discovers Turtle (`.ttl`) files under the project root.
- Parses selected files with `rdflib`.
- Builds a graph (NetworkX) and renders an interactive visualization using PyVis/VisJS.

The module is primarily a Streamlit script; UI code runs at import/run time.

## Public API
Reusable functions defined in this module:

- `discover_ttl_files() -> list[dict]`
  - Recursively finds `*.ttl` under the computed project root (`Path(__file__).parent.parent.parent.parent`).
  - Skips any hidden path segments (parts starting with `.`).
  - Returns sorted metadata dicts: `path`, `full_path`, `name`, `module`, `category`, `size`.

- `get_module_from_path(path: str) -> str`
  - Extracts module name from paths containing `modules/<module>/...`.
  - Returns `"core"` if no module segment is found.

- `get_category_from_path(path: str) -> str`
  - Categorizes a TTL file by substring checks:
    - contains `"domain-experts"` → `Domain Experts`
    - contains `"core/modules"` → `Core Modules`
    - contains `"marketplace"` → `Marketplace`
    - otherwise → `Other`

- `parse_ttl_file(file_path: str) -> dict` (cached via `@st.cache_data`)
  - Parses a Turtle file into:
    - `triples`: list of `{subject, predicate, object, subject_type, object_type}`
    - `namespaces`: `dict` of parsed namespaces (`Graph().namespaces()`)
    - `count`: number of triples
  - On exception returns: `error`, and empty `triples/namespaces`, `count=0`.

- `get_node_type(node) -> str`
  - Classifies RDF nodes as: `URI`, `Literal`, `BlankNode`, or `Unknown`.

- `create_knowledge_graph(selected_files: list[dict], max_nodes: int = 500) -> tuple`
  - Parses selected TTL files (using `parse_ttl_file`) until a rough triple limit (`max_nodes * 3`).
  - Builds a NetworkX `nx.Graph()` from triples:
    - Skips triples where `object_type == "Literal"`.
    - Adds edges with `label=get_short_name(predicate)`.
    - Stops adding when node count exceeds `max_nodes`.
  - Produces a `pyvis.network.Network(directed=True)` with physics options and node styling.
  - Returns `(net, file_stats, node_count, edge_count)` where:
    - `file_stats[file_name] = {"triples": parsed_count, "category": file_category}`

- `get_short_name(uri: str) -> str`
  - Shortens by fragment (`#...`) or last path segment (`/...`), else truncates to 50 chars.

- `get_node_color(uri: str, category_colors: dict) -> str`
  - Returns a hex color based on substring matches in the URI:
    - contains `abi:` or `abi.com` → red
    - contains `rdfs:` or `rdf:` → teal
    - contains `owl:` → blue
    - contains `foaf:` → green
    - otherwise → light salmon
  - Note: `category_colors` is accepted but not used.

## Configuration/Dependencies
- Python packages:
  - `streamlit`, `pandas`, `rdflib`, `networkx`, `pyvis`
- Filesystem assumptions:
  - Project root is computed relative to this file and scanned recursively for `*.ttl`.
  - Optional `SOP.md` is expected in the same directory for the SOP page.
- Streamlit behavior:
  - `st.set_page_config(page_title="ABI Ontology Explorer", page_icon="🕸️", layout="wide")`
  - Session state keys used: `ontology_data`, `selected_files`, `graph_html`, `page`

## Usage

### Run the Streamlit app
```bash
streamlit run libs/naas-abi-marketplace/naas_abi_marketplace/__demo__/apps/ontology-mode/ontology_interface.py
```

### Reuse functions (non-UI)
Importing this module will execute Streamlit UI code; reuse is best done in a Streamlit context.

```python
from naas_abi_marketplace.__demo__.apps.ontology_mode.ontology_interface import (
    discover_ttl_files,
    create_knowledge_graph,
)

ttl_files = discover_ttl_files()
net, file_stats, node_count, edge_count = create_knowledge_graph(ttl_files[:2], max_nodes=100)

net.save_graph("graph.html")
print(node_count, edge_count)
print(file_stats)
```

## Caveats
- This is a Streamlit script: importing it triggers UI initialization and page logic.
- Literal objects are excluded from the visualization (`object_type == "Literal"`).
- Graph size is bounded:
  - Only up to ~`max_nodes * 3` triples are processed.
  - Node insertion stops when node count exceeds `max_nodes`.
- Directionality mismatch:
  - PyVis network is created with `directed=True`, but the underlying NetworkX graph is `nx.Graph()` (undirected).
