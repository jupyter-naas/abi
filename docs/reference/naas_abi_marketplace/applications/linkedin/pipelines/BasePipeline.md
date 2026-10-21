# BasePipeline

## What it is
- A minimal base class for LinkedIn application pipelines.
- Instantiates and exposes:
  - `SPARQLUtils` for triple-store access
  - `StorageUtils` for object storage access
- Wires utilities using the current `ABIModule` engine services.

## Public API
- `class BasePipeline`
  - `__init__(self) -> None`
    - Retrieves the module singleton via `ABIModule.get_instance()`.
    - Initializes:
      - `self.sparql_utils = SPARQLUtils(module.engine.services.triple_store)`
      - `self.storage_utils = StorageUtils(module.engine.services.object_storage)`

## Configuration/Dependencies
- Requires `naas_abi_marketplace.applications.linkedin.ABIModule` to be initialized and accessible via `ABIModule.get_instance()`.
- Expects the module to expose engine services:
  - `module.engine.services.triple_store`
  - `module.engine.services.object_storage`
- Uses:
  - `naas_abi_core.utils.SPARQL.SPARQLUtils`
  - `naas_abi_core.utils.StorageUtils.StorageUtils`

## Usage
```python
from naas_abi_marketplace.applications.linkedin.pipelines.BasePipeline import BasePipeline

class MyPipeline(BasePipeline):
    def run(self):
        # Access configured utilities
        _sparql = self.sparql_utils
        _storage = self.storage_utils

pipeline = MyPipeline()
pipeline.run()
```

## Caveats
- Initialization will fail if `ABIModule.get_instance()` is unavailable or if `module.engine.services.triple_store` / `object_storage` are not configured.
