# build_user

## What it is
- Utility function that maps an expanded X v2 `User` object (`includes.users[]`) into RDF.
- Produces:
  - A rich `XUser` individual (profile fields)
  - Optionally an `XUserPublicMetrics` individual (when `public_metrics` is present)
- Designed to be called by an `XTweetGraphBuilder` implementation.

## Public API
- `build_user(builder: XTweetGraphBuilder, record: dict) -> tuple[XUser, rdflib.Graph]`
  - Converts a single user payload (`record`) into RDF.
  - Returns the created `XUser` object and a `rdflib.Graph` containing newly-added triples.
  - Uses `builder.label_exists(...)` and `builder.mark_existing(...)` to avoid emitting duplicate individuals by label.
  - Links the user to its metrics via `has_user_public_metrics` when metrics are present.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_marketplace.applications.x.ontologies.modules.XOntology`:
    - `XUser`
    - `XUserPublicMetrics`
  - `naas_abi_marketplace.applications.x.pipelines.utils._helpers.parse_dt` for `created_at` parsing
  - `rdflib.Graph`, `rdflib.URIRef`
  - A builder compatible with `XTweetGraphBuilder` (must provide at least):
    - `uri(class_name: str, identifier: str) -> str`
    - `label_exists(label: str, class_uri) -> bool`
    - `mark_existing(class_uri, label: str) -> None`

## Usage
```python
from naas_abi_marketplace.applications.x.pipelines.utils.build_user import build_user

# builder must be an instance compatible with XTweetGraphBuilder in your pipeline
user_record = {
    "id": "123",
    "username": "alice",
    "name": "Alice",
    "created_at": "2024-01-01T00:00:00.000Z",
    "public_metrics": {"followers_count": 10, "following_count": 5, "tweet_count": 3},
}

xuser, g = build_user(builder, user_record)
print(xuser)          # XUser instance
print(len(g))         # number of RDF triples emitted (may be 0 if deduped)
```

## Caveats
- `record["id"]` is required; missing it will raise a `KeyError`.
- For best results, call this before building tweets so the rich user individual is emitted before any minimal author stub (as noted in the function docstring).
- RDF emission is label-deduplicated via the builder; the returned graph may be empty if the label was already recorded.
