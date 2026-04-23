# OntologyService

## What it is
- A thin service wrapper that exposes Named Entity Recognition (NER) against a provided ontology string.
- Delegates the actual NER work to an injected `IOntologyNERPort` adaptor and returns an `rdflib.Graph`.

## Public API
- `class OntologyService(IOntologyService)`
  - `__init__(ner_adaptor: IOntologyNERPort, ontology_str: str)`
    - Stores the NER adaptor and the ontology data (as a string) used for recognition.
  - `named_entity_recognition(input: str) -> rdflib.Graph`
    - Runs NER on `input` using the stored ontology string by delegating to the adaptor:
      - `ner_adaptor.named_entity_recognition(input, ontology_str)`

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.services.ontology.OntologyPorts.IOntologyNERPort` (injected adaptor)
  - `naas_abi_core.services.ontology.OntologyPorts.IOntologyService` (service interface)
  - `rdflib.Graph` (return type)

## Usage
```python
from rdflib import Graph
from naas_abi_core.services.ontology.OntologyService import OntologyService

# Minimal stub adaptor matching the expected port method signature
class DummyNERAdaptor:
    def named_entity_recognition(self, text: str, ontology_str: str) -> Graph:
        return Graph()  # replace with real extraction logic

ontology_str = "<your ontology as a string>"
service = OntologyService(ner_adaptor=DummyNERAdaptor(), ontology_str=ontology_str)

g = service.named_entity_recognition("Some input text")
print(type(g))  # <class 'rdflib.graph.Graph'>
```

## Caveats
- No validation is performed:
  - `ontology_str` is passed through as-is to the adaptor.
  - The returned `Graph` content and semantics depend entirely on the adaptor implementation.
