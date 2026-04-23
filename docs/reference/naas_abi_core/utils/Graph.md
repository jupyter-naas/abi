# ABIGraph

## What it is
- `ABIGraph` is a thin wrapper around `rdflib.Graph` that:
  - Pre-binds common namespaces used by the NAAS ABI ontology.
  - Provides helpers to add OWL individuals (NamedIndividuals) with labels, timestamps, and simple data properties.
  - Provides a helper to model “process”-like individuals with common object-property links (participants, realizes, occurs in, etc.).

## Public API

### Module constants
- `BFO`, `ABI`, `TEST`, `TIME`, `XSD`, `CCO`, `DCTERMS` (`rdflib.Namespace`)
  - Common namespaces used in the graph.
- `URI_REGEX` (`str`)
  - Regex string for matching NAAS ontology URIs of the form `http://ontology.naas.ai/.../<uuid>`.

### Class `ABIGraph(rdflib.Graph)`
#### `__init__(**kwargs)`
- Initializes an RDFLib graph and binds prefixes:
  - `bfo`, `skos`, `abi`, `cco`, `xsd`, `time`.

#### `add_data_properties(uri: URIRef, lang="en", **data_properties)`
- Adds ABI data-property triples to `uri` based on Python value types:
  - `str` → `Literal(value.strip(), lang=lang)`
  - `int`/`float` → `Literal(value, datatype=XSD.integer)`
  - `datetime` → `Literal(value.strftime("%Y-%m-%dT%H:%M:%S%z"), datatype=XSD.dateTime)`
    - If `tzinfo` is missing, UTC is applied.
  - `date` → `Literal(value.strftime("%Y-%m-%d"), datatype=XSD.date)`
- Always adds a `dcterms:modified` timestamp (as `xsd:dateTime`).

#### `add_individual(uri: URIRef, label, is_a, lang="en", skip_if_exists=True, **data_properties) -> URIRef`
- Ensures `uri` is represented as:
  - `rdf:type owl:NamedIndividual`
  - `rdf:type is_a`
  - `rdfs:label` with language tag
  - `dcterms:created` timestamp (as `xsd:dateTime`)
- If `(uri, rdf:type, is_a)` already exists and `skip_if_exists=True`, it does not re-add the core individual triples (but still adds/updates data properties, including `dcterms:modified`).
- Returns `uri`.

#### `add_individual_to_prefix(prefix: Namespace, uid: str, label: str, is_a: URIRef, lang="en", skip_if_exists=True, **data_properties) -> URIRef`
- Constructs a URI of the form:  
  `"{prefix}{type_name}#{uid}"` where `type_name` is the last path segment of `is_a`.
- URL-quotes the resulting URI (keeping `:/#` safe).
- Delegates to `add_individual(...)`.
- Returns the created/ensured `URIRef`.

#### `add_process(..., **data_properties) -> URIRef`
- Creates/ensures an individual (via `add_individual_to_prefix`) and adds common object-property links:
  - `participants` with forward `participants_oprop` (default `BFO.BFO_0000057`) and inverse `participants_oprop_inverse` (default `BFO.BFO_0000056`)
  - `realizes` with forward `realizes_oprop` (default `BFO.BFO_0000055`) and inverse `realizes_oprop_inverse` (default `BFO.BFO_0000054`)
  - `occurs_in` with forward `occurs_in_oprop` (default `BFO.BFO_0000066`) and inverse `occurs_in_oprop_inverse` (default `BFO.BFO_0000183`)
  - `concretizes` with forward `concretizes_oprop` (default `BFO.BFO_0000058`) and inverse `concretizes_oprop_inverse` (default `BFO.BFO_0000059`)
  - Optional:
    - `temporal_region` via `temporal_region_oprop` (default `BFO.BFO_0000199`)
    - `spatiotemporal_region` via `spatiotemporal_region_oprop` (default `BFO.BFO_0000200`)
- Returns the process individual `URIRef`.

## Configuration/Dependencies
- Requires:
  - `rdflib`
  - `pytz`
- Uses `naas_abi_core.logger` for debug logging.
- Datatype IRIs are taken from the `XSD` namespace declared in this module (`http://www.w3.org/2001/XMLSchema#`).

## Usage
```python
from rdflib import URIRef
from naas_abi_core.utils.Graph import ABIGraph, ABI

g = ABIGraph()

person_class = ABI["Person"]
person_uri = URIRef("http://ontology.naas.ai/abi/Person#123")

g.add_individual(
    uri=person_uri,
    label="Alice",
    is_a=person_class,
    description="Example person",
    age=30,
)

print(len(g))  # number of triples
```

## Caveats
- `add_data_properties` maps both `int` and `float` to `xsd:integer` (not `xsd:decimal`/`xsd:double`).
- Timestamps are formatted with `strftime("%Y-%m-%dT%H:%M:%S%z")`; `datetime.now()` is naive here, so `%z` may be empty depending on environment.
- `add_process` uses mutable default arguments (`participants=[]`, `realizes=[]`, etc.). Avoid mutating those lists in-place; pass your own lists instead.
