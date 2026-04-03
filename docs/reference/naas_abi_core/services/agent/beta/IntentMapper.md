# IntentMapper

## What it is
- A small intent-matching utility that:
  - Indexes a list of `Intent` objects in an in-memory `VectorStore` using embeddings.
  - Retrieves the most similar intents to an input string (intent text or raw user prompt).
- It also initializes an LLM client (`ChatOpenAI`), but the current `map_prompt` implementation does **not** call the LLM.

## Public API

### Enums
- `IntentScope`
  - `DIRECT`, `ALL`
- `IntentType`
  - `AGENT`, `TOOL`, `RAW`

### Dataclass
- `Intent`
  - Fields:
    - `intent_value: str` - canonical text for the intent (used for embedding/indexing).
    - `intent_type: IntentType` - classification of the intent target.
    - `intent_target: Any` - arbitrary target object associated with the intent.
    - `intent_scope: Optional[IntentScope] = IntentScope.ALL` - scope metadata.

### Class: `IntentMapper`
- `__init__(intents: list[Intent], embedding_model: Embeddings | None = None)`
  - Builds a `VectorStore` and indexes `intent.intent_value` for all provided intents.
  - If `embedding_model` is provided, uses it for document/query embeddings.
  - If `embedding_model` is `None`, logs a warning and instantiates `OpenAIEmbeddings(model="text-embedding-3-large")`.
  - Defers `VectorStore` creation until embeddings are computed, then infers vector dimension from the first vector.
  - Initializes `self.model = ChatOpenAI(model="gpt-4.1-mini")`.
  - Sets a `system_prompt` string (not used by current mapping methods).
- `get_intent_from_value(value: str) -> Intent | None`
  - Returns the `Intent` whose `intent_value` exactly matches `value`, else `None`.
- `map_intent(intent: str, k: int = 1) -> list[dict]`
  - Performs vector similarity search over indexed intents for the given text.
  - Augments each result dict with `result["intent"]` containing the matched `Intent` object.
- `map_prompt(prompt: str, k: int = 1) -> Tuple[list[dict], list[dict]]`
  - Maps the raw prompt directly via `map_intent`.
  - Returns a tuple: `([], prompt_results)` (first element always empty in current implementation).

## Configuration/Dependencies
- Embeddings/vector store dependencies:
  - Optional custom `embedding_model` implementing LangChain `Embeddings`
  - `OpenAIEmbeddings` for default fallback behavior
  - `VectorStore` with:
    - `add_texts(texts, embeddings=..., metadatas=...)`
    - `similarity_search(query_embedding, k=...)`

## Usage
```python
from naas_abi_core.services.agent.beta.IntentMapper import Intent, IntentMapper, IntentType

intents = [
    Intent(intent_value="write a report", intent_type=IntentType.AGENT, intent_target="report_agent"),
    Intent(intent_value="calculate an arithmetic result", intent_type=IntentType.TOOL, intent_target="calculator"),
]

mapper = IntentMapper(intents)

results = mapper.map_intent("I need to write a report about AI trends", k=1)
top = results[0]["intent"]
print(top.intent_value)     # e.g. "write a report"
print(top.intent_type)      # IntentType.AGENT
print(top.intent_target)    # "report_agent"

_, prompt_results = mapper.map_prompt("3 / 4 + 5", k=1)
print(prompt_results[0]["intent"].intent_value)
```

## Caveats
- If `embedding_model` is not provided, a warning is logged and `OpenAIEmbeddings(model="text-embedding-3-large")` is used.
- The internal `VectorStore` is initialized only after embeddings are generated, and its dimension is inferred from the first vector.
- `map_prompt` does not use the configured LLM; it only does embedding similarity against `intent_value` strings and returns `([], prompt_results)`.
- Returned items from `map_intent`/`map_prompt` are dicts whose base shape is determined by `VectorStore.similarity_search`; this module only adds an `"intent"` key.
