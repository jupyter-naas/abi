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


class ClaudeFable51Model(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.CLAUDE_FABLE_5_1
    MODEL_ID = "claude-fable-5-1"
    PROVIDER = ModelProvider.ANTHROPIC

    # Claude Fable 5.1 always thinks: only {"type": "adaptive"} (or no `thinking`)
    # is accepted. temperature/top_p/top_k and forced tool_choice ("any"/"tool")
    # return a 400. Depth is controlled with output_config.effort.
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
        name="Fable 5.1",
        owner="anthropic",
        description="Anthropic's most capable widely released model, for long-running agents.",
        pricing={
            "prompt": "0.00001",
            "completion": "0.00005",
            "input_cache_read": "0.00000025",
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
            "adaptive_thinking": "always_on",
            "effort": EFFORT,
            "comparative_latency": "slower",
            "max_output_tokens": 128000,
        },
    )


model: ChatModel = ClaudeFable51Model.model
