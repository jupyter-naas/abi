# `ABIClient`

## What it is
- A typed client that wires multiple Naas ABI service clients to a single shared `Transport` (one underlying NATS connection).
- Provides an async context manager and a generic job accessor.

## Public API

### Class: `ABIClient`
Creates service-specific clients that all share the same transport.

#### `__init__(url: str, token: str | Callable[[], str], *, timeout: float = 10.0, **connection_options: Any) -> None`
- Creates a `Transport` and initializes the following service clients:
  - `bus: BusClient`
  - `activity_log: ActivityLogClient`
  - `cache: CacheClient`
  - `coding_environment: CodingEnvironmentClient`
  - `dataset: DatasetClient`
  - `document: DocumentClient`
  - `email: EmailClient`
  - `event: EventClient`
  - `keyvalue: KeyvalueClient`
  - `model_registry: ModelRegistryClient`
  - `object_storage: ObjectStorageClient`
  - `secret: SecretClient`
  - `source_control: SourceControlClient`
  - `triple_store: TripleStoreClient`
  - `vector_store: VectorStoreClient`

#### Async context manager
- `async __aenter__(self) -> ABIClient`
  - Returns `self`.
- `async __aexit__(self, *exc) -> None`
  - Calls `await self.close()`.

#### `get_job(self, module_id: str, name: str, *, project: str = "default")`
- Returns a `JobProxy` for a job identified by `module_id` and job `name`.
- Notes from docstring:
  - Works for any module (including engine modules not in discovery).
  - Nothing is validated until a trigger; unknown job runs may remain `QUEUED`.
  - Prefer `ModuleProxy.get_job` for discovered modules.

#### `async close(self) -> None`
- Closes the underlying transport connection.
- Does **not** shut down any remote service.

## Configuration/Dependencies
- Requires `naas_abi_sdk.transport.Transport` and the various `*Client` service modules.
- Parameters:
  - `url`: transport endpoint.
  - `token`: authentication token string or a callable returning a token.
  - `timeout`: transport timeout (default `10.0`).
  - `connection_options`: forwarded to `Transport`.

## Usage

```python
import asyncio
from naas_abi_sdk.client import ABIClient

async def main():
    async with ABIClient(url="nats://localhost:4222", token="MY_TOKEN") as abi:
        # Use any typed service client
        # e.g., abi.bus, abi.cache, abi.dataset, ...

        # Access a job by module id + job name
        job = abi.get_job(module_id="my-module", name="daily_run", project="default")
        # Triggering/using the job depends on JobProxy API (not shown here).

asyncio.run(main())
```

## Caveats
- `get_job()` does not validate the module/job upfront; unknown jobs may result in runs that stay `QUEUED` until triggered.
