# `{{integration_name_pascal}}Integration`

## What it is
- A template integration module defining:
  - A configuration dataclass for `{{integration_name_pascal}}`
  - An integration class that stores and forwards its configuration to the base `Integration`

## Public API
- `{{integration_name_pascal}}IntegrationConfiguration(IntegrationConfiguration)`
  - Dataclass placeholder for integration configuration (currently no additional fields).
- `{{integration_name_pascal}}Integration(Integration)`
  - `__init__(configuration: {{integration_name_pascal}}IntegrationConfiguration)`
    - Initializes the base `Integration` with the provided configuration and stores it internally.

## Configuration/Dependencies
- Depends on `naas_abi_core`:
  - `naas_abi_core.integration.Integration`
  - `naas_abi_core.integration.IntegrationConfiguration`
- The module also imports (currently unused in this template):
  - `requests`, `logger`, `IntegrationConnectionError`
  - `CacheFactory`, `CacheService`, `DataType`
  - standard libs: `hashlib`, `re`, `dataclasses`, `datetime`, `typing`

## Usage
```python
from naas_abi_cli.cli.new.templates.integration.{{integration_name_pascal}}Integration import (
    {{integration_name_pascal}}Integration,
    {{integration_name_pascal}}IntegrationConfiguration,
)

config = {{integration_name_pascal}}IntegrationConfiguration()
integration = {{integration_name_pascal}}Integration(config)
```

## Caveats
- This is a scaffold/template: it defines no operational methods beyond initialization and adds no configuration fields.
