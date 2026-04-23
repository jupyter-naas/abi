# `mappings` (`COLORS_NODES`)

## What it is
A module-level mapping of ontology term URIs to color values (hex strings or named colors). Intended for consistent node coloring (e.g., in graph/visualization contexts).

## Public API
- `COLORS_NODES: dict[str, str]`
  - Maps an ontology class/term URI to a color value.
  - Values are CSS-like color strings (e.g., `"#f61685"`, `"white"`, `"grey"`, `"black"`).

## Configuration/Dependencies
- No external dependencies.
- No configuration required.

## Usage
```python
from naas_abi_marketplace.applications.naas.mappings import COLORS_NODES

uri = "http://ontology.naas.ai/abi/Product"
color = COLORS_NODES.get(uri, "#000000")  # fallback if unknown
print(uri, color)
```

## Caveats
- Keys are exact URI strings; lookups are case- and character-sensitive.
- Some values are named colors (e.g., `"white"`, `"grey"`, `"black"`) rather than hex codes; ensure your renderer supports both.
