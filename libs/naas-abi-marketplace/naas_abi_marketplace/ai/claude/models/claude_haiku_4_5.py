from langchain_anthropic import ChatAnthropic
from naas_abi_marketplace.ai.claude import ABIModule
from naas_abi_core.models.Model import ChatModel
from pydantic import SecretStr

MODEL_ID = "claude-haiku-4-5-20251001"
PROVIDER = "anthropic"

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
