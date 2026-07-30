"""Qwen2.5-Coder 3B — the default local chat model for a new project.

Code-tuned, 32k context, ~1.9GB, which suits a developer-facing platform: most
of what people ask an ABI project to do is write pipelines, workflows, SPARQL
and ontology code.

**It cannot back a tool-using agent.** Ollama advertises a ``tools`` capability
for this model, but the capability flag is misleading: the coder fine-tune emits
tool calls as bare JSON in the message body instead of wrapping them in the
``<tool_call>`` tags its own chat template expects, so Ollama never parses them
into the structured ``tool_calls`` field and LangGraph never sees a tool call.
Measured over identical prompts and tool bindings:

    qwen2.5-coder:7b   0/3 structured tool calls
    qwen2.5-coder:3b   0/3 structured tool calls
    qwen2.5:3b         3/3 structured tool calls

The 7B behaving no better than the 3B is why this ships at 3B — the extra 2.8GB
buys nothing for the tool problem. Agents that bind tools (AbiAgent,
OntologyEngineerAgent) therefore point at :mod:`qwen2_5_3b` instead; see the
module README.
"""

from langchain_ollama import ChatOllama
from naas_abi_core.models.Model import (
    CanonicalModelId,
    ChatModel,
    ModelDefinition,
    ModelProvider,
)
from naas_abi_marketplace.ai.ollama import ABIModule


class Qwen25Coder3BModel(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.QWEN_2_5_CODER_3B
    MODEL_ID = "qwen2.5-coder:3b"
    PROVIDER = ModelProvider.OLLAMA

    model: ChatModel = ChatModel(
        model_id=MODEL_ID,
        provider=PROVIDER,
        name="Qwen2.5-Coder 3B",
        owner="alibaba",
        description=(
            "Alibaba's Qwen2.5-Coder 3B running locally via Ollama. Code-tuned "
            "with a 32k context and no API key. Does not reliably emit "
            "structured tool calls, so tool-using agents need a general model."
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
model: ChatModel = Qwen25Coder3BModel.model
