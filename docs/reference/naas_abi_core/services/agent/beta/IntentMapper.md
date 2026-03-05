# IntentMapper

## What it is
- A small intent-matching utility that:
  - Indexes a list of `Intent` objects in an in-memory `VectorStore` using embeddings.
  - Retrieves the most similar intents to an input string (intent text or raw user prompt).
- It also initializes an LLM client (`ChatOpenAI` or an airgapped local alternative), but the current `map_prompt` implementation does **not** call the LLM.

## Public API

### Enums
- `IntentScope`
  - `DIRECT`, `ALL`
- `IntentType`
  - `AGENT`, `TOOL`, `RAW`

### Dataclass
- `Intent`
  - Fields:
    - `intent_value: str` — canonical text for the intent (used for embedding/indexing).
    - `intent_type: IntentType` — classification of the intent target.
    - `intent_target: Any` — arbitrary target object associated with the intent.
    - `intent_scope: Optional[IntentScope] = IntentScope.ALL` — scope metadata.

### Class: `IntentMapper`
- `__init__(intents: list[Intent])`
  - Builds a `VectorStore` and indexes `intent.intent_value` for all provided intents.
  - Determines embedding dimension from `EMBEDDINGS_MODELS_DIMENSIONS_MAP` keyed by `Embeddings._model_name`; raises if unset.
  - Initializes `self.model` depending on environment (see Dependencies).
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
- Environment variables:
  - `AI_MODE="airgap"`: uses `naas_abi_core.services.agent.beta.LocalModel.AirgapChatOpenAI` with a local base URL (`http://localhost:12434/engines/v1`).
  - `OPENROUTER_API_KEY`: if set (and not in airgap mode), uses OpenRouter via `ChatOpenAI(..., base_url="https://openrouter.ai/api/v1")`.
  - Otherwise falls back to `ChatOpenAI(model="gpt-4.1-mini")`.
- Embeddings/vector store dependencies (imported from sibling modules):
  - `Embeddings._model_name` (must be non-`None`, else `ValueError`)
  - `EMBEDDINGS_MODELS_DIMENSIONS_MAP`
  - `embeddings(text: str)`, `embeddings_batch(texts: list[str])`
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
- `Embeddings._model_name` must be set; otherwise `IntentMapper(...)` raises `ValueError("Embeddings model name is not set")`.
- `map_prompt` does not use the configured LLM; it only does embedding similarity against `intent_value` strings and returns `([], prompt_results)`.
- Returned items from `map_intent`/`map_prompt` are dicts whose base shape is determined by `VectorStore.similarity_search`; this module only adds an `"intent"` key.
