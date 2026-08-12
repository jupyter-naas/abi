# LinkedInExportProfilePipeline

## What it is
A pipeline that reads a LinkedIn export CSV (default `Profile.csv`), converts each row into RDF triples (data source + row component, LinkedIn profile page, and a person), and inserts the resulting RDF graph into a configured triple store.

## Public API

### Classes

- `LinkedInExportProfilePipelineConfiguration(PipelineConfiguration)`
  - Holds required configuration:
    - `triple_store: ITripleStoreService` — target triple store.
    - `linkedin_export_configuration: LinkedInExportIntegrationConfiguration` — LinkedIn export integration settings (e.g., ZIP path).

- `LinkedInExportProfilePipelineParameters(PipelineParameters)`
  - Runtime inputs:
    - `linkedin_public_url: str` — public LinkedIn profile URL to associate with imported data.
    - `file_name: str = "Profile.csv"` — CSV file name within the export.

- `LinkedInExportProfilePipeline(Pipeline, BasePipeline)`
  - Main pipeline implementation.

### Methods (`LinkedInExportProfilePipeline`)

- `run(parameters: PipelineParameters) -> rdflib.Graph`
  - Reads the CSV from the LinkedIn export, builds an RDF graph, writes CSV/Turtle artifacts to storage, and inserts the graph into the triple store.
  - Raises `TypeError` if `parameters` is not `LinkedInExportProfilePipelineParameters`.
  - Returns an empty `Graph()` if the CSV has zero rows.

- `add_backing_datasource(graph, file_path, file_modified_at, file_created_at, df) -> (Graph, URIRef)`
  - Adds/gets an `abi:DataSource` individual keyed by a hash of `"{file_modified_at}_{file_path}"`.
  - Stores file/CSV metadata (filename, source path/type, extracted/created timestamps, columns list/count, rows count).

- `add_backing_datasource_component(graph, data_source_uri, row) -> (Graph, URIRef)`
  - Adds/gets an `abi:DataSourceComponent` individual keyed by a hash of `tuple(row)`.
  - For each column, writes a data property `linkedin:{normalized_column_name}` with string literal values (`UNKNOWN` for empty/null).

- `add_linkedin_profile_page(graph, linkedin_public_url, backing_datasource_component_uri) -> (Graph, URIRef)`
  - Adds/gets a `linkedin:ProfilePage` keyed by `linkedin:public_url`.
  - Extracts `public_id` from the URL using `split("/in/")[1]...`.
  - Links the profile page to the backing row component via `abi:hasBackingDataSource`.

- `add_person(graph, linkedin_profile_page_uri, backing_datasource_component_uri, first_name, last_name, maiden_name=None, birth_date=None) -> (Graph, URIRef)`
  - If no person is already linked from the profile page (`abi:isLinkedInPageOf`), creates a `cco:ont00001262` (Person).
  - Adds `abi:first_name`, `abi:last_name`, optional `abi:maiden_name`.
  - If `birth_date` is provided, attempts to parse format `"%b %d, %Y"` and writes `abi:birth_date` as `xsd:date` (`""` if parsing fails).
  - Links person and page using `abi:isLinkedInPageOf` / `abi:hasLinkedInPage` and attaches `abi:hasBackingDataSource`.

- `get_person_uri_from_linkedin_profile_page_uri(linkedin_profile_page_uri) -> URIRef | None`
  - SPARQL lookup against the configured triple store to find an existing person linked via `abi:isLinkedInPageOf`.

- `as_tools() -> list[BaseTool]`
  - Exposes the pipeline as a LangChain `StructuredTool`.
  - Tool name/description refer to “connections” even though this pipeline imports profile data.

- `as_api(...) -> None`
  - API exposure placeholder; does not register routes (no behavior beyond defaulting `tags`).

## Configuration/Dependencies

- Services:
  - `ITripleStoreService`
    - Must support `query(sparql: str)` and `insert(graph: rdflib.Graph, graph_name: rdflib.URIRef)`.

- Integration:
  - `LinkedInExportIntegrationConfiguration` used to instantiate `LinkedInExportIntegration`.
  - `LinkedInExportIntegration` is used for:
    - `read_csv(file_name)`
    - `unzip_export()` returning keys: `extracted_directory`, `file_modified_at`, `file_created_at`.

- Base utilities (via `BasePipeline`):
  - `self.sparql_utils.get_identifiers(...)`
  - `self.sparql_utils.results_to_list(...)`
  - `self.storage_utils.save_triples(...)`
  - `self.storage_utils.save_csv(...)`

- RDF/Namespaces:
  - Uses `rdflib` with bindings for `ABI`, `BFO`, `CCO`, and `LINKEDIN = "http://ontology.naas.ai/abi/linkedin/"`.
  - Inserts into graph name: `http://ontology.naas.ai/graph/default`.

## Usage

```python
from naas_abi_marketplace.applications.linkedin.integrations.LinkedInExportIntegration import (
    LinkedInExportIntegrationConfiguration,
)
from naas_abi_marketplace.applications.linkedin.pipelines.LinkedInExportProfilePipeline import (
    LinkedInExportProfilePipeline,
    LinkedInExportProfilePipelineConfiguration,
    LinkedInExportProfilePipelineParameters,
)

triple_store = ...  # ITripleStoreService implementation

pipeline = LinkedInExportProfilePipeline(
    LinkedInExportProfilePipelineConfiguration(
        triple_store=triple_store,
        linkedin_export_configuration=LinkedInExportIntegrationConfiguration(
            export_file_path="path/to/Complete_LinkedInDataExport.zip"
        ),
    )
)

g = pipeline.run(
    LinkedInExportProfilePipelineParameters(
        linkedin_public_url="https://demo.example/profiles/demo",
        file_name="Profile.csv",
    )
)

print(len(g))
```

## Caveats

- `linkedin_public_url` must contain `"/in/"`; otherwise `add_linkedin_profile_page()` will raise during `split("/in/")[1]`.
- Empty/null CSV cell values are stored as the string `"UNKNOWN"` for `linkedin:*` predicates.
- `run()` passes `.strip()` values for `"Maiden Name"` and `"Birth Date"`; if these are `"UNKNOWN"` they are treated as truthy:
  - `maiden_name` may be stored as `"UNKNOWN"`.
  - `birth_date` parsing may fail and store `""^^xsd:date`.
- `run()` calls `unzip_export()` multiple times to retrieve metadata; behavior depends on the integration implementation.
- Triples are always inserted into `http://ontology.naas.ai/graph/default` (not configurable here).
