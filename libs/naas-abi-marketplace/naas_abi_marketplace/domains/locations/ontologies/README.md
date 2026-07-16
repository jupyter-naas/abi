# Locations Ontology

`modules/LocationsOntology.ttl` defines the gazetteer classes as drafts (`abi:` prefix) subclassing [Common Core Ontologies](https://www.commoncoreontologies.org/) (imported from `imports/GeospatialOntology.ttl` and `imports/InformationEntityOntology.ttl` -- resolved automatically since the module loader globs every `.ttl` under `ontologies/`, regardless of subfolder):

| Class | CCO parent | Represents |
|---|---|---|
| `abi:Country` | Geospatial Region (`cco:ont00000472`) | ISO country |
| `abi:State` | Geospatial Region | admin1 (GeoNames) / `state_name` (pgeocode) |
| `abi:Region` | Geospatial Region | admin2 (GeoNames) / `county_name` (pgeocode) |
| `abi:City` | Populated place (`cco:ont00000224`) | leaf locality |
| `abi:Address` | Designative ICE (`cco:ont00000686`) | structured address string |
| `abi:PostalCode` | Designative ICE | worldwide postal code |
| `abi:ZIPCode` | `abi:PostalCode` | US-specific postal code |

Datatype properties `abi:country_code`, `abi:state_code`, `abi:region_code` store the corresponding GeoNames admin codes. No new object property was needed for the location hierarchy (City -> Region -> State -> Country) -- it's expressed with the existing BFO core relation `bfo:BFO_0000171` ("located in"), which is generic enough to link a material `City` to an immaterial `Region`/`State`/`Country`.

Validated with `/check-ontology` (`onto2py`); generated Python classes live in `classes/ontology_naas_ai/abi/` and `modules/LocationsOntology.py`. Re-run `/check-ontology` after any further edits to this file.
