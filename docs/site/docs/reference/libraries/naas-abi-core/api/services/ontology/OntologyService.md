# OntologyService

## What it is
- A small service that implements `IOntologyService` and delegates Named Entity Recognition (NER) to an injected `IOntologyNERPort` adaptor using a provided ontology string.
- Returns results as an `rdflib.Graph`.

## Public API
- `class OntologyService(IOntologyService)`
  - `__init__(ner_adaptor: IOntologyNERPort, ontology_str: str)`
    - Stores the NER adaptor and the ontology serialized as a string.
  - `named_entity_recognition(input: str) -> rdflib.Graph`
    - Delegates to `ner_adaptor.named_entity_recognition(input, ontology_str)` and returns the resulting RDF graph.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.services.ontology.OntologyPorts`:
    - `IOntologyService` (implemented by this class)
    - `IOntologyNERPort` (required adaptor interface)
  - `rdflib.Graph` (return type)

## Usage
```python
from rdflib import Graph
from naas_abi_core.services.ontology.OntologyService import OntologyService

# Minimal stub adaptor matching the expected port method signature
class DummyNERAdaptor:
    def named_entity_recognition(self, text: str, ontology_str: str) -> Graph:
        return Graph()

service = OntologyService(
    ner_adaptor=DummyNERAdaptor(),
    ontology_str="...ontology content..."
)

g = service.named_entity_recognition("Find entities in this text.")
print(type(g))  # <class 'rdflib.graph.Graph'>
```

## Caveats
- `named_entity_recognition` behavior is entirely determined by the injected `IOntologyNERPort` implementation.
- `ontology_str` is passed through as-is; no validation or parsing is performed here.
