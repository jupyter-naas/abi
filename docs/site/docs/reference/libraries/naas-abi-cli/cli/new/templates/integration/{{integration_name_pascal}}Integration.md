# `{{integration_name_pascal}}Integration`

## What it is
- A template integration class for `naas_abi_core` integrations.
- Defines a configuration dataclass and an `Integration` subclass wiring that configuration into the base class.

## Public API
- `{{integration_name_pascal}}IntegrationConfiguration(IntegrationConfiguration)`
  - Purpose: Holds configuration for the integration (currently empty; extend with fields as needed).
- `{{integration_name_pascal}}Integration(Integration)`
  - `__init__(configuration: {{integration_name_pascal}}IntegrationConfiguration)`
    - Purpose: Initialize the integration with a typed configuration and pass it to the base `Integration`.

## Configuration/Dependencies
- Depends on `naas_abi_core`:
  - `naas_abi_core.integration.Integration`
  - `naas_abi_core.integration.IntegrationConfiguration`
- Note: Several modules are imported but not used in this template (e.g., `requests`, cache services, `logger`).

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
- The configuration class currently has no fields; add required settings by extending the dataclass.
- This template does not implement any integration-specific methods beyond initialization.
