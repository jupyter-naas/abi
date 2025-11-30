from langchain_perplexity import ChatPerplexity
from naas_abi import secret
from naas_abi_core.models.Model import ChatModel
from pydantic import SecretStr

MODEL_ID = "sonar-pro"
PROVIDER = "perplexity"

api_key = secret.get("PERPLEXITY_API_KEY")
if secret.get("OPENROUTER_API_KEY"):
    api_key = secret.get("OPENROUTER_API_KEY")

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
