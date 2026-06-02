# Ontology Service — AGENTS.md

> Scope: `libs/naas-abi-core/naas_abi_core/services/ontology/`. Canonical reference for agents.

## Purpose

Named Entity Recognition over unstructured text, mapped against an RDF/OWL ontology. Output is an RDFLib `Graph` of recognised entities.

**Not** a triple store — this service only does extraction. For storage / SPARQL, see `triple_store/`.

## Files

```
ontology/
├── OntologyPorts.py                                   # IOntologyNERPort, IOntologyService
├── OntologyService.py                                 # public service
└── adaptors/secondary/
    └── OntologyService_SecondaryAdaptor_NERPort.py    # LangChain ChatModel backend
```

## Port (`OntologyPorts.py`)

```python
class IOntologyNERPort:
    def named_entity_recognition(input: str, ontology_str: str) -> Graph

class IOntologyService:
    def named_entity_recognition(input: str) -> Graph
```

## Service API (`OntologyService.py`)

```python
OntologyService(ner_adaptor: IOntologyNERPort, ontology_str: str)

named_entity_recognition(input: str) -> Graph
# Applies NER on `input` against the bound ontology, returns mapped RDF Graph.
```

## Available Adapters

| Adapter | Backend / Notes |
|---|---|
| `OntologyService_SecondaryAdaptor_NERPort` | LangChain `BaseChatModel`. Prompts the model for Turtle output, parses it into an RDFLib Graph |

## Instantiation

No factory file:

```python
from naas_abi_core.services.ontology.OntologyService import OntologyService
from naas_abi_core.services.ontology.adaptors.secondary.OntologyService_SecondaryAdaptor_NERPort import (
    OntologyService_SecondaryAdaptor_NERPort,
)

ner = OntologyService_SecondaryAdaptor_NERPort(chat_model=my_chat_model)
service = OntologyService(ner_adaptor=ner, ontology_str=open("schema.ttl").read())
graph = service.named_entity_recognition("Bob met Alice in Paris.")
```

## Tests

No tests in this directory. Related downstream coverage:

```bash
uv run pytest libs/naas-abi-marketplace/naas_abi_marketplace/domains/ontology_engineer/
```

If you change `OntologyService` semantics, add a `OntologyService_test.py` next to it.

## Adding a new adapter

1. Implement `IOntologyNERPort.named_entity_recognition` in `adaptors/secondary/<Name>.py`.
2. Return a valid `rdflib.Graph` aligned with the supplied ontology.
3. Add an `<Name>_test.py` covering a non-trivial input → output sample.
