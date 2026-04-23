# Processor

## What it is
- A thin subclass of `naas_abi_marketplace.domains.document.ontologies.modules.DocumentOntology.Processor`.
- Intended as a hook point to implement custom processor “actions” logic.

## Public API
- `class Processor(_Processor)`
  - Extends the base `Processor` from `DocumentOntology`.
  - `actions(self)`
    - Placeholder method intended to contain the action logic.
    - Currently does nothing (`pass`).

## Configuration/Dependencies
- Depends on:
  - `naas_abi_marketplace.domains.document.ontologies.modules.DocumentOntology.Processor` (imported as `_Processor`)

## Usage
```python
from naas_abi_marketplace.domains.document.ontologies.classes.ontology_naas_ai.abi.document.Processor import Processor

class MyProcessor(Processor):
    def actions(self):
        # implement your logic here
        print("Running actions")

p = MyProcessor()
p.actions()
```

## Caveats
- `Processor.actions()` is not implemented in this file; calling it on `Processor` will perform no work.
- Any runtime behavior beyond `actions()` comes from the inherited `_Processor` implementation.
