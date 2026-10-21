# ToVectorBasePipeline

## What it is
- A base `Pipeline` for:
  - Discovering files of a configured MIME type from an RDF triple store.
  - Loading file bytes from object storage.
  - Chunking content (implemented by subclasses).
  - Embedding chunks using OpenAI embeddings with a KV-cache.
  - Persisting chunk RDF (`Chunk` ontology) into the document graph.
  - Upserting vectors + metadata into a vector store collection.

## Public API
- **`ChunkInfo` (dataclass)**
  - Represents a single chunk to embed/store.
  - Fields:
    - `text: str` — chunk text to embed and store.
    - `extra_metadata: dict[str, Any]` — additional metadata merged into vector metadata.

- **`ToVectorBasePipelineConfiguration` (dataclass, `PipelineConfiguration`)**
  - Static configuration for `ToVectorBasePipeline` and subclasses.
  - Fields:
    - `api_key: str`
    - `mime_type: str`
    - `collection_name: str` (default `"documents"`)
    - `file_path: str` (substring filter for `doc:path`)
    - `model_id: str` (default `"text-embedding-3-small"`)
    - `dimension: int` (default `1536`)
    - `chunk_size: int` (default `1000`)
    - `chunk_overlap: int` (default `200`)

- **`ToVectorBasePipelineParameters` (`PipelineParameters`)**
  - Runtime parameters:
    - `graph_name: str` — RDF graph containing document triples (default `http://ontology.naas.ai/graph/document`)

- **`ToVectorBasePipeline` (`Pipeline`)**
  - `chunk_content(content: bytes, file_path: str) -> list[ChunkInfo]`
    - **Abstract / required**: subclasses must implement.
  - `run(parameters: PipelineParameters) -> rdflib.Graph`
    - Executes the end-to-end vectorization process and returns a combined RDF graph of inserted chunks.
  - `as_tools() -> list[BaseTool]`
    - Exposes the pipeline as a LangChain `StructuredTool` using `ToVectorBasePipelineParameters`.
  - `as_api(...) -> None`
    - Not implemented (always returns `None`).

## Configuration/Dependencies
- Requires an `ABIModule` instance providing engine services:
  - `triple_store.query(...)`, `triple_store.insert(...)`
  - `object_storage.get_object(prefix, key)`
  - `vector_store.ensure_collection(...)`, `vector_store.add_documents(...)`
  - `kv.get(key)`, `kv.set(key, value)` for embedding cache
- Uses `langchain_openai.OpenAIEmbeddings`:
  - Constructed with `model=<model_id>`, `dimensions=<dimension>`, `api_key=SecretStr(api_key)`
- Cache key format:
  - `{model_id}_{dimension}_{sha256_hex(text.encode("utf-8"))}`

## Usage
Minimal subclass example (implements chunking) and invocation:

```python
from naas_abi_marketplace.domains.signals.pipelines.document.pipelines.ToVectorBasePipeline import (
    ToVectorBasePipeline,
    ToVectorBasePipelineConfiguration,
    ToVectorBasePipelineParameters,
    ChunkInfo,
)

class PlainTextToVectorPipeline(ToVectorBasePipeline):
    def chunk_content(self, content: bytes, file_path: str):
        text = content.decode("utf-8", errors="ignore")
        # Minimal chunking: single chunk
        return [ChunkInfo(text=text)]

cfg = ToVectorBasePipelineConfiguration(
    api_key="YOUR_OPENAI_API_KEY",
    mime_type="text/plain",
    collection_name="documents",
)

pipeline = PlainTextToVectorPipeline(cfg)
graph = pipeline.run(ToVectorBasePipelineParameters())
```

## Caveats
- Files are **skipped** if the triple store already contains at least one `doc:Chunk` for the file **and** the configured `collection_name`.
- `file_path` configuration is a substring filter applied to `doc:path` via SPARQL `CONTAINS`.
- If KV cache retrieval/parsing fails, embeddings are recomputed silently (cache miss behavior).
- `as_api` is not exposed (no HTTP route setup).
