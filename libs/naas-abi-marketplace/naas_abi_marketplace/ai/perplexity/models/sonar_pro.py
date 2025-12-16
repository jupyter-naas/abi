from langchain_perplexity import ChatPerplexity  # type: ignore
from naas_abi_marketplace.ai.perplexity import ABIModule
from naas_abi_core.models.Model import ChatModel
from pydantic import SecretStr

MODEL_ID = "sonar-pro"
PROVIDER = "perplexity"

api_key = ABIModule.get_instance().configuration.perplexity_api_key or ""

model: ChatModel = ChatModel(
    model_id=MODEL_ID,
    provider=PROVIDER,
    model=ChatPerplexity(
        model=MODEL_ID,
        temperature=0,
        api_key=SecretStr(api_key),
        timeout=120,
    ),
)
