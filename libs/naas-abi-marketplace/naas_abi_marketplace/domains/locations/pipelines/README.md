# Locations Pipelines

## LocationsPipeline

Fetches city/region/state/country/postal_code records from one of the [integrations](../integrations/README.md) and materializes them as RDF individuals following [LocationsOntology](../ontologies/modules/LocationsOntology.ttl):

`abi:PostalCode -> abi:City -> abi:Region -> abi:State -> abi:Country`

(`Region` and/or `State` are omitted when the source has no data for that level.) Levels are linked with `bfo:BFO_0000171` ("located in"); `abi:Country`/`abi:State`/`abi:Region` carry their GeoNames admin code (`country_code`/`state_code`/`region_code`); `abi:City` carries latitude/longitude (`cco:ont00001766`/`cco:ont00001764`).

### Configuration

- `source`: `LocationSource.GEONAMES` (default) or `LocationSource.PGEOCODE`.

### Parameters

- `country_code` (required): ISO-3166 alpha-2 country code, e.g. `"FR"`.
- `postal_code` (optional): a specific postal code. Required when `source` is `pgeocode`. When omitted with `source=geonames`, the pipeline bulk-loads every postal code of the country into the returned graph.

### Usage

```python
from naas_abi_marketplace.domains.locations.pipelines.LocationsPipeline import (
    LocationSource, LocationsPipeline, LocationsPipelineConfiguration, LocationsPipelineParameters,
)

pipeline = LocationsPipeline(LocationsPipelineConfiguration(source=LocationSource.GEONAMES))
graph = pipeline.run(LocationsPipelineParameters(country_code="FR", postal_code="75001"))
```

`run()` returns an `rdflib.Graph` (via `ABIGraph`); it does not persist to a triple store itself. It is also exposed as the `add_locations_to_graph` tool via `as_tools()`, wired into `LocationsAgent`.
