"""The model tags a keyless project depends on.

These live in their own module, with **no third-party imports**, for two
reasons:

1. They are needed outside this package. The Nexus API has its own Ollama
   layer (status endpoint, model pull, provider fallback) which used to
   hardcode an unrelated tag, so a user who followed the project README and
   pulled the documented model was told by the UI to pull a different one.
   Both sides now read these constants.
2. Importing them must not require the ``ai-ollama`` extra. Anything that
   touches ``langchain_ollama`` would make the Nexus API's import of these
   values fail on an installation that never enabled this module.
"""

# Serves both plain chat and the tool-binding agents. See models/qwen2_5_3b.py
# for why this specific model, and the README for what it can and cannot do.
DEFAULT_CHAT_MODEL_TAG = "qwen2.5:3b"

# The only local embedding model in the marketplace — without it a keyless
# project has no working vector store.
DEFAULT_EMBEDDING_MODEL_TAG = "nomic-embed-text"

# Ordered fallbacks for "some local model, any local model" — used when
# picking among whatever the user happens to have pulled. Preference order is
# tool-calling ability first, then size.
FALLBACK_CHAT_MODEL_TAGS = (
    DEFAULT_CHAT_MODEL_TAG,
    "qwen2.5:1.5b",
    "qwen2.5",
    "llama3.2:3b",
    "llama3.2:1b",
    "llama3.2",
)

__all__ = [
    "DEFAULT_CHAT_MODEL_TAG",
    "DEFAULT_EMBEDDING_MODEL_TAG",
    "FALLBACK_CHAT_MODEL_TAGS",
]
