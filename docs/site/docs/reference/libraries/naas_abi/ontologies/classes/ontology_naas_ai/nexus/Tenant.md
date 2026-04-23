# Tenant

## What it is
- A thin subclass of `naas_abi.ontologies.modules.NexusPlatformOntology.Tenant`.
- Provides a placeholder `actions()` method intended to be overridden with custom logic.

## Public API
- **Class `Tenant`**
  - Inherits from: `naas_abi.ontologies.modules.NexusPlatformOntology.Tenant`
  - **Method `actions(self)`**
    - Purpose: Hook for implementing tenant-related action logic.
    - Current behavior: No-op (`pass`).

## Configuration/Dependencies
- Depends on `naas_abi.ontologies.modules.NexusPlatformOntology` providing the base class `Tenant`.

## Usage
```python
from naas_abi.ontologies.classes.ontology_naas_ai.nexus.Tenant import Tenant

class MyTenant(Tenant):
    def actions(self):
        # implement your logic here
        return "ok"

t = MyTenant()
print(t.actions())
```

## Caveats
- `actions()` is a placeholder and does nothing unless overridden.
