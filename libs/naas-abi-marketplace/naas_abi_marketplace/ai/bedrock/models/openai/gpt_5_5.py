from langchain_aws import ChatBedrockConverse
from naas_abi_core.models.Model import (
    CanonicalModelId,
    ChatModel,
    ModelDefinition,
    ModelProvider,
)
from naas_abi_marketplace.ai.bedrock import ABIModule


class Gpt55BedrockModel(ModelDefinition):
    """
    URL:https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-openai-gpt-55.html
    """
    CANONICAL_ID = CanonicalModelId.GPT_5_5
    MODEL_ID = "openai.gpt-5.5"
    PROVIDER = ModelProvider.BEDROCK

    _cfg = ABIModule.get_instance().configuration

    model: ChatModel = ChatModel(
        model_id=MODEL_ID,
        provider=PROVIDER,
        context_window=1050000,
        description="GPT-5.5 is OpenAI's most capable model, designed for advanced coding, research, analysis, software operation, document workflows, and long-running agentic tasks. GPT-5.5 can understand open-ended goals, use tools, reason across longer workflows, navigate ambiguity, and carry complex tasks through to completion with less orchestration. For more information about model development and performance, see the model/service card.",
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


model: ChatModel = Gpt55BedrockModel.model
