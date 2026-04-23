# IntentMapper

## What it is
- A small utility to map an input string (prompt/intent text) to the closest predefined `Intent`(s) using embedding similarity search.
- Builds an in-memory vector index of `Intent.intent_value` strings and returns nearest matches.

## Public API

### Enums
- `IntentScope`
  - `DIRECT`, `ALL`
- `IntentType`
  - `AGENT`, `TOOL`, `RAW`

### Data model
- `@dataclass Intent`
  - `intent_value: str` — text used for indexing/matching
  - `intent_type: IntentType`
  - `intent_target: Any`
  - `intent_scope: Optional[IntentScope] = IntentScope.ALL`

### Class: `IntentMapper`
- `__init__(intents, embedding_model=None, model=None)`
  - Builds an embedding index for `intents` (if any).
  - Defaults:
    - `embedding_model`: `OpenAIEmbeddings(model="text-embedding-3-large")`
    - `model`: `ChatOpenAI(model="gpt-4.1-mini")`
  - Raises `ValueError` if embeddings are empty when building the index.
- `get_intent_from_value(value: str) -> Intent | None`
  - Exact-match lookup in the provided intents list by `intent_value`.
- `map_intent(intent: str, k: int = 1) -> list[dict]`
  - Returns top-`k` similarity results from the vector store.
  - Each result dict is augmented with `result["intent"] = <Intent>`.
  - Returns `[]` if no vector store was built (e.g., no intents provided).
- `map_prompt(prompt: str, k: int = 1) -> Tuple[list[dict], list[dict]]`
  - Maps the raw prompt directly via `map_intent` (no LLM extraction).
  - Returns `([], prompt_results)` to match an expected two-list format.

## Configuration/Dependencies
- Requires LangChain core interfaces and OpenAI integrations:
  - `langchain_core.embeddings.Embeddings`
  - `langchain_core.language_models.chat_models.BaseChatModel`
  - `langchain_openai.OpenAIEmbeddings`, `langchain_openai.ChatOpenAI`
- Uses internal components:
  - `VectorStore` (from `.VectorStore`) for similarity search.
  - `logger` (from `naas_abi_core.utils.Logger`) for warnings when defaults are used.
- If you rely on the default OpenAI models, your environment must be configured for OpenAI access as required by `langchain_openai`.

## Usage

```python
from naas_abi_core.services.agent.beta.IntentMapper import (
    IntentMapper, Intent, IntentType
)

intents = [
    Intent(intent_value="write a report", intent_type=IntentType.AGENT, intent_target=None),
    Intent(intent_value="calculate an arithmetic result", intent_type=IntentType.TOOL, intent_target=None),
]

mapper = IntentMapper(intents=intents)

# Map a user prompt to nearest intent(s)
_, prompt_results = mapper.map_prompt("Can you write a report about AI trends?", k=1)

for r in prompt_results:
    print(r["intent"].intent_value)
```

## Caveats
- If `intents` is empty, no vector index is built and `map_intent`/`map_prompt` return no matches.
- `map_prompt` does not use the configured chat model; it performs direct embedding similarity on the raw prompt.
