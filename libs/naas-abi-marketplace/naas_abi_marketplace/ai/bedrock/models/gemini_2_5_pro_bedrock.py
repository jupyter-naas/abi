from langchain_aws import ChatBedrockConverse
from naas_abi_core.models.Model import (
    CanonicalModelId,
    ChatModel,
    ModelDefinition,
    ModelProvider,
)
from naas_abi_marketplace.ai.bedrock import ABIModule


class Gemini25ProBedrockModel(ModelDefinition):
    """Largest Gemini model currently exposed on Bedrock."""

    CANONICAL_ID = CanonicalModelId.GEMINI_2_5_PRO
    MODEL_ID = "us.google.gemini-2-5-pro-v1:0"
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
    )


model: ChatModel = Gemini25ProBedrockModel.model
