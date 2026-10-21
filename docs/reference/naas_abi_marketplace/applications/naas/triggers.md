# `triggers` (naas_abi_marketplace.applications.naas.triggers)

## What it is
- Defines ontology-store triggers for the Naas application.
- Builds trigger definitions conditionally based on environment (production vs dev/testing).
- Each trigger listens to ontology triple *insert* events and executes a workflow callback.

## Public API
- `is_production_mode() -> bool`
  - Returns `True` when `ENV` is not `"dev"`.

- `create_class_ontology_yaml() -> tuple | None`
  - In production only:
    - Fetches `NAAS_API_KEY` from the module secret service.
    - Instantiates the class-ontology YAML workflow pipeline.
    - Returns a trigger tuple subscribing to `OntologyEvent.INSERT` for all triples.
  - Returns `None` if not in production or if `NAAS_API_KEY` is missing.

- `create_individual_ontology_yaml() -> tuple | None`
  - In production only:
    - Fetches `NAAS_API_KEY` from the module secret service.
    - Instantiates the individual-ontology YAML workflow pipeline.
    - Returns a trigger tuple subscribing to `OntologyEvent.INSERT` for all triples.
  - Returns `None` if not in production or if `NAAS_API_KEY` is missing.

- Module variable: `triggers: list`
  - Active triggers for this module.
  - Empty when running under tests (`PYTEST_CURRENT_TEST` set or `TESTING=="true"`).
  - Otherwise includes non-`None` results from the two factory functions above.

### Trigger tuple shape
Each factory returns:
- `((None, None, None), OntologyEvent.INSERT, workflow.trigger, True)`
  - Pattern `(None, None, None)` matches any inserted triple.
  - Callback is the workflow’s `trigger` method.
  - The trailing `True` is an additional flag included in the trigger definition.

## Configuration/Dependencies
- Environment variables:
  - `ENV`: if `"dev"`, trigger factories return `None` (no triggers).
  - `PYTEST_CURRENT_TEST` or `TESTING=="true"`: disables all triggers (`triggers = []`).

- Secret dependency:
  - `NAAS_API_KEY` via `ABIModule.get_instance().engine.services.secret.get("NAAS_API_KEY")`.
  - If missing, an error is logged and the trigger is not created.

- Imports/Services:
  - `OntologyEvent` from `naas_abi_core.services.triple_store.TripleStorePorts`
  - `ABIModule` from `naas_abi_marketplace.applications.naas`
  - Workflow/integration classes are imported lazily inside the factory functions.

## Usage
Minimal example: inspect which triggers are active.

```python
import os

# Production mode is any value except "dev"
os.environ["ENV"] = "prod"

from naas_abi_marketplace.applications.naas import triggers as naas_triggers

print(naas_triggers.triggers)
for pattern, event, callback, flag in naas_triggers.triggers:
    print(pattern, event, callback, flag)
```

## Caveats
- No triggers are created when `ENV="dev"`.
- All triggers are disabled during testing when `PYTEST_CURRENT_TEST` is set or `TESTING=="true"`.
- If `NAAS_API_KEY` is not available from the secret service, corresponding triggers are not activated.
