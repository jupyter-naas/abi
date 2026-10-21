# CreateClassEmbeddingsWorkflow

## What it is
A workflow that:
- Queries a triple store for all entities of a given RDF class (`a {class_uri}`), including optional `owl:DatatypeProperty` values.
- Creates OpenAI embeddings from each entity’s `rdfs:label`.
- Stores embeddings and metadata in a vector store collection, skipping entities already present.
- Optionally creates a LangChain `StructuredTool` to run similarity search against the stored embeddings.

## Public API

### Classes

- `CreateClassEmbeddingsWorkflowConfiguration(WorkflowConfiguration)`
  - Holds required services and embedding settings.
  - Fields:
    - `triple_store: ITripleStoreService`
    - `vector_store: VectorStoreService`
    - `embeddings_model_name: str = "text-embedding-3-large"`
    - `embeddings_dimension: int = 3072`

- `CreateClassEmbeddingsWorkflowParameters(WorkflowParameters)`
  - Input parameters for embedding creation.
  - Fields:
    - `class_uri: str` — RDF class URI used in SPARQL.
    - `collection_name: str` — vector store collection name.
    - `entity_variable_name: str` — SPARQL variable name for the entity (e.g. `"person"`).
    - `entity_type_label: str` — label used in logs (e.g. `"person"`).

- `CreateClassEmbeddingsWorkflow(Workflow)`
  - Main workflow implementation.

### Methods (CreateClassEmbeddingsWorkflow)

- `create_class_embeddings(parameters: CreateClassEmbeddingsWorkflowParameters) -> dict[str, Any]`
  - Ensures the vector collection exists (cosine distance; configured dimension).
  - Queries the triple store for entity URI + `rdfs:label` and optional datatype properties.
  - Skips entities already stored in the vector store by checking `document_id = uri.split("/")[-1]`.
  - Embeds only new entity labels and stores vectors + metadata.
  - Returns:
    - When nothing found / nothing new: `{"status": "success", "entities_processed": 0}`
    - When embeddings added: includes `collection_name` and `entity_type`.

- `create_search_tool(collection_name: str, search_param_name: str, tool_name: str, tool_description: str, entity_type_label: str) -> StructuredTool`
  - Builds a LangChain `StructuredTool` that:
    - Accepts a dynamically named search parameter (e.g. `"person_name"`) and `k` (default `5`, bounds `1..20`).
    - Embeds the query (`embed_query`) and searches the vector store.
    - Returns a list of `{uri, label, score}` (from stored metadata), or `{"error": ...}` on failure.

- `as_tools() -> list[BaseTool]`
  - Exposes a LangChain tool:
    - Name: `"create_class_embeddings"`
    - Args schema: `CreateClassEmbeddingsWorkflowParameters`
    - Calls `create_class_embeddings(...)`.

- `as_api(...) -> None`
  - Declared but not implemented (`pass`).

## Configuration/Dependencies
- Services:
  - `ITripleStoreService` with `query(sparql: str)`.
  - `VectorStoreService` with:
    - `ensure_collection(collection_name, dimension, distance_metric)`
    - `get_document(collection_name, document_id, include_vector=False)`
    - `add_documents(collection_name, ids, vectors, metadata)`
    - `search_similar(collection_name, query_vector, k, include_metadata=True)`
- Embeddings:
  - `langchain_openai.OpenAIEmbeddings(model=embeddings_model_name)`
  - Uses:
    - `embed_documents(list[str])` for batch embedding
    - `embed_query(str)` for search
- Utilities:
  - `SPARQLUtils(...).results_to_list(...)` to normalize triple store query results.
- Data handling:
  - Converts embeddings to `numpy.array` before storage.

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

print(tool.func(person_name="Ada Lovelace", k=5))
```

## Caveats
- Document IDs are derived from `uri.split("/")[-1]`; URIs without `/` or with non-unique trailing segments can collide.
- Embeddings are computed only from `rdfs:label`; datatype properties are stored as metadata but not embedded.
- `as_api()` is not implemented.
