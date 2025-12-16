from langchain_perplexity import ChatPerplexity
from naas_abi_marketplace.ai.perplexity import ABIModule
from naas_abi_core.models.Model import ChatModel
from pydantic import SecretStr

MODEL_ID = "sonar-reasoning"
PROVIDER = "perplexity"


model: ChatModel = ChatModel(
    model_id=MODEL_ID,
    provider=PROVIDER,
    model=ChatPerplexity(
        model=MODEL_ID,
        temperature=0,
        api_key=SecretStr(ABIModule.get_instance().configuration.perplexity_api_key),
        timeout=120,
    ),
)
