# OntologyService_SecondaryAdaptor_NERPort

## What it is
- A secondary adaptor implementing `IOntologyNERPort` that performs Named Entity Recognition (NER) by:
  - Prompting a LangChain `BaseChatModel` with input text and an ontology (Turtle).
  - Expecting the model to return Turtle.
  - Parsing the returned Turtle into an `rdflib.Graph`.

## Public API
- **Class: `OntologyService_SecondaryAdaptor_NERPort(IOntologyNERPort)`**
  - `__init__(chat_model: BaseChatModel)`
    - Stores the provided LangChain chat model instance.
  - `named_entity_recognition(input: str, ontology_str: str) -> rdflib.Graph`
    - Sends a system+human message prompt to the model.
    - Sanitizes response by removing ```turtle and ``` fences.
    - Parses the Turtle into an RDFLib `Graph` and returns it.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_core.language_models.BaseChatModel`
  - `langchain_core.messages.SystemMessage`, `HumanMessage`
  - `rdflib.Graph`
  - `naas_abi_core.services.ontology.OntologyPorts.IOntologyNERPort`
- **Model contract**
  - `chat_model.invoke(messages)` must return an object with a `.content` attribute of type `str` containing Turtle.

## Usage
```python
from rdflib import Graph
from langchain_core.language_models import BaseChatModel
from naas_abi_core.services.ontology.adaptors.secondary.OntologyService_SecondaryAdaptor_NERPort import (
    OntologyService_SecondaryAdaptor_NERPort,
)

# You must provide a concrete BaseChatModel implementation.
chat_model: BaseChatModel = ...

adaptor = OntologyService_SecondaryAdaptor_NERPort(chat_model)

text = "Alice works at Acme Corp."
ontology_ttl = """
@prefix ex: <http://example.org/> .
ex:Person a <http://www.w3.org/2002/07/owl#Class> .
ex:Organization a <http://www.w3.org/2002/07/owl#Class> .
"""

g: Graph = adaptor.named_entity_recognition(text, ontology_ttl)
print(len(g))  # number of parsed triples
```

## Caveats
- The method asserts `response.content` is a `str`; non-string content will raise an `AssertionError`.
- If the model returns invalid Turtle (or missing prefixes), `rdflib.Graph().parse(..., format="turtle")` will raise a parsing exception.
- Only removes Markdown fences ` ```turtle ` and ` ``` `; other formatting artifacts are not handled.
