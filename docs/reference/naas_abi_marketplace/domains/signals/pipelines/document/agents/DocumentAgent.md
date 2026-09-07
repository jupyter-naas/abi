# DocumentAgent

## What it is
- An `IntentAgent` specialized for answering questions over ingested and vectorized documents.
- Provides a semantic search tool (`search_documents`) backed by a vector store (collections produced by a Markdown-to-vector pipeline).
- Uses a system prompt that instructs the agent to always search first and cite `file_path` sources.

## Public API
- `class DocumentAgent(IntentAgent)`
  - Purpose: Agent type for document Q&A (no additional methods defined in this file).
- `def create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> DocumentAgent`
  - Purpose: Factory that wires models, vector store, tools, and prompts to instantiate `DocumentAgent`.

## Configuration/Dependencies
- **Models/Services (resolved via `ABIModule`)**
  - `ModelRegistryService` (must be initialized):
    - `get_default_chat_model()`
    - `get_default_embedding_model().model` (LangChain `Embeddings`)
  - `vector_store_service` (from `module.engine.services.vector_store`) must implement:
    - `search_similar(collection_name, query_vector, k, include_metadata=True)`
- **Tooling**
  - LangChain `StructuredTool` with `DocumentSearchInput` schema:
    - `query: str` (required)
    - `collection_name: str = "documents"`
    - `k: int = 5` (range 1–20)
- **Other**
  - `numpy` is used to convert embedding vectors to `np.float32`.
  - The system prompt is built from `SYSTEM_PROMPT` by replacing `[TOOLS]` with tool names/descriptions.

## Usage
```python
from naas_abi_marketplace.domains.signals.pipelines.document.agents.DocumentAgent import create_agent

agent = create_agent()

# How you run the agent depends on IntentAgent's interface in naas_abi_core.
# The created agent includes a tool named `search_documents` for semantic retrieval.
```

## Caveats
- `create_agent()` asserts the model registry is initialized (`assert registry is not None`).
- The search tool returns a list of dicts; on errors it returns `[{"error": "..."}]` rather than raising.
- If `query` is empty, the tool returns `[{"error": "query is required"}]`.
- Returned search results include:
  - `score`, `file_path` (defaults to `"unknown"`), `chunk_index` (defaults to `-1`), and `content`.
