"""Llama 3.2 3B — the local model for agents that need tools.

Phi-3.5 is the default chat model, but Ollama reports its capabilities as
``completion`` only: an agent that binds tools cannot use it. Llama 3.2 3B
advertises ``tools``, is a comparable size (~2GB), and is therefore what the
tool-using agents (AbiAgent, OntologyEngineerAgent) point at so a keyless
project has a working agent layer and not just a working chat box.
"""

from langchain_ollama import ChatOllama
from naas_abi_core.models.Model import (
    CanonicalModelId,
    ChatModel,
    ModelDefinition,
    ModelProvider,
)
from naas_abi_marketplace.ai.ollama import ABIModule


class Llama32Model(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.LLAMA_3_2
    MODEL_ID = "llama3.2"
    PROVIDER = ModelProvider.OLLAMA

    model: ChatModel = ChatModel(
        model_id=MODEL_ID,
        provider=PROVIDER,
        name="Llama 3.2 3B",
        owner="meta",
        description=(
            "Meta's Llama 3.2 3B running locally via Ollama. Supports tool "
            "calling, so it can back agents that bind tools — unlike Phi-3.5, "
            "which is completion-only."
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
model: ChatModel = Llama32Model.model
