# Partnership

## What it is
- A thin subclass of an imported `Partnership` process class, intended as an **action class** extension point.
- Defined in `naas_abi_marketplace.domains.intelligence.ontologies.classes.ontology_demo.abi.Partnership`.

## Public API
- `class Partnership(_Partnership)`
  - Inherits all behavior from `naas_abi_marketplace.domains.intelligence.ontologies.organizations.ontologies.processes.OrganizationAllianceProcess.Partnership`.
  - `actions(self)`
    - Placeholder method intended for custom logic.
    - Currently contains only a docstring and **does not implement any behavior**.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_marketplace.domains.intelligence.ontologies.organizations.ontologies.processes.OrganizationAllianceProcess.Partnership` (imported as `_Partnership`)

## Usage
```python
from naas_abi_marketplace.domains.intelligence.ontologies.classes.ontology_demo.abi.Partnership import Partnership

p = Partnership()
p.actions()  # No behavior implemented in this subclass
```

## Caveats
- `actions()` is a stub; calling it will effectively do nothing unless the parent class provides an implementation or you override it with actual logic.
