from langchain_anthropic import ChatAnthropic
from naas_abi_core.models.Model import (
    CanonicalModelId,
    ChatModel,
    ModelDefinition,
    ModelProvider,
)
from naas_abi_marketplace.ai.anthropic import ABIModule
from pydantic import SecretStr

EFFORT = "medium"


class ClaudeHaiku55Model(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.CLAUDE_HAIKU_5_5
    MODEL_ID = "claude-haiku-5-5"
    PROVIDER = ModelProvider.ANTHROPIC

    # Claude Haiku 5.5 runs adaptive thinking by default (`budget_tokens` and
    # non-default temperature/top_p/top_k return a 400). Effort defaults to
    # `medium` on the API; it is set explicitly so the choice is visible.
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
        name="Haiku 5.5",
        owner="anthropic",
        description="The current Haiku: fastest and cheapest Claude for simple, high-volume tasks.",
        pricing={
            # Prompts up to 100K tokens; beyond that: $0.50 / $2.50 per MTok.
            "prompt": "0.0000001",
            "completion": "0.0000005",
            "prompt_above_100k": "0.0000005",
            "completion_above_100k": "0.0000025",
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
            "comparative_latency": "fastest",
            "max_output_tokens": 128000,
        },
    )


model: ChatModel = ClaudeHaiku55Model.model
