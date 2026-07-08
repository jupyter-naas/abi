from langchain_anthropic import ChatAnthropic
from naas_abi_core.models.Model import (
    CanonicalModelId,
    ChatModel,
    ModelDefinition,
    ModelProvider,
)
from naas_abi_marketplace.ai.anthropic import ABIModule
from pydantic import SecretStr


class ClaudeFable5Model(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.CLAUDE_FABLE_5
    MODEL_ID = "claude-fable-5"
    PROVIDER = ModelProvider.ANTHROPIC

    # Claude Fable 5 has thinking always on and rejects sampling parameters
    # (temperature/top_p/top_k) with a 400 — do not pass temperature.
    model: ChatModel = ChatModel(
        model_id=MODEL_ID,
        provider=PROVIDER,
        model=ChatAnthropic(
            model_name=MODEL_ID,
            max_retries=2,
            api_key=SecretStr(ABIModule.get_instance().configuration.anthropic_api_key),
            timeout=None,
            stop=None,
        ),
        context_window=1000000,
        name="Fable 5",
        owner="anthropic",
        description="Next-generation intelligence for long-running agents.",
        pricing={"prompt": "0.00001", "completion": "0.00005"},
        top_provider={
            "context_length": 1000000,
            "max_completion_tokens": 128000,
            "is_moderated": False,
        },
        architecture={
            "modality": "text+image->text",
            "input_modalities": ["text", "image"],
            "output_modalities": ["text"],
            "tokenizer": "Claude",
            "extended_thinking": False,
            "adaptive_thinking": "always_on",
            "comparative_latency": "slower",
            "max_output_tokens": 128000,
            "knowledge_cutoff": "2026-01",
            "training_cutoff": "2026-01",
        },
    )


model: ChatModel = ClaudeFable5Model.model
