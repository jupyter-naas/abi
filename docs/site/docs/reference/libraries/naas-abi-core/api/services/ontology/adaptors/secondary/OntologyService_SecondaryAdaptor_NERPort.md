# OntologyService_SecondaryAdaptor_NERPort

## What it is
- A secondary adaptor implementing `IOntologyNERPort` that performs Named Entity Recognition (NER) by prompting a LangChain chat model to output RDF in Turtle format, then parses it into an `rdflib.Graph`.

## Public API
- **Class: `OntologyService_SecondaryAdaptor_NERPort(IOntologyNERPort)`**
  - **`__init__(chat_model: BaseChatModel)`**
    - Stores the provided LangChain chat model used to run the NER prompt.
  - **`named_entity_recognition(input: str, ontology_str: str) -> rdflib.Graph`**
    - Sends a system prompt containing the ontology (Turtle) plus the unstructured input text to the chat model.
    - Expects the model to return Turtle content; strips optional ```turtle / ``` fences.
    - Parses the Turtle into an `rdflib.Graph` and returns it.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_core.language_models.BaseChatModel` (must support `.invoke(messages)`)
  - `langchain_core.messages.SystemMessage`, `HumanMessage`
  - `rdflib.Graph` (used to parse Turtle output)
  - `naas_abi_core.services.ontology.OntologyPorts.IOntologyNERPort` (interface/base port)

- **Chat model requirement**
  - The provided `chat_model` must return an object with a `.content` attribute that is a `str` containing valid Turtle.

## Usage
```python
from rdflib import Graph
from langchain_core.language_models import BaseChatModel

from naas_abi_core.services.ontology.adaptors.secondary.OntologyService_SecondaryAdaptor_NERPort import (
    OntologyService_SecondaryAdaptor_NERPort,
)

# Provide a concrete LangChain chat model that implements BaseChatModel
chat_model: BaseChatModel = ...

adaptor = OntologyService_SecondaryAdaptor_NERPort(chat_model)

ontology_ttl = """
@prefix ex: <http://example.org/> .
ex:Person a ex:Concept .
"""

text = "Alice works at ExampleCorp."

g: Graph = adaptor.named_entity_recognition(text, ontology_ttl)
print(len(g))  # number of parsed RDF triples
```

## Caveats
- The method **asserts** `response.content` is a `str`; non-string content will raise `AssertionError`.
- If the model returns invalid Turtle (or missing prefixes), `rdflib.Graph().parse(...)` will raise a parsing exception.
- Only basic sanitization is performed (removes ```turtle and ```); other formatting issues are not handled.
