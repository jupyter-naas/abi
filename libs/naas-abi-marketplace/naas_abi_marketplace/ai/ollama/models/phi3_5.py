"""Microsoft Phi-3.5 mini — the default local chat model for a new project.

Chosen as the keyless default because it is small enough (3.8B, ~2.2GB) to run
on an ordinary laptop while still carrying a 128k context window.

Caveat worth knowing: Ollama reports Phi-3.5's capabilities as ``completion``
only — it does **not** do tool calling. That is fine for conversational agents
(the scaffolded project agent binds no tools), but an agent that needs tools
should ask the registry for a tool-capable model instead::

    registry.get_chat_model("llama3.2", provider="ollama")

which the module's provider factory serves without needing a model file.
"""

from langchain_ollama import ChatOllama
from naas_abi_core.models.Model import (
    CanonicalModelId,
    ChatModel,
    ModelDefinition,
    ModelProvider,
)
from naas_abi_marketplace.ai.ollama import ABIModule


class Phi35Model(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.PHI_3_5
    MODEL_ID = "phi3.5"
    PROVIDER = ModelProvider.OLLAMA

    model: ChatModel = ChatModel(
        model_id=MODEL_ID,
        provider=PROVIDER,
        name="Phi-3.5 Mini",
        owner="microsoft",
        description=(
            "Microsoft's Phi-3.5 Mini (3.8B) running locally via Ollama. Small "
            "enough for consumer hardware, with a 128k context window. "
            "Completion-only — no tool calling."
        ),
        image="https://naasai-public.s3.eu-west-3.amazonaws.com/logos/ollama_100x100.png",
        context_window=131072,
        model=ChatOllama(
            model=MODEL_ID,
            base_url=ABIModule.resolved_base_url(),
            temperature=0,
        ),
    )


# Back-compat for direct importers.
model: ChatModel = Phi35Model.model
