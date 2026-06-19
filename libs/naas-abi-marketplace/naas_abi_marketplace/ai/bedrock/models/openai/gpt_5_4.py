from langchain_aws import ChatBedrockConverse
from naas_abi_core.models.Model import (
    CanonicalModelId,
    ChatModel,
    ModelDefinition,
    ModelProvider,
)
from naas_abi_marketplace.ai.bedrock import ABIModule


class Gpt54BedrockModel(ModelDefinition):
    """
    URL:https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-openai-gpt-54.html
    """
    CANONICAL_ID = CanonicalModelId.GPT_5_4
    MODEL_ID = "openai.gpt-5.4"
    PROVIDER = ModelProvider.BEDROCK

    _cfg = ABIModule.get_instance().configuration

    model: ChatModel = ChatModel(
        model_id=MODEL_ID,
        provider=PROVIDER,
        context_window=1050000,
        description="GPT-5.4 brings frontier reasoning, coding, computer use, long-context workflows, and tool use to Amazon Bedrock. It helps developers build AI applications and production workflows that can interpret context, interact with tools, operate software environments, and verify outputs across multiple steps. GPT-5.4 is well suited for professional workflows that require reliable reasoning and action across complex business systems. For more information about model development and performance, see the model/service card",
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


model: ChatModel = Gpt54BedrockModel.model
