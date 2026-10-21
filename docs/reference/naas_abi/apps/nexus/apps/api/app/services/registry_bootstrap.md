# `initialize_nexus_service_registry`

## What it is
- A bootstrap function that initializes and configures the global `ServiceRegistry` singleton for the Nexus API application.
- Wires service instances together and connects Postgres-backed secondary adapters via a shared DB session getter.

## Public API
- `initialize_nexus_service_registry() -> ServiceRegistry`
  - Returns the already-configured `ServiceRegistry` singleton if it exists.
  - Otherwise:
    - Creates a `db_getter()` that returns `PostgresSessionRegistry.instance().current_session()`.
    - Instantiates services and their Postgres secondary adapters.
    - Calls `ServiceRegistry.configure(RegistryServices(...))` and returns the configured registry.

## Configuration/Dependencies
- Depends on singleton registries:
  - `ServiceRegistry.instance()` / `ServiceRegistry.configure(...)`
  - `PostgresSessionRegistry.instance().current_session()`
- Constructs the following services/adapters:
  - `IAMService(IAMSecondaryAdapterPostgres(db_getter=...))`
  - `WorkspaceService(WorkspaceSecondaryAdapterPostgres(db_getter=...))`
  - `OrganizationService(OrganizationSecondaryAdapterPostgres(db_getter=...))`
  - `ChatService(adapter=ChatSecondaryAdapterPostgres(db_getter=...), iam_service=iam_service)`
  - `SearchService()`
  - `AgentService(AgentSecondaryAdapterPostgres(db_getter=...), iam_service=iam_service)`

## Usage
```python
from naas_abi.apps.nexus.apps.api.app.services.registry_bootstrap import (
    initialize_nexus_service_registry,
)

registry = initialize_nexus_service_registry()

# Access services from the registry (attribute names come from RegistryServices)
iam = registry.services.iam
chat = registry.services.chat
```

## Caveats
- If `ServiceRegistry.instance()` raises `RuntimeError`, the function proceeds to configure a new registry; otherwise it returns the existing singleton as-is.
- Requires `PostgresSessionRegistry` to be properly set up so `current_session()` can be obtained when adapters use `db_getter()`.
