from langchain_anthropic import ChatAnthropic
from naas_abi_core.models.Model import (
    CanonicalModelId,
    ChatModel,
    ModelDefinition,
    ModelProvider,
)
from naas_abi_marketplace.ai.anthropic import ABIModule
from pydantic import SecretStr


class ClaudeOpus48Model(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.CLAUDE_OPUS_4_8
    MODEL_ID = "claude-opus-4-8"
    PROVIDER = ModelProvider.ANTHROPIC

    model: ChatModel = ChatModel(
        model_id=MODEL_ID,
        provider=PROVIDER,
        model=ChatAnthropic(
            model_name=MODEL_ID,
            max_retries=2,
            # Explicit — otherwise langchain_anthropic defaults max_tokens to 1024,
            # which adaptive thinking can exhaust and truncate the visible answer.
            max_tokens=8192,
            api_key=SecretStr(ABIModule.get_instance().configuration.anthropic_api_key),
            timeout=None,
            stop=None,
        ),
        context_window=1000000,
        name="Opus 4.8",
        owner="anthropic",
        description="For complex agentic coding and enterprise work.",
        pricing={"prompt": "0.000005", "completion": "0.000025"},
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
            "adaptive_thinking": True,
            "comparative_latency": "moderate",
            "max_output_tokens": 128000,
            "knowledge_cutoff": "2026-01",
            "training_cutoff": "2026-01",
        },
    )


model: ChatModel = ClaudeOpus48Model.model
