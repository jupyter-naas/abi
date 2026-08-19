# FlightsService

## What it is
- An async service orchestrator for flight tracking data.
- Wraps three `IFlightAdapter` implementations (civil, military, theater) and exposes safe fetch methods that return an empty list on failure and log a warning.

## Public API
- **Class: `FlightsService(IFlightsService)`**
  - `__init__(civil: IFlightAdapter, military: IFlightAdapter, theater: IFlightAdapter) -> None`
    - Injects adapters used to fetch flight state data.
  - `async get_civil() -> list[FlightState]`
    - Fetches civil flight states via the civil adapter.
    - On exception: logs a warning and returns `[]`.
  - `async get_military() -> list[FlightState]`
    - Fetches military flight states via the military adapter.
    - On exception: logs a warning and returns `[]`.
  - `async get_theater() -> list[FlightState]`
    - Fetches theater flight states via the theater adapter.
    - On exception: logs a warning and returns `[]`.

## Configuration/Dependencies
- **Logging**
  - Uses `logging.getLogger(__name__)` and logs warnings on fetch failures.
- **Types/Interfaces**
  - `FlightState` from `ports.models`
  - `IFlightAdapter`, `IFlightsService` from `services.flights.FlightsPort`
- **Adapter contract**
  - Each injected `IFlightAdapter` is expected to implement an async `fetch()` returning `list[FlightState]`.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.intelligence.apps.wsr.apps.dashboard.api.services.flights.FlightsService import FlightsService

# Your adapters must implement: async def fetch(self) -> list[FlightState]
class DummyAdapter:
    async def fetch(self):
        return []  # replace with real FlightState objects

async def main():
    service = FlightsService(
        civil=DummyAdapter(),
        military=DummyAdapter(),
        theater=DummyAdapter(),
    )

    civil = await service.get_civil()
    military = await service.get_military()
    theater = await service.get_theater()

    print(len(civil), len(military), len(theater))

asyncio.run(main())
```

## Caveats
- All exceptions from adapter `fetch()` are swallowed; callers only receive `[]` and must rely on logs for error visibility.
