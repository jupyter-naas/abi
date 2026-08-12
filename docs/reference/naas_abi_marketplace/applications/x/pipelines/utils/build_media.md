# build_media

## What it is
Utilities to map an expanded X (Twitter) API v2 `Media` object (from `includes.media[]`) into RDF using the project’s `XOntology.Media` model.

## Public API
- `best_media_url(record: dict[str, Any]) -> str | None`
  - Returns the most appropriate direct media asset URL:
    - Uses `record["url"]` for photos when present.
    - For videos/animated GIFs, selects the highest-bitrate `video/mp4` variant from `record["variants"]`.
    - Returns `None` if no suitable URL is found.

- `build_media(builder: XTweetGraphBuilder, record: dict) -> tuple[Media, rdflib.Graph]`
  - Builds a `Media` ontology object and its RDF graph from a single media record.
  - Deduplicates by label/class via `builder.label_exists(...)`:
    - If already present, returns `(media, empty Graph())`.
    - Otherwise returns `(media, media.rdf())` and marks it as existing via `builder.mark_existing(...)`.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_marketplace.applications.x.ontologies.modules.XOntology.Media`
  - `rdflib.Graph`
  - A builder implementing the expected `XTweetGraphBuilder` interface (imported only for type checking), with at least:
    - `uri(entity_type: str, key: str) -> Any`
    - `label_exists(label: str, class_uri: Any) -> bool`
    - `mark_existing(class_uri: Any, label: str) -> None`

## Usage
```python
from naas_abi_marketplace.applications.x.pipelines.utils.build_media import build_media

# builder must be an XTweetGraphBuilder-compatible instance
record = {
    "media_key": "3_123",
    "type": "video",
    "variants": [
        {"content_type": "video/mp4", "bit_rate": 256000, "url": "https://cdn/x-low.mp4"},
        {"content_type": "video/mp4", "bit_rate": 832000, "url": "https://cdn/x-high.mp4"},
    ],
    "preview_image_url": "https://cdn/preview.jpg",
    "width": 1280,
    "height": 720,
    "duration_ms": 12000,
}

media_obj, media_graph = build_media(builder, record)
```

## Caveats
- `build_media` requires `record["media_key"]`; missing it will raise `KeyError`.
- `best_media_url` only considers `video/mp4` variants and picks the maximum `bit_rate` (missing/falsey `bit_rate` is treated as `0`).
- When the label already exists for `Media._class_uri`, `build_media` returns an empty RDF graph (no triples).
