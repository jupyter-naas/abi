# Integration

## What it is
- A minimal base module for defining third-party service integrations.
- Provides:
  - A standard configuration container type (`IntegrationConfiguration`)
  - A base integration class (`Integration`) that stores configuration
  - A dedicated exception type for connection failures (`IntegrationConnectionError`)

## Public API
- `class IntegrationConnectionError(Exception)`
  - Exception type intended for integration connection-related failures.

- `@dataclass class IntegrationConfiguration`
  - Placeholder configuration object to be extended with credentials/settings.

- `class Integration`
  - Base class representing an integration with an external tool/service.
  - `__init__(self, configuration: IntegrationConfiguration)`
    - Stores the provided configuration instance.

## Configuration/Dependencies
- Dependencies:
  - Standard library: `dataclasses.dataclass`
- Configuration:
  - `IntegrationConfiguration` currently has no fields; expected to be subclassed/extended.

## Usage
```python
from dataclasses import dataclass
from naas_abi_core.integration.integration import (
    Integration,
    IntegrationConfiguration,
)

@dataclass
class MyConfig(IntegrationConfiguration):
    api_key: str

class MyIntegration(Integration):
    pass

integration = MyIntegration(MyConfig(api_key="secret"))
```

## Caveats
- `IntegrationConfiguration` is empty in this module; it does not enforce any required settings.
- `Integration` only stores configuration; it does not implement connection logic or any operational methods.
