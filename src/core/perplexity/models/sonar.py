from lib.abi.models.Model import ChatModel
from langchain_perplexity import ChatPerplexity
from src import secret
from pydantic import SecretStr

MODEL_ID = "sonar"
PROVIDER = "perplexity"

model: ChatModel = ChatModel(
    model_id=MODEL_ID,
    provider=PROVIDER,
    model=ChatPerplexity(
        model=MODEL_ID,
        temperature=0,
        api_key=SecretStr(secret.get("PERPLEXITY_API_KEY")),
        timeout=120,
    ),
)