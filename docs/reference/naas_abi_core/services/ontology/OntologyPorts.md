# OntologyPorts

## What it is
Abstract port/interface definitions for an ontology-oriented Named Entity Recognition (NER) workflow. These interfaces describe how to map entities from text to ontology concepts and return results as an RDFLib `Graph`.

## Public API
- `class IOntologyNERPort(ABC)`
  - Purpose: Adapter/port interface for performing NER given raw text and an ontology (Turtle string).
  - `named_entity_recognition(input: str, ontology_str: str) -> rdflib.Graph`
    - Maps entities in `input` against `ontology_str` and returns an RDF graph.

- `class IOntologyService(ABC)`
  - Purpose: Service interface that performs NER using an underlying NER port/adaptor and a configured ontology (details not defined here).
  - `named_entity_recognition(input: str) -> rdflib.Graph`
    - Maps entities in `input` and returns an RDF graph.

## Configuration/Dependencies
- Depends on:
  - `rdflib.Graph` (return type)
  - `langchain_core.language_models.BaseChatModel` (type hint for an internal chat model attribute)
  - `abc.ABC`, `abc.abstractmethod` (abstract interfaces)

Note: Private attributes (`__chat_model`, `__ner_adaptor`) are declared for typing purposes; no initialization or wiring is implemented in this module.

## Usage
Implement the interfaces in concrete classes:

```python
from rdflib import Graph
from naas_abi_core.services.ontology.OntologyPorts import IOntologyNERPort, IOntologyService

class SimpleNER(IOntologyNERPort):
    def named_entity_recognition(self, input: str, ontology_str: str) -> Graph:
        g = Graph()
        # Your NER + ontology mapping implementation here
        return g

class OntologyService(IOntologyService):
    def __init__(self, ner: IOntologyNERPort, ontology_str: str):
        self._ner = ner
        self._ontology_str = ontology_str

    def named_entity_recognition(self, input: str) -> Graph:
        return self._ner.named_entity_recognition(input, self._ontology_str)

svc = OntologyService(SimpleNER(), ontology_str="")  # Turtle string goes here
graph = svc.named_entity_recognition("Some input text")
```

## Caveats
- These are abstract interfaces only; calling the abstract methods requires concrete implementations.
- No validation is performed on `ontology_str` or the returned `Graph` in this module.
