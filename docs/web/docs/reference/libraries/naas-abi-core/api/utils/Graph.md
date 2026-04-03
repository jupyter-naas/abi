# ABIGraph

## What it is
- A small utility wrapper around `rdflib.Graph` that:
  - Pre-binds common ontology namespaces (ABI, BFO, etc.).
  - Provides helpers to add OWL named individuals with labels, timestamps, and data properties.
  - Provides a helper to add “process”-like individuals with common BFO object-property relations.

## Public API

### Class: `ABIGraph(rdflib.Graph)`
A subclass of `rdflib.Graph` with additional convenience methods.

#### `__init__(**kwargs)`
- Initializes the RDF graph and binds namespaces:
  - `bfo`, `skos`, `abi`, `cco`, `xsd`, `time`

#### `add_data_properties(uri: URIRef, lang="en", **data_properties)`
- Adds ABI data properties (`ABI[<key>]`) to the given subject `uri` for each `key=value` in `data_properties`.
- Type handling:
  - `str` → language-tagged literal (trimmed)
  - `int` / `float` → literal with datatype `xsd:integer` (note: float is also typed as integer)
  - `datetime` → `xsd:dateTime` formatted as `%Y-%m-%dT%H:%M:%S%z` (adds UTC tzinfo if missing)
  - `date` → `xsd:date` formatted as `%Y-%m-%d`
- Always adds `dcterms:modified` with current timestamp (`xsd:dateTime`).

#### `add_individual(uri: URIRef, label, is_a, lang="en", skip_if_exists=True, **data_properties) -> URIRef`
- Adds (or reuses) an OWL named individual:
  - `(uri, rdf:type, owl:NamedIndividual)`
  - `(uri, rdf:type, is_a)`
  - `(uri, rdfs:label, label@lang)`
  - `(uri, dcterms:created, now()^^xsd:dateTime)`
- If `(uri, rdf:type, is_a)` already exists and `skip_if_exists=True`, it does not re-add the core type/label/created triples.
- Always calls `add_data_properties(...)` afterward (thus always updates `dcterms:modified`).

#### `add_individual_to_prefix(prefix: Namespace, uid: str, label: str, is_a: URIRef, lang="en", skip_if_exists=True, **data_properties) -> URIRef`
- Builds a URI from:
  - `uid` → uses the part after the last `:` (if present)
  - `type_name` → last segment of `is_a` after `/`
  - URI pattern: `"{prefix}{type_name}#{uid}"` (URL-quoted, `safe=":/#"`)
- Delegates to `add_individual(...)`.

#### `add_process(..., **data_properties) -> URIRef`
Creates an individual (via `add_individual_to_prefix`) and adds common BFO relations.

Parameters (selected):
- Identity:
  - `prefix: Namespace`, `uid: str`, `label: str`, `is_a: URIRef`, `lang="en"`, `skip_if_exists=True`
- Participants:
  - `participants: list[URIRef]` (default `[]`)
  - `participants_oprop` default `BFO.BFO_0000057`
  - `participants_oprop_inverse` default `BFO.BFO_0000056`
- Realizes:
  - `realizes: list[URIRef]` (default `[]`)
  - `realizes_oprop` default `BFO.BFO_0000055`
  - `realizes_oprop_inverse` default `BFO.BFO_0000054`
- Occurs in:
  - `occurs_in: list[URIRef]` (default `[]`)
  - `occurs_in_oprop` default `BFO.BFO_0000066`
  - `occurs_in_oprop_inverse` default `BFO.BFO_0000183`
- Concretizes:
  - `concretizes: list[URIRef]` (default `[]`)
  - `concretizes_oprop` default `BFO.BFO_0000058`
  - `concretizes_oprop_inverse` default `BFO.BFO_0000059`
- Regions (optional single URIRefs):
  - `temporal_region` with predicate `BFO.BFO_0000199`
  - `spatiotemporal_region` with predicate `BFO.BFO_0000200`

Behavior:
- Adds forward and inverse triples for list-based relations.
- Adds region triples only if provided.

## Configuration/Dependencies
- External libraries:
  - `rdflib`
  - `pytz`
- Uses `naas_abi_core.logger` for debug logging.
- Namespaces/constants defined in-module:
  - `BFO`, `ABI`, `TEST`, `TIME`, `XSD`, `CCO`, `DCTERMS`, and `URI_REGEX`.

## Usage

```python
from rdflib import URIRef
from naas_abi_core.utils.Graph import ABIGraph, ABI

g = ABIGraph()

person_class = ABI["Person"]
alice = URIRef("http://ontology.naas.ai/abi/Person#alice")

g.add_individual(
    uri=alice,
    label="Alice",
    is_a=person_class,
    description="Example person",
    age=30,
)

print(g.serialize(format="turtle"))
```

## Caveats
- `add_data_properties` types `float` values as `xsd:integer` (same as `int`).
- `add_process` (and some parameters) use mutable list defaults (e.g., `participants=[]`), which can lead to unintended sharing if those defaults are mutated externally.
- Datetime formatting uses `%z`; if timezone is missing it forces UTC, otherwise it preserves the provided tzinfo.
