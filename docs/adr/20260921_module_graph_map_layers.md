# Module graph map layers

Status: Accepted

Date: 2026-09-21

## Context

Deployments need to display organization locations in Nexus Maps while preserving the ontology, source provenance and workspace graph permissions. Public datasets and environment-configured Custom feeds already share the Leaflet viewer. Product-specific evidence must remain outside upstream ABI.

## Decision

Modules register a GraphMapLayer in their FastAPI hook. The generic Maps catalog exposes authenticated, workspace-scoped discovery and read-only feeds. Each descriptor declares an exact graph URI and a projection accepting GraphQueryPort. The API checks workspace membership and graph grants before running the projection with WorkspaceGraphStore. It never passes the unrestricted catalog store.

The browser discovers permitted layers at runtime in the Custom group. Graph feeds extend the pin contract with entity and graph URIs, sources, observation dates, coordinate precision and relationships. A shared inspector links to the KG within the same workspace. Source links accept only HTTP(S). Catalog and feeds disable caching, abort on workspace changes and do not retain another workspace's results.

Feeds may also include `coverage: {pins: [...]}` with independently cited city records and `memberIds` linking the address records in that response. The frontend offers address and city-coverage views on one map. Natural Earth supplies country geometry; represented countries and city counts are derived only from the scoped coverage pins. Country shading is a geographic summary, not a new claim of countrywide operations.

## Consequences

Company evidence, ontology extensions, snapshot selection and SPARQL stay in deployment modules. ABI provides reusable rendering and access control. Existing public and environment-configured feeds remain supported. Graph snapshots must be published and granted to a workspace before their layers are discoverable. City reference coordinates are presented with their supplied precision; a map marker does not establish building occupancy or deployment activity.

Validation covers HTTP authentication, workspace membership, graph grants, scoped-store projection, live RDF changes, feed parsing and KG links.
