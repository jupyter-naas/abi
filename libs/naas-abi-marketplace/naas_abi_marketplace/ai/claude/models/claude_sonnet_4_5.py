from langchain_anthropic import ChatAnthropic
from naas_abi_core.models.Model import (
    CanonicalModelId,
    ChatModel,
    ModelDefinition,
    ModelProvider,
)
from naas_abi_marketplace.ai.claude import ABIModule
from pydantic import SecretStr


class ClaudeSonnet45Model(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.CLAUDE_SONNET_4_5
    MODEL_ID = "claude-sonnet-4-5-20250929"
    PROVIDER = ModelProvider.ANTHROPIC

    model: ChatModel = ChatModel(
        model_id=MODEL_ID,
        provider=PROVIDER,
        model=ChatAnthropic(
            model_name=MODEL_ID,
            temperature=0,
            max_retries=2,
            api_key=SecretStr(ABIModule.get_instance().configuration.anthropic_api_key),
            timeout=None,
            stop=None,
        ),
    )


model: ChatModel = ClaudeSonnet45Model.model
