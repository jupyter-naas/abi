# LinkedInExportProfilePipeline

## What it is
A pipeline that reads a LinkedIn export CSV (default `Profile.csv`), converts rows into RDF triples (backing data source + components, LinkedIn profile page, and person), and inserts the resulting graph into a configured triple store.

## Public API

### Classes

- `LinkedInExportProfilePipelineConfiguration(PipelineConfiguration)`
  - Holds required services/config for the pipeline:
    - `triple_store: ITripleStoreService`
    - `linkedin_export_configuration: LinkedInExportIntegrationConfiguration`

- `LinkedInExportProfilePipelineParameters(PipelineParameters)`
  - Runtime inputs:
    - `linkedin_public_url: str` — LinkedIn public profile URL to associate with the imported data.
    - `file_name: str = "Profile.csv"` — CSV file name inside the LinkedIn export.

- `LinkedInExportProfilePipeline(Pipeline, BasePipeline)`
  - Main pipeline implementation.

### Methods (LinkedInExportProfilePipeline)

- `run(parameters: PipelineParameters) -> rdflib.Graph`
  - Reads the CSV, builds an RDF graph, writes logs/artifacts to storage, and inserts the graph into the triple store.
  - Validates `parameters` is `LinkedInExportProfilePipelineParameters`.

- `add_backing_datasource(graph, file_path, file_modified_at, file_created_at, df) -> (Graph, URIRef)`
  - Adds/gets a `abi:DataSource` individual identified by a hash of `(modified_at, file_path)` and stores basic CSV metadata.

- `add_backing_datasource_component(graph, data_source_uri, row) -> (Graph, URIRef)`
  - Adds/gets a `abi:DataSourceComponent` individual for the given CSV row (hash of row tuple).
  - Writes each CSV column value as a `linkedin:{normalized_column_name}` predicate on the row individual.

- `add_linkedin_profile_page(graph, linkedin_public_url, backing_datasource_component_uri) -> (Graph, URIRef)`
  - Adds/gets a `linkedin:ProfilePage` individual keyed by `linkedin:public_url`.
  - Extracts `public_id` from the URL by splitting on `"/in/"`.

- `add_person(graph, linkedin_profile_page_uri, backing_datasource_component_uri, first_name, last_name, maiden_name=None, birth_date=None) -> (Graph, URIRef)`
  - Creates a `cco:ont00001262` (Person) individual if none is already linked via `abi:isLinkedInPageOf`.
  - Optionally parses birth date strings in format `"%b %d, %Y"` to `YYYY-MM-DD`.

- `get_person_uri_from_linkedin_profile_page_uri(linkedin_profile_page_uri) -> URIRef | None`
  - SPARQL lookup: finds a person already linked from the given profile page via `abi:isLinkedInPageOf`.

- `as_tools() -> list[BaseTool]`
  - Exposes the pipeline as a LangChain `StructuredTool` (note: tool name/description currently mention “connections” even though this pipeline imports profiles).

- `as_api(...) -> None`
  - API exposure stub; currently does nothing and returns `None`.

## Configuration/Dependencies

- Requires:
  - A triple store service implementing `ITripleStoreService` with:
    - `query(sparql: str)`
    - `insert(graph: rdflib.Graph, graph_name: rdflib.URIRef)`
  - `LinkedInExportIntegrationConfiguration` (e.g., `export_file_path=...zip`)
  - `BasePipeline` utilities (used indirectly):
    - `self.sparql_utils.get_identifiers(...)`
    - `self.sparql_utils.results_to_list(...)`
    - `self.storage_utils.save_triples(...)`
    - `self.storage_utils.save_csv(...)`

- Libraries used:
  - `rdflib`, `pandas`, `fastapi` (router type), `langchain_core.tools`

- Namespaces/ontologies:
  - `ABI`, `BFO`, `CCO`, and `LINKEDIN = "http://ontology.naas.ai/abi/linkedin/"`

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

# Provide your triple store service instance somehow:
triple_store = ...  # must implement ITripleStoreService

pipeline = LinkedInExportProfilePipeline(
    LinkedInExportProfilePipelineConfiguration(
        triple_store=triple_store,
        linkedin_export_configuration=LinkedInExportIntegrationConfiguration(
            export_file_path="path/to/Complete_LinkedInDataExport.zip"
        ),
    )
)

graph = pipeline.run(
    LinkedInExportProfilePipelineParameters(
        linkedin_public_url="https://www.linkedin.com/in/some-public-id/",
        file_name="Profile.csv",
    )
)

print(graph.serialize(format="turtle"))
```

## Caveats

- `linkedin_public_url` must contain `"/in/"`; otherwise `add_linkedin_profile_page()` will fail when extracting the public id.
- Missing/empty cell values are coerced to `"UNKNOWN"`; row predicates always store string literals.
- `maiden_name` and `birth_date` are passed from the CSV even if `"UNKNOWN"`; this can result in:
  - `abi:maiden_name "UNKNOWN"`
  - `abi:birth_date ""^^xsd:date` (if birth date parsing fails)
- `run()` repeatedly calls `unzip_export()` to fetch metadata; behavior depends on the integration implementation.
- Inserts into graph name `http://ontology.naas.ai/graph/default` unconditionally.
