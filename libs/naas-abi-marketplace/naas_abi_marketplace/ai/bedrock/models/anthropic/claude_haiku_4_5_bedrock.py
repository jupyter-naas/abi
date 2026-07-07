from langchain_aws import ChatBedrockConverse
from naas_abi_core.models.Model import (
    CanonicalModelId,
    ChatModel,
    ModelDefinition,
    ModelProvider,
)
from naas_abi_marketplace.ai.bedrock import ABIModule


class ClaudeHaiku45BedrockModel(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.CLAUDE_HAIKU_4_5
    MODEL_ID = "anthropic.claude-haiku-4-5"
    PROVIDER = ModelProvider.BEDROCK

    _cfg = ABIModule.get_instance().configuration

    model: ChatModel = ChatModel(
        model_id=MODEL_ID,
        provider=PROVIDER,
        model=ChatBedrockConverse(
            model=MODEL_ID,
            region_name=_cfg.region_name,
            aws_access_key_id=_cfg.aws_access_key_id,
            aws_secret_access_key=_cfg.aws_secret_access_key,
            aws_session_token=_cfg.aws_session_token,
            temperature=0,
            max_tokens=None,
        ),
        context_window=200000,
        name="Claude Haiku 4.5",
        owner="anthropic",
        description="The fastest model with near-frontier intelligence.",
        canonical_slug=MODEL_ID,
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


model: ChatModel = ClaudeHaiku45BedrockModel.model
