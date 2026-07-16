# Locations Agent

`LocationsAgent` wires together every tool built for this domain:

- `GeoNamesIntegration.as_tools()` -- `get_geonames_country_info`, `get_geonames_postal_codes`, `search_geonames_postal_code`
- `PgeocodeIntegration.as_tools()` -- `query_pgeocode_postal_code`
- `GeonamescacheIntegration.as_tools()` -- `get_geonamescache_countries`, `get_geonamescache_cities`, `search_geonamescache_cities`, `get_geonamescache_us_states`, `get_geonamescache_us_counties`
- `CLDRIntegration.as_tools()` -- `get_cldr_territory_name`, `get_cldr_territory_names`, `get_cldr_territories`, `get_cldr_language_name`
- `LocationsPipeline.as_tools()` -- `add_locations_to_graph` (persists city/region/state/country/postal_code records into the knowledge graph, see [pipelines/README.md](../pipelines/README.md))
- `LocationsWorkflow.as_tools()` -- `vectorize_locations`, `search_locations` (embeds every location individual into a vector collection for semantic search, see [workflows/README.md](../workflows/README.md))

See [integrations/README.md](../integrations/README.md) for what each data source covers.

`LocationsAgent.New()` pulls `triple_store`, `vector_store`, and `secret` from `ABIModule.get_instance().engine.services` -- these are enabled in [`domains/locations/__init__.py`](../__init__.py).
