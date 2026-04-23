# BasePipeline

## What it is
- A minimal base class for LinkedIn application pipelines.
- Provides ready-to-use helpers for:
  - SPARQL/triple-store access (`SPARQLUtils`)
  - Object storage access (`StorageUtils`)
- Initializes these utilities using the current `ABIModule` engine services.

## Public API
- `class BasePipeline`
  - `__init__(self) -> None`
    - Fetches `ABIModule.get_instance()`
    - Instantiates:
      - `self.sparql_utils = SPARQLUtils(module.engine.services.triple_store)`
      - `self.storage_utils = StorageUtils(module.engine.services.object_storage)`

## Configuration/Dependencies
- Depends on:
  - `naas_abi_marketplace.applications.linkedin.ABIModule` being properly initialized and accessible via `ABIModule.get_instance()`.
  - Engine services exposed on the module instance:
    - `module.engine.services.triple_store`
    - `module.engine.services.object_storage`
- External utilities:
  - `naas_abi_core.utils.SPARQL.SPARQLUtils`
  - `naas_abi_core.utils.StorageUtils.StorageUtils`

## Usage
```python
from naas_abi_marketplace.applications.linkedin.pipelines.BasePipeline import BasePipeline

class MyPipeline(BasePipeline):
    def run(self):
        # Use self.sparql_utils and self.storage_utils here
        pass

pipeline = MyPipeline()
pipeline.run()
```

## Caveats
- `BasePipeline` assumes `ABIModule.get_instance()` is available and its `engine.services` are configured; otherwise initialization may fail.
