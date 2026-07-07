from langchain_aws import ChatBedrockConverse
from naas_abi_core.models.Model import (
    CanonicalModelId,
    ChatModel,
    ModelDefinition,
    ModelProvider,
)
from naas_abi_marketplace.ai.bedrock import ABIModule


class ClaudeOpus48BedrockModel(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.CLAUDE_OPUS_4_8
    MODEL_ID = "anthropic.claude-opus-4-8"
    PROVIDER = ModelProvider.BEDROCK

    _cfg = ABIModule.get_instance().configuration

    # Claude Opus 4.8 rejects sampling parameters (temperature/top_p/top_k)
    # with a 400 — do not pass temperature.
    model: ChatModel = ChatModel(
        model_id=MODEL_ID,
        provider=PROVIDER,
        model=ChatBedrockConverse(
            model=MODEL_ID,
            region_name=_cfg.region_name,
            aws_access_key_id=_cfg.aws_access_key_id,
            aws_secret_access_key=_cfg.aws_secret_access_key,
            aws_session_token=_cfg.aws_session_token,
            max_tokens=None,
        ),
        context_window=1000000,
        name="Claude Opus 4.8",
        owner="anthropic",
        description="For complex agentic coding and enterprise work.",
        canonical_slug=MODEL_ID,
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


model: ChatModel = ClaudeOpus48BedrockModel.model
