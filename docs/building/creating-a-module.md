# Creating a Module

Modules are the primary extension unit of ABI. A module packages a set of related agents, integrations, pipelines, workflows, and ontologies into a self-contained, dependency-declaring unit that the Engine loads and wires.

Related pages: [[libs/naas-abi-core/Module-System|Module System]], [[libs/naas-abi-core/Engine|Engine]], [[building/creating-an-agent|Creating an Agent]].

---

## Module tiers

Choose the right location for your module:

| Tier | Path | Use for |
|------|------|---------|
| Core | `libs/naas-abi/naas_abi/modules/core/` | Essential system functionality; shipped upstream |
| Custom | `libs/naas-abi/naas_abi/modules/custom/` | Your private extensions; not committed to upstream |
| Marketplace | `libs/naas-abi-marketplace/` | Community-shared modules; disabled by default |

For most users, **custom** is the right choice.

---

## Module structure

```
naas_abi/modules/custom/my_module/
├── __init__.py             # Required - exports ABIModule
├── agents/
│   └── MyAgent.py          # Must contain Agent.New() pattern
├── integrations/
│   └── MyIntegration.py    # External API adapter
├── pipelines/
│   └── MyPipeline.py       # Data ingestion into triple store
├── workflows/
│   └── MyWorkflow.py       # Business logic exposed as tools + API
├── ontologies/
│   └── MyOntology.ttl      # OWL Turtle ontology
└── tests/
    └── test_my_module.py
```

Only `__init__.py` is required. All other folders are optional and auto-discovered.

---

## Module class

```python
# __init__.py
from naas_abi_core.module.Module import BaseModule, ModuleConfiguration, ModuleDependencies
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService


class ABIModule(BaseModule):
    dependencies = ModuleDependencies(
        modules=[],                     # List module names this one depends on
        services=[TripleStoreService],  # List required services
    )

    class Configuration(ModuleConfiguration):
        # Add module-specific config fields here
        pass

    def on_load(self):
        super().on_load()
        # Called when module is loaded. Access self.engine_proxy for dependencies.

    def on_initialized(self):
        # Called after ALL modules and services are loaded.
        # Safe to access services and sibling modules here.
        pass
```

The Engine computes a topological load order from all `dependencies` declarations. Circular dependencies fail fast.

---

## Enabling a module

Add it to `config.yaml`:

```yaml
modules:
  - module: "naas_abi.modules.custom.my_module"
    enabled: true
    config:
      my_custom_field: "value"
```

---

## Auto-discovery

When the Engine loads your module, it automatically discovers:

- **Ontologies**: all `*.ttl` files under `ontologies/`
- **Agents**: all `*Agent.py` files under `agents/` that expose `Agent.New()`
- **Orchestrations**: all classes in `orchestrations/`

---

## Data storage path

By code-data symmetry ([[adr/20250824_code-data-symmetry|ADR]]), your module's data lives at a path that mirrors its code path:

```
Code:  naas_abi/modules/custom/my_module/
Data:  storage/datastore/modules/custom/my_module/
```

Use `ensure_data_directory(module_path)` from `naas_abi_core.utils.Storage` to create this path at startup.

---

## Accessing services from within a module

Inside any module method, `self.engine` is an `EngineProxy` that exposes only declared dependencies:

```python
def on_initialized(self):
    triple_store = self.engine.services.triple_store
    triple_store.query("SELECT * WHERE { ?s ?p ?o } LIMIT 10")
```

Attempting to access an undeclared service raises a runtime error. This is intentional - it enforces explicit dependency contracts.

---

## Soft dependencies

Suffix a module name with `#soft` to declare an optional dependency:

```python
dependencies = ModuleDependencies(
    modules=["naas_abi.modules.core.linkedin#soft"],
    services=[TripleStoreService],
)
```

The Engine loads your module even if the soft dependency is absent.

---

## Testing

```python
# tests/test_my_module.py
from naas_abi_core.engine.Engine import Engine

def test_module_loads():
    engine = Engine()
    engine.load(module_names=["naas_abi.modules.custom.my_module"])
    assert "naas_abi.modules.custom.my_module" in engine.modules
```

Next steps: [[building/creating-an-agent|Creating an Agent]], [[building/creating-an-integration|Creating an Integration]].
