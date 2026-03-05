# Services Overview

Services provide infrastructure capabilities behind stable ports/adapters.

Related pages:

- [[services/Triple-Store]]
- [[services/Vector-Store]]
- [[services/Object-Storage]]
- [[services/Secret-Service]]
- [[services/Bus-Service]]
- [[services/Key-Value-Service]]
- [[services/Cache-Service]]

## Shared pattern

Each service follows the same architecture:

1. **Port interface**: abstract contract.
2. **Adapters**: concrete backend implementation.
3. **Service**: domain facade used by modules and applications.
4. **Config binding**: choose adapter in `config.yaml`.

## Runtime loading strategy

Services are lazy-selected by module dependency requirements.

- If no module requires a service, it is not loaded.
- Some service dependencies are auto-included (example: triple store implies bus for event publishing).

## Configuration keys

- `services.object_storage.object_storage_adapter`
- `services.triple_store.triple_store_adapter`
- `services.vector_store.vector_store_adapter`
- `services.secret.secret_adapters`
- `services.bus.bus_adapter`
- `services.kv.kv_adapter`
