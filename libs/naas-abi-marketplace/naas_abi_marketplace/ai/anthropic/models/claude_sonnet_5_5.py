from langchain_anthropic import ChatAnthropic
from naas_abi_core.models.Model import (
    CanonicalModelId,
    ChatModel,
    ModelDefinition,
    ModelProvider,
)
from naas_abi_marketplace.ai.anthropic import ABIModule
from pydantic import SecretStr

EFFORT = "high"


class ClaudeSonnet55Model(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.CLAUDE_SONNET_5_5
    MODEL_ID = "claude-sonnet-5-5"
    PROVIDER = ModelProvider.ANTHROPIC

    # Claude Sonnet 5.5 runs adaptive thinking by default. `thinking: disabled`
    # returns a 400 (use {"type": "between_tools"} at effort <= high to turn it
    # off); temperature/top_p/top_k and forced tool_choice ("any"/"tool") also 400.
    model: ChatModel = ChatModel(
        model_id=MODEL_ID,
        provider=PROVIDER,
        model=ChatAnthropic(
            model_name=MODEL_ID,
            max_retries=2,
            # Explicit, otherwise langchain_anthropic defaults max_tokens to 1024,
            # which thinking can exhaust and truncate the visible answer. Kept
            # under ~21K so the SDK accepts it on non-streaming calls.
            # Use the pydantic field alias; mypy rejects the `max_tokens` kwarg.
            max_tokens_to_sample=16000,
            thinking={"type": "adaptive"},
            model_kwargs={"output_config": {"effort": EFFORT}},
            api_key=SecretStr(ABIModule.get_instance().configuration.anthropic_api_key),
            timeout=None,
            stop=None,
        ),
        context_window=1000000,
        name="Sonnet 5.5",
        owner="anthropic",
        description="The current Sonnet: speed and capability for everyday agent work.",
        pricing={
            "prompt": "0.000002",
            "completion": "0.00001",
            "input_cache_read": "0.0000002",
        },
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
            "effort": EFFORT,
            "comparative_latency": "fast",
            "max_output_tokens": 128000,
        },
    )


model: ChatModel = ClaudeSonnet55Model.model
