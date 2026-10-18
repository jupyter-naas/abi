# IntentMapper

## What it is
- An async, embedding-based intent matcher that ranks a prompt against a fixed list of `Intent` objects using cosine similarity.
- Builds an in-memory index of embedding vectors (no external vector DB).

## Public API
- `class IntentMapper(intents: list[Intent], embedding_model: Any | None = None)`
  - Holds intents and lazily builds their embedding vectors on first use.
- `async IntentMapper.map_intent(text: str, k: int = 1) -> list[dict]`
  - Returns the top-`k` matching intents with cosine similarity scores.
  - Each result dict contains:
    - `text`: the matched intent’s `intent_value`
    - `metadata`: `{"index": <intent_index>}`
    - `score`: cosine similarity (float)
    - `intent`: the original `Intent` instance
- `async IntentMapper.map_prompt(prompt: str, k: int = 1) -> tuple[list[dict], list[dict]]`
  - Returns a tuple: `([], <intent_matches>)`. The first element is always an empty list.

## Configuration/Dependencies
- Requires:
  - `naas_abi_sdk.agents.intents.Intent` (each intent must expose `intent_value`).
  - An `embedding_model` providing async methods:
    - `aembed_documents(list[str]) -> list[list[float]]`
    - `aembed_query(str) -> list[float]`
- Internal behavior:
  - Intent embeddings are computed once and cached in memory.
  - Index build is guarded by an `asyncio.Lock()`.

## Usage
```python
import asyncio
from naas_abi_sdk.agents.intent_mapper import IntentMapper
from naas_abi_sdk.agents.intents import Intent

# Minimal embedding model stub (replace with a real async embeddings implementation)
class DummyEmbeddings:
    async def aembed_documents(self, texts):
        return [[float(len(t))] for t in texts]
    async def aembed_query(self, text):
        return [float(len(text))]

async def main():
    intents = [Intent(intent_value="hello"), Intent(intent_value="goodbye")]
    mapper = IntentMapper(intents, embedding_model=DummyEmbeddings())

    matches = await mapper.map_intent("hi there", k=1)
    print(matches[0]["text"], matches[0]["score"])

asyncio.run(main())
```

## Caveats
- If `embedding_model` is not provided and intents are non-empty, `map_intent()` raises `RuntimeError`.
- If the embedding model returns empty vectors (e.g., `[]` or `[[]]`), index build raises `ValueError`.
- If `intents` is empty, `map_intent()` returns `[]`.
- Cosine similarity uses `zip(a, b)`; if query and document vectors differ in length, extra dimensions are ignored.
