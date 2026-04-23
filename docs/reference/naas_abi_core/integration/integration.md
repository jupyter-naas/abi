# Integration

## What it is
- A minimal base module for representing connections to third-party tools/services.
- Provides:
  - A base `Integration` class that stores configuration.
  - A placeholder `IntegrationConfiguration` dataclass for credentials/settings.
  - A dedicated `IntegrationConnectionError` exception type.

## Public API
- **Exception**
  - `IntegrationConnectionError`: Raised to represent integration connection-related failures (no behavior beyond being a distinct exception type).

- **Dataclass**
  - `IntegrationConfiguration`: Empty configuration container intended to be subclassed/extended with fields needed by a specific integration.

- **Class**
  - `Integration`
    - `__init__(configuration: IntegrationConfiguration)`: Stores the provided configuration on the instance (no connection logic implemented).

## Configuration/Dependencies
- Standard library:
  - `dataclasses.dataclass`
- Configuration model:
  - `IntegrationConfiguration` is empty; expected to be extended in real integrations.

## Usage
```python
from dataclasses import dataclass
from naas_abi_core.integration.integration import Integration, IntegrationConfiguration

@dataclass
class MyConfig(IntegrationConfiguration):
    api_key: str

integration = Integration(MyConfig(api_key="secret"))
```

## Caveats
- `IntegrationConfiguration` has no fields; you must define your own subclass with the required settings.
- `Integration` only stores configuration; it does not implement connection, authentication, or API calls.
- Configuration is stored in a name-mangled private attribute (`__configuration`), so it is not directly accessible as `integration.__configuration`.
