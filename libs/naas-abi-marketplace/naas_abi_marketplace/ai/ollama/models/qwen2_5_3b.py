"""Qwen2.5 3B — the local model behind the tool-using agents.

The default *chat* model is Qwen2.5-Coder (see :mod:`qwen2_5_coder_3b`), but the
coder fine-tune does not emit structured tool calls, so it cannot drive an agent
that binds tools. This general Qwen2.5 3B does, reliably — 3/3 on identical
prompts where both coder variants scored 0/3 — so ``abi_agent_model`` and
``ontology_engineer_model`` point here.

Same size class as the coder model (3.1B, ~1.9GB, 32k context). For very
constrained machines, ``qwen2.5:1.5b`` (~1GB) is also tool-capable and can be
swapped in via the module's provider factory::

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


class Qwen25ThreeBModel(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.QWEN_2_5_3B
    MODEL_ID = "qwen2.5:3b"
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
        context_window=32768,
        model=ChatOllama(
            model=MODEL_ID,
            base_url=ABIModule.resolved_base_url(),
            temperature=0,
        ),
    )


# Back-compat for direct importers.
model: ChatModel = Qwen25ThreeBModel.model
