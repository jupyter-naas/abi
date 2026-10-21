# `build_tweet`

## What it is
- A utility function that maps an X (Twitter) API v2 **Tweet-shaped dict** into an **RDFLib `Graph`**.
- It is designed to be called from an `XTweetGraphBuilder` and delegates sub-entity construction back to that builder.

## Public API
- `build_tweet(builder, record, source_set_uri=None, *, referenced=False) -> rdflib.Graph`
  - Builds RDF triples for a single tweet and related entities.
  - Supports both:
    - **Matched tweets** (`referenced=False`): mapped as `x:Tweet` and linked via `x:isContainedInSearchResultSet`.
    - **Referenced/context tweets** (`referenced=True`): mapped as `x:ReferencedTweet` and linked via `x:isReferencedTweetOfSearchResultSet`, and additionally asserted as `rdf:type x:Tweet` (no reasoning assumed).

## Configuration/Dependencies
- Requires an `XTweetGraphBuilder` instance providing:
  - `uri(entity_type, id) -> str`
  - `prop(property_name) -> URIRef` (or URI string usable as `URIRef`)
  - `label_exists(label, class_uri) -> bool`
  - `mark_existing(class_uri, label) -> None`
  - Sub-entity helpers:
    - `_build_user(user_id, username=None) -> (XUser, Graph)`
    - `_build_metrics(tweet_id, metrics_payload) -> (…, Graph)`
    - `_build_language(lang_code, tweet_obj) -> (…, Graph) | None`
    - `_build_context_annotation(payload) -> (ContextAnnotation, Graph) | None`
    - `_build_url_entity(url_payload) -> (TweetURL, Graph) | None`
- Uses:
  - `rdflib.Graph`, `rdflib.URIRef`, `rdflib.namespace.RDF`
  - Ontology classes: `Tweet`, `ReferencedTweet`
  - Helpers: `parse_dt`, `first`

## Usage
```python
from naas_abi_marketplace.applications.x.pipelines.utils.build_tweet import build_tweet
from naas_abi_marketplace.applications.x.pipelines.utils._graph_builder import XTweetGraphBuilder

builder = XTweetGraphBuilder(...)
record = {
    "id": "123",
    "text": "Hello",
    "author_id": "42",
    "created_at": "2024-01-01T00:00:00.000Z",
}

g = build_tweet(builder, record, source_set_uri="https://example.org/set/1", referenced=False)
print(len(g))
```

## Caveats
- `record["id"]` is required (KeyError otherwise); `text` is expected (stored as `tweet_text`) but is accessed via `record.get("text")`.
- Tweet URL is reconstructed as `https://x.com/<author_id>/status/<id>` and is omitted if `author_id` is missing.
- Entities are read from both `entities` and `note_tweet.entities` and are deduplicated by:
  - mention `id` for mentions
  - generated URL-entity URI for URLs
- Deduplication of tweets relies on `builder.label_exists(tweet_label, Tweet._class_uri)` and uses the label format `Tweet <id>`.
