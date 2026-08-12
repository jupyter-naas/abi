# XOntology

## What it is
A set of Pydantic models representing X (formerly Twitter) domain entities with:
- RDF serialization via `rdflib` (`RDFEntity.rdf()`).
- Optional hydration from an RDF store using SPARQL (`RDFEntity.from_iri()`).
- Ontology-aligned class and property URIs (ABI/X namespaces) and basic namespace binding.

## Public API

### Base class: `RDFEntity`
Pydantic base model for RDF-backed entities.

- `set_namespace(namespace: str) -> None`  
  Set the base namespace used to auto-generate instance URIs when `_uri` is not provided.

- `set_query_executor(query_executor: Callable[[str], Iterable[object]] | None) -> None`  
  Register a SPARQL query executor used by `from_iri()`.

- `from_iri(iri: str, query_executor: Callable[[str], Iterable[object]] | None = None, graph_name: str | None = None) -> RDFEntity`  
  Load an instance by querying `<iri> ?p ?o` (optionally within `GRAPH <graph_name>`).  
  - Maps predicate URIs to model field names using class `_property_uris`.
  - Coerces literals to Python values; object properties become strings (IRIs).
  - Fills missing required fields with `None` or `[]` (for list fields).
  - If `label` exists and is missing, derives it from the IRI tail.
  - On validation errors, returns a permissively constructed model (`model_construct`).

- `rdf(subject_uri: str | None = None, visited: set[str] | None = None) -> rdflib.Graph`  
  Serialize the instance into RDF triples:
  - Adds `rdf:type` of the class (`_class_uri`) and `owl:NamedIndividual`.
  - Adds `rdfs:label` if `label` is present.
  - Serializes properties using `_property_uris`.
  - Object properties:
    - If value is another `RDFEntity`, recursively includes its triples (cycle-safe via `visited`).
    - If value is `str`/`URIRef`, emits an IRI reference.
  - Data properties emitted as literals.

### X domain entity models
All are Pydantic models inheriting an ABI/BFO base class plus `RDFEntity`, and define:
- `_class_uri`: RDF class IRI
- `_property_uris`: mapping of field name → predicate IRI
- `_object_properties`: set of fields treated as object properties in RDF

- `XPlatform(Site, RDFEntity)`  
  Fields: `label`, `created`, `creator`.

- `XUser(GenericallyDependentContinuant, RDFEntity)`  
  Data fields include (non-exhaustive): `author_id`, `username`, `user_display_name`, `user_description`, `user_location`, `user_url`, `user_created_at`, `verified`, `verified_type`, `protected`, `parody`, `is_identity_verified`, `subscription_type`, `profile_image_url`, `profile_banner_url`, `pinned_tweet_id`, `most_recent_tweet_id`, plus `label`, `created`, `creator`.  
  Object fields: `generically_depends_on`, `has_authored_tweet`, `has_user_public_metrics`, `is_concretized_by`, `is_x_user_account_of`.

- `Tweet(GenericallyDependentContinuant, RDFEntity)`  
  Data fields include (non-exhaustive): `tweet_id`, `tweet_text`, `full_text`, `tweet_created_at`, `edit_history_tweet_id`, `conversation_id`, `reply_settings`, `possibly_sensitive`, `paid_partnership`, `card_uri`, `url`, plus `label`, `created`, `creator`.  
  Object fields: `generically_depends_on`, `has_attached_media`, `has_context_annotation`, `has_language`, `has_public_metrics`, `has_url_entity`, `in_reply_to_user`, `is_authored_by`, `is_concretized_by`, `is_referenced_by_tweet`, `mentions_user`, `quotes_tweet`, `references_tweet`, `replies_to_tweet`, `retweets_tweet`, `tweeted_at`.

- `TweetPublicMetrics(GenericallyDependentContinuant, RDFEntity)`  
  Data fields: `retweet_count`, `reply_count`, `like_count`, `quote_count`, `bookmark_count`, `impression_count`, plus `label`, `created`, `creator`.  
  Object fields: `generically_depends_on`, `is_concretized_by`, `is_public_metrics_of`.

- `XUserPublicMetrics(GenericallyDependentContinuant, RDFEntity)`  
  Data fields: `followers_count`, `following_count`, `user_tweet_count`, `listed_count`, `user_like_count`, `user_media_count`, plus `label`, `created`, `creator`.  
  Object fields: `generically_depends_on`, `is_concretized_by`, `is_user_public_metrics_of`.

- `Media(GenericallyDependentContinuant, RDFEntity)`  
  Data fields: `media_key`, `media_type`, `media_url`, `preview_image_url`, `media_width`, `media_height`, `duration_ms`, plus `label`, `created`, `creator`.  
  Object fields: `generically_depends_on`, `is_attached_media_of`, `is_concretized_by`.

- `ContextAnnotation(GenericallyDependentContinuant, RDFEntity)`  
  Data fields: `context_domain_id`, `context_domain_name`, `context_domain_description`, `context_entity_id`, `context_entity_name`, `context_entity_description`, plus `label`, `created`, `creator`.  
  Object fields: `generically_depends_on`, `is_concretized_by`, `is_context_annotation_of`.

- `TweetURL(GenericallyDependentContinuant, RDFEntity)`  
  Data fields: `url`, `expanded_url`, `display_url`, `unwound_url`, `url_title`, `url_description`, plus `label`, `created`, `creator`.  
  Object fields: `generically_depends_on`, `is_concretized_by`, `is_url_entity_of`.

- `TweetLanguage(Quality, RDFEntity)`  
  Data fields: `language_code`, plus `label`, `created`, `creator`.  
  Object fields: `concretizes`, `inheresIn`, `inheres_in`, `participates_in`.

- `ReferencedTweet(Tweet, RDFEntity)`  
  Same field surface as `Tweet`, with a distinct `_class_uri` (`http://ontology.naas.ai/x/ReferencedTweet`).

## Configuration/Dependencies
- Dependencies:
  - `pydantic` (models, validation)
  - `rdflib` (Graph, URIRef, Literal, namespaces)
  - `naas_abi.ontologies.modules.ABIOntology` (ontology base classes/types used in annotations)
- Optional configuration:
  - `RDFEntity.set_namespace()` controls auto-generated `_uri`.
  - `RDFEntity.set_query_executor()` (or `from_iri(..., query_executor=...)`) is required to use `from_iri()`.

## Usage

### Create entities and serialize to RDF
```python
from naas_abi_marketplace.applications.x.ontologies.modules.XOntology import XUser, Tweet

user = XUser(author_id="123", username="alice", label="Alice")
tweet = Tweet(tweet_id="999", tweet_text="Hello", is_authored_by=[user])

g = tweet.rdf()
print(g.serialize(format="turtle"))
```

### Load an entity from an RDF store via SPARQL
```python
from naas_abi_marketplace.applications.x.ontologies.modules.XOntology import Tweet

def executor(sparql: str):
    # Must return an iterable of row-like objects with bindings for "p" and "o".
    # For example, this could be a wrapper around an rdflib SPARQL result set.
    raise NotImplementedError

Tweet.set_query_executor(executor)
tweet = Tweet.from_iri("http://ontology.naas.ai/abi/some-tweet-iri")
```

## Caveats
- `from_iri()` only considers predicates present in the model’s `_property_uris`; all others are ignored.
- For object properties, `from_iri()` coerces values to `str` IRIs (it does not automatically instantiate nested objects).
- `rdf()` recurses into related objects only when the property value is an object with both `.rdf()` and `._uri`. Cycles are handled via a `visited` set.
