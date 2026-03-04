# Module System

Modules are the primary extension mechanism in `naas-abi-core`.

Related pages: [[Engine]], [[Architecture]], [[Built-in-Module-Templatable-SPARQL]].

## Module contract

Every module exports `ABIModule` (subclass of `BaseModule`) and a nested `Configuration` class (subclass of `ModuleConfiguration`).

It also defines static dependencies:

- dependent modules
- required services

## Example skeleton

```python
from naas_abi_core.module.Module import BaseModule, ModuleConfiguration, ModuleDependencies
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService


class ABIModule(BaseModule):
    dependencies = ModuleDependencies(
        modules=["my_other_module"],
        services=[TripleStoreService],
    )

    class Configuration(ModuleConfiguration):
        pass

    def on_load(self):
        super().on_load()

    def on_initialized(self):
        # Safe point to access dependencies
        pass
```

## Lifecycle hooks

- `on_load()`: called during module loading.
- `on_initialized()`: called after all modules/services/ontologies are loaded.
- `on_unloaded()`: optional unload hook.

## Auto-discovery inside a module

On load, the module runtime auto-discovers:

- ontology files in `<module_root>/ontologies/**/*.ttl`
- agent classes in `<module_root>/agents/*.py`
- orchestration classes in `<module_root>/orchestrations/*.py`

## Dependency visibility

Inside module code, `self.engine` is an `EngineProxy`:

- you can access only declared service dependencies
- you can access only declared module dependencies

This keeps module boundaries explicit and enforceable.

For a step-by-step build guide, see [[modules/Creating-a-Module]].
