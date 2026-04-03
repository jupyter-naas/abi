# OntologyPorts

## What it is
- Defines abstract “port” interfaces for ontology-based Named Entity Recognition (NER).
- Establishes contracts for:
  - An NER adapter that maps text to an ontology (provided as Turtle).
  - A service that performs NER using an internal adapter/configured ontology.

## Public API
### `class IOntologyNERPort(ABC)`
Interface for an ontology-aware NER adapter.

- `named_entity_recognition(self, input: str, ontology_str: str) -> rdflib.Graph`
  - Applies NER to `input` and maps recognized entities to ontology concepts defined in `ontology_str` (Turtle).
  - Returns an `rdflib.Graph` with mapped entities/relationships.

### `class IOntologyService(ABC)`
Interface for an ontology NER service.

- `named_entity_recognition(self, input: str) -> rdflib.Graph`
  - Applies NER to `input`.
  - Returns an `rdflib.Graph` with mapped entities/relationships.

## Configuration/Dependencies
- **Dependencies**
  - `rdflib.Graph` (return type for both ports)
  - `langchain_core.language_models.BaseChatModel` (typed private attribute in `IOntologyNERPort`)
- **Notes**
  - The module defines private typed attributes (`__chat_model`, `__ner_adaptor`) but does not expose constructors or setters; concrete implementations are responsible for wiring these.

## Usage
Minimal example implementing both interfaces:

```python
from rdflib import Graph
from naas_abi_core.services.ontology.OntologyPorts import IOntologyNERPort, IOntologyService

class DummyNER(IOntologyNERPort):
    def named_entity_recognition(self, input: str, ontology_str: str) -> Graph:
        return Graph()  # populate graph in a real implementation

class OntologyService(IOntologyService):
    def __init__(self, ner: IOntologyNERPort, ontology_str: str):
        self._ner = ner
        self._ontology_str = ontology_str

    def named_entity_recognition(self, input: str) -> Graph:
        return self._ner.named_entity_recognition(input, self._ontology_str)

svc = OntologyService(DummyNER(), ontology_str="")  # Turtle ontology string goes here
g = svc.named_entity_recognition("Some text")
print(len(g))
```

## Caveats
- These are **abstract interfaces only**; no concrete NER logic is provided.
- `IOntologyNERPort.named_entity_recognition` requires the ontology as a **Turtle string** (`ontology_str`).
