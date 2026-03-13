# Creating a Module

This is a practical guide to implement a new ABI module.

Related pages: [[Module-System]], [[Configuration]], [[Engine]].

## 1) Create package and export `ABIModule`

Your Python package should expose an `ABIModule` symbol at package root.

## 2) Implement dependencies

Declare what you need explicitly with `ModuleDependencies`.

```python
dependencies = ModuleDependencies(
    modules=["another_module", "optional_module#soft"],
    services=[TripleStoreService, Secret],
)
```

## 3) Add a `Configuration` class

Configuration must subclass `ModuleConfiguration`.

```python
class Configuration(ModuleConfiguration):
    my_setting: str
```

The values come from `modules[].config` in engine YAML.

## 4) Implement lifecycle hooks

- `on_load()`: local initialization, file discovery, local setup.
- `on_initialized()`: cross-module/service interactions.

## 5) Optional module layout

- `agents/` for agent classes
- `orchestrations/` for orchestration classes
- `ontologies/` for `.ttl` files auto-loaded by engine

## 6) Register in config

```yaml
modules:
  - module: "my_module"
    enabled: true
    config:
      my_setting: "value"
```

## 7) Validate with engine

```python
engine = Engine()
engine.load(module_names=["my_module"])
```
