# FlightsPort

## What it is
- Defines async interface contracts for the `wsr:FlightTrackingProcess` domain.
- Provides two abstract port interfaces:
  - An adapter interface for fetching flight states.
  - A service interface for retrieving categorized flight states (civil, military, theater).

## Public API
### Classes
- `IFlightAdapter`
  - `async fetch() -> list[FlightState]`
    - Contract for fetching a list of `FlightState` records from an external source.

- `IFlightsService`
  - `async get_civil() -> list[FlightState]`
    - Contract for retrieving civil flight states.
  - `async get_military() -> list[FlightState]`
    - Contract for retrieving military flight states.
  - `async get_theater() -> list[FlightState]`
    - Contract for retrieving theater flight states.

## Configuration/Dependencies
- Depends on `FlightState` model:
  - `from ports.models import FlightState`
- All methods are `async` and must be awaited.

## Usage
Minimal example implementing the interfaces:

```python
import asyncio
from ports.models import FlightState
from naas_abi_marketplace.domains.intelligence.apps.wsr.apps.dashboard.api.services.flights.FlightsPort import (
    IFlightAdapter, IFlightsService
)

class MyFlightAdapter(IFlightAdapter):
    async def fetch(self) -> list[FlightState]:
        return []  # return real FlightState objects in practice

class MyFlightsService(IFlightsService):
    def __init__(self, adapter: IFlightAdapter):
        self.adapter = adapter

    async def get_civil(self) -> list[FlightState]:
        return await self.adapter.fetch()

    async def get_military(self) -> list[FlightState]:
        return await self.adapter.fetch()

    async def get_theater(self) -> list[FlightState]:
        return await self.adapter.fetch()

async def main():
    service = MyFlightsService(MyFlightAdapter())
    flights = await service.get_civil()
    print(flights)

asyncio.run(main())
```

## Caveats
- Base methods raise `NotImplementedError`; these classes are contracts and must be subclassed to be usable.
- Return types are annotated as `list[FlightState]`; implementations should return actual `FlightState` instances.
