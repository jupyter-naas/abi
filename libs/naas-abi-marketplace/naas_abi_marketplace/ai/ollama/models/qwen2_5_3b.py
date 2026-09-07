"""Qwen2.5 3B — the default local chat model for a new project.

Chosen as the keyless default because it is small enough (3.1B, ~1.9GB) to run
on an ordinary laptop *and* advertises tool calling, which lets a single local
model serve both plain conversation and the agents that bind tools
(AbiAgent, OntologyEngineerAgent). A completion-only model would have forced a
second download just to keep the agent layer working.

On multi-tool routing (8 tools) this scored 8/8; ``qwen2.5:1.5b`` (~1GB) managed
6/8, twice answering in prose instead of calling a tool. Treat the 1.5B as a
constrained-hardware fallback rather than an equivalent; swap it in via the
module's provider factory::

    registry.get_chat_model("qwen2.5:1.5b", provider="ollama")
"""

from langchain_ollama import ChatOllama
from naas_abi_core.models.Model import (
    CanonicalModelId,
    ChatModel,
    ModelDefinition,
    ModelProvider,
)
from naas_abi_marketplace.ai.ollama import ABIModule
from naas_abi_marketplace.ai.ollama.defaults import DEFAULT_CHAT_MODEL_TAG


class Qwen25ThreeBModel(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.QWEN_2_5_3B
    MODEL_ID = DEFAULT_CHAT_MODEL_TAG
    # Declared once and passed to both the metadata and the client, so the
    # advertised window and the one Ollama actually allocates cannot drift.
    CONTEXT_WINDOW = 32768
    PROVIDER = ModelProvider.OLLAMA

    model: ChatModel = ChatModel(
        model_id=MODEL_ID,
        provider=PROVIDER,
        name="Qwen2.5 3B",
        owner="alibaba",
        description=(
            "Alibaba's Qwen2.5 3B running locally via Ollama. Small enough for "
            "consumer hardware, 32k context, and supports tool calling — so it "
            "can back both chat and tool-using agents with no API key."
        ),
        image="https://naasai-public.s3.eu-west-3.amazonaws.com/logos/ollama_100x100.png",
        context_window=CONTEXT_WINDOW,
        model=ChatOllama(
            model=MODEL_ID,
            base_url=ABIModule.resolved_base_url(),
            temperature=0,
            # Ollama defaults to a 4096-token context regardless of what the
            # model supports, and truncates silently. Without this the 32k
            # advertised above is a lie: `ollama ps` reports CONTEXT 4096, and
            # long conversations or tool-heavy prompts lose their head with no
            # error. Costs ~1GB of extra KV cache (2.2GB -> 3.2GB resident).
            num_ctx=CONTEXT_WINDOW,
        ),
    )


# Back-compat for direct importers.
model: ChatModel = Qwen25ThreeBModel.model
