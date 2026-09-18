from langchain_aws import ChatBedrockConverse
from naas_abi_core.models.Model import (
    CanonicalModelId,
    ChatModel,
    ModelDefinition,
    ModelProvider,
)
from naas_abi_marketplace.ai.bedrock import ABIModule

# Bedrock Converse requires a system inference profile for GPT-5.6 Sol (not on-demand
# foundation-model id). Catalog model_id stays openai.gpt-5.6-sol for operators.
_BEDROCK_INFERENCE_PROFILE_ID = "us.openai.gpt-5.6-sol"
_CATALOG_MODEL_ID = "openai.gpt-5.6-sol"


class Gpt56SolBedrockModel(ModelDefinition):
    """
    URL:https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-openai.html
    """

    CANONICAL_ID = CanonicalModelId.GPT_5_6_SOL
    MODEL_ID = _CATALOG_MODEL_ID
    PROVIDER = ModelProvider.BEDROCK

    _cfg = ABIModule.get_instance().configuration

    model: ChatModel = ChatModel(
        model_id=MODEL_ID,
        provider=PROVIDER,
        description=(
            "GPT-5.6 Sol on Amazon Bedrock (OpenAI). Invoked via the US inference "
            "profile us.openai.gpt-5.6-sol."
        ),
        model=ChatBedrockConverse(
            model=_BEDROCK_INFERENCE_PROFILE_ID,
            region_name=_cfg.region_name,
            aws_access_key_id=_cfg.aws_access_key_id,
            aws_secret_access_key=_cfg.aws_secret_access_key,
            aws_session_token=_cfg.aws_session_token,
            max_tokens=None,
        ),
    )


model: ChatModel = Gpt56SolBedrockModel.model
