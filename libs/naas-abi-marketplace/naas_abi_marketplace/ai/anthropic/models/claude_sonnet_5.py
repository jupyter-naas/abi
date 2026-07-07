from langchain_anthropic import ChatAnthropic
from naas_abi_core.models.Model import (
    CanonicalModelId,
    ChatModel,
    ModelDefinition,
    ModelProvider,
)
from naas_abi_marketplace.ai.anthropic import ABIModule
from pydantic import SecretStr


class ClaudeSonnet5Model(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.CLAUDE_SONNET_5
    MODEL_ID = "claude-sonnet-5"
    PROVIDER = ModelProvider.ANTHROPIC

    model: ChatModel = ChatModel(
        model_id=MODEL_ID,
        provider=PROVIDER,
        model=ChatAnthropic(
            model_name=MODEL_ID,
            max_retries=2,
            api_key=SecretStr(ABIModule.get_instance().configuration.anthropic_api_key),
            timeout=None,
            stop=None,
        ),
    )


model: ChatModel = ClaudeSonnet5Model.model
