# `mappings` (`COLORS_NODES`)

## What it is
A module that defines a single dictionary mapping ontology term URIs (strings) to color values (CSS-like strings). Intended for consistent node coloring in graph/visualization contexts.

## Public API
- `COLORS_NODES: dict[str, str]`
  - Maps an ontology class/term URI to a color value.
  - Values are color strings such as hex codes (e.g., `"#f61685"`) or named colors (e.g., `"white"`, `"grey"`, `"black"`).

## Configuration/Dependencies
- No external dependencies.
- No configuration required.

## Usage
```python
from naas_abi_marketplace.applications.naas.mappings import COLORS_NODES

uri = "http://ontology.naas.ai/abi/Product"
color = COLORS_NODES.get(uri, "#000000")  # fallback color if unknown URI
print(color)
```

## Caveats
- Keys are exact URI strings; lookups are case- and character-sensitive.
- Some values are named colors (e.g., `"white"`, `"grey"`, `"black"`) instead of hex codes; ensure your renderer supports both formats.
