from langchain_anthropic import ChatAnthropic
from naas_abi_core.models.Model import (
    CanonicalModelId,
    ChatModel,
    ModelDefinition,
    ModelProvider,
)
from naas_abi_marketplace.ai.anthropic import ABIModule
from pydantic import SecretStr


class ClaudeHaiku45Model(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.CLAUDE_HAIKU_4_5
    MODEL_ID = "claude-haiku-4-5-20251001"
    PROVIDER = ModelProvider.ANTHROPIC

    model: ChatModel = ChatModel(
        model_id=MODEL_ID,
        provider=PROVIDER,
        model=ChatAnthropic(
            model_name=MODEL_ID,
            temperature=0,
            max_retries=2,
            # Explicit — otherwise langchain_anthropic defaults max_tokens to 1024,
            # which extended thinking can exhaust and truncate the visible answer.
            # Use the pydantic field alias; mypy rejects the `max_tokens` kwarg.
            max_tokens_to_sample=8192,
            api_key=SecretStr(ABIModule.get_instance().configuration.anthropic_api_key),
            timeout=None,
            stop=None,
        ),
        context_window=200000,
        name="Haiku 4.5",
        owner="anthropic",
        description="The fastest model with near-frontier intelligence.",
        pricing={"prompt": "0.000001", "completion": "0.000005"},
        top_provider={
            "context_length": 200000,
            "max_completion_tokens": 64000,
            "is_moderated": False,
        },
        architecture={
            "modality": "text+image->text",
            "input_modalities": ["text", "image"],
            "output_modalities": ["text"],
            "tokenizer": "Claude",
            "extended_thinking": True,
            "adaptive_thinking": False,
            "comparative_latency": "fastest",
            "max_output_tokens": 64000,
            "knowledge_cutoff": "2025-02",
            "training_cutoff": "2025-07",
        },
    )


model: ChatModel = ClaudeHaiku45Model.model
