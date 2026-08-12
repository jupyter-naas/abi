# `defaults` (Ollama model tag constants)

## What it is
A small, dependency-free module that defines the default and fallback Ollama model tags used by the project (including components outside this package) without requiring any `ai-ollama` extras.

## Public API
Exported constants:

- `DEFAULT_CHAT_MODEL_TAG: str`  
  - Default local chat model tag (also used for tool-binding agents).
- `DEFAULT_EMBEDDING_MODEL_TAG: str`  
  - Default local embedding model tag (required for vector-store functionality in keyless setups).
- `FALLBACK_CHAT_MODEL_TAGS: tuple[str, ...]`  
  - Ordered fallback chat model tags to try when selecting “some local model”. Preference is tool-calling ability first, then size.

## Configuration/Dependencies
- No third-party imports.
- Values are plain strings intended to be consumed by other modules/services (e.g., a Nexus API layer).

## Usage
```python
from naas_abi_marketplace.ai.ollama.defaults import (
    DEFAULT_CHAT_MODEL_TAG,
    DEFAULT_EMBEDDING_MODEL_TAG,
    FALLBACK_CHAT_MODEL_TAGS,
)

print("Default chat:", DEFAULT_CHAT_MODEL_TAG)
print("Default embedding:", DEFAULT_EMBEDDING_MODEL_TAG)

# Example selection logic: pick the first available model tag
available = {"llama3.2:1b", "qwen2.5:1.5b"}  # e.g., from local Ollama inventory
selected = next((tag for tag in FALLBACK_CHAT_MODEL_TAGS if tag in available), None)
print("Selected chat:", selected)
```

## Caveats
- These are tags only; the module does not validate availability or pull models.
- Keep imports dependency-free: do not add imports that require optional Ollama/LangChain extras.
