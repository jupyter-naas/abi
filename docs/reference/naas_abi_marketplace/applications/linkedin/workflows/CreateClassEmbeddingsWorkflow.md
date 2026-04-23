# CreateClassEmbeddingsWorkflow

## What it is
A workflow that:
- Queries a triple store for all entities of a given RDF class (plus their datatype properties).
- Creates OpenAI embeddings from each entity’s `rdfs:label`.
- Stores new embeddings (skipping already-indexed entities) into a vector store collection.
- Optionally builds a LangChain `StructuredTool` for similarity search over a collection.

## Public API

### Classes

- `CreateClassEmbeddingsWorkflowConfiguration(WorkflowConfiguration)`
  - Holds required services and embedding settings.
  - Fields:
    - `triple_store: ITripleStoreService` (required)
    - `vector_store: VectorStoreService` (required)
    - `embeddings_model_name: str = "text-embedding-3-large"`
    - `embeddings_dimension: int = 3072`

- `CreateClassEmbeddingsWorkflowParameters(WorkflowParameters)`
  - Input parameters for embedding creation.
  - Fields:
    - `class_uri: str` — RDF class URI used in SPARQL `a {class_uri}`.
    - `collection_name: str` — vector store collection name.
    - `entity_variable_name: str` — SPARQL variable name for the entity (e.g. `"person"`).
    - `entity_type_label: str` — label used in logs (e.g. `"person"`).

- `CreateClassEmbeddingsWorkflow(Workflow)`
  - Main workflow implementation.

### Methods (CreateClassEmbeddingsWorkflow)

- `create_class_embeddings(parameters: CreateClassEmbeddingsWorkflowParameters) -> Dict[str, Any]`
  - Ensures the target vector collection exists (cosine distance; configured dimension).
  - Queries the triple store for:
    - entity URI, `rdfs:label`, and all `owl:DatatypeProperty` values (optional).
  - Creates embeddings for **new** entities only (based on `document_id = uri.split("/")[-1]`).
  - Stores vectors and metadata in the vector store.
  - Returns a status dict including `entities_processed` and, when embeddings were added, `collection_name` and `entity_type`.

- `create_search_tool(collection_name: str, search_param_name: str, tool_name: str, tool_description: str, entity_type_label: str) -> StructuredTool`
  - Builds a LangChain `StructuredTool` that:
    - Accepts a dynamically named query parameter (e.g. `"person_name"`) and `k` (default 5, 1–20).
    - Embeds the query text and runs vector similarity search.
    - Returns a list of `{uri, label, score}` from stored metadata.

- `as_tools() -> list[BaseTool]`
  - Exposes the workflow as a LangChain tool:
    - Tool name: `"create_class_embeddings"`
    - Args schema: `CreateClassEmbeddingsWorkflowParameters`

- `as_api(...) -> None`
  - Declared but not implemented (`pass`).

## Configuration/Dependencies
- Requires:
  - `ITripleStoreService` for SPARQL querying (`query()`).
  - `VectorStoreService` for collection management and vector operations:
    - `ensure_collection(...)`
    - `get_document(...)`
    - `add_documents(...)`
    - `search_similar(...)`
- Uses OpenAI embeddings via `langchain_openai.OpenAIEmbeddings` with `embeddings_model_name`.
- Uses `numpy` to convert embedding lists to arrays before storage.
- Uses `SPARQLUtils(...).results_to_list(...)` to normalize triple store query results.

## Usage

### Create embeddings for a class
```python
from naas_abi_core.engine.Engine import Engine
from naas_abi_marketplace.applications.linkedin import ABIModule
from naas_abi_marketplace.applications.linkedin.workflows.CreateClassEmbeddingsWorkflow import (
    CreateClassEmbeddingsWorkflow,
    CreateClassEmbeddingsWorkflowConfiguration,
    CreateClassEmbeddingsWorkflowParameters,
)

engine = Engine()
engine.load(module_names=["naas_abi_marketplace.applications.linkedin"])
module: ABIModule = ABIModule.get_instance()

cfg = CreateClassEmbeddingsWorkflowConfiguration(
    triple_store=module.engine.services.triple_store,
    vector_store=module.engine.services.vector_store,
)

wf = CreateClassEmbeddingsWorkflow(cfg)
result = wf.create_class_embeddings(
    CreateClassEmbeddingsWorkflowParameters(
        class_uri="cco:ont00001262",
        collection_name="linkedin_persons",
        entity_variable_name="person",
        entity_type_label="person",
    )
)
print(result)
```

### Create a similarity search tool
```python
tool = wf.create_search_tool(
    collection_name="linkedin_persons",
    search_param_name="person_name",
    tool_name="search_person",
    tool_description="Search persons by name using embeddings.",
    entity_type_label="person",
)

# Call tool function directly (LangChain integration may vary)
print(tool.func(person_name="Ada Lovelace", k=5))
```

## Caveats
- Document IDs are derived from `uri.split("/")[-1]`; URIs not containing `/` or requiring different ID logic may collide or behave unexpectedly.
- Embeddings are computed only from `rdfs:label`; datatype properties are stored as metadata but not embedded.
- `as_api()` is not implemented.
