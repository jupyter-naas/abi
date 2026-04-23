# `triggers` (naas_abi_marketplace.applications.naas.triggers)

## What it is
- Defines ontology-store triggers for the Naas application module.
- Triggers are conditionally created based on environment (production vs dev/testing).
- Each trigger subscribes to ontology triple insert events and executes a workflow callback.

## Public API
- `is_production_mode() -> bool`
  - Returns `True` when `ENV` is not `"dev"`.
- `create_class_ontology_yaml() -> tuple | None`
  - In production only, builds and returns a trigger tuple to create **class ontology YAML** on ontology triple inserts.
  - Returns `None` when not in production or when `NAAS_API_KEY` is missing.
- `create_individual_ontology_yaml() -> tuple | None`
  - In production only, builds and returns a trigger tuple to create **individual ontology YAML** on ontology triple inserts.
  - Returns `None` when not in production or when `NAAS_API_KEY` is missing.
- Module variable: `triggers: list`
  - List of active triggers.
  - Empty during testing (`PYTEST_CURRENT_TEST` set or `TESTING=="true"`), otherwise includes non-`None` triggers created by the factory functions above.

### Trigger tuple shape
The factory functions return a tuple with:
- `pattern`: `(None, None, None)` (wildcard subject/predicate/object)
- `event`: `OntologyEvent.INSERT`
- `callback`: `workflow.trigger`
- `True`: an additional flag value (passed through as part of the trigger definition)

## Configuration/Dependencies
- Environment variables:
  - `ENV`: if `"dev"`, triggers are not created.
  - `PYTEST_CURRENT_TEST` or `TESTING=="true"`: disables all triggers (`triggers = []`).
- Secret:
  - `NAAS_API_KEY` retrieved from `ABIModule.get_instance().engine.services.secret.get("NAAS_API_KEY")`.
  - If missing, trigger creation logs an error and returns `None`.
- Depends on:
  - `naas_abi_core.logger`
  - `OntologyEvent` from `naas_abi_core.services.triple_store.TripleStorePorts`
  - `ABIModule` from `naas_abi_marketplace.applications.naas`
  - Workflow/integration classes imported lazily inside trigger factory functions.

## Usage
Minimal example: importing and reading the active trigger list.

```python
import os

# Simulate production mode (not "dev")
os.environ["ENV"] = "prod"

from naas_abi_marketplace.applications.naas import triggers as naas_triggers

for t in naas_triggers.triggers:
    pattern, event, callback, flag = t
    print(pattern, event, callback, flag)
```

## Caveats
- In `ENV="dev"`, no triggers are created.
- In testing contexts (`PYTEST_CURRENT_TEST` set or `TESTING=="true"`), **all triggers are disabled**.
- If `NAAS_API_KEY` is not available via the module secret service, triggers are not activated.
