from lib.abi.models.Model import ChatModel
from langchain_openai import ChatOpenAI
from pydantic import SecretStr
from src import secret

MODEL_ID = "gpt-4.1"
PROVIDER = "openai"

api_key = secret.get("OPENAI_API_KEY")
if secret.get("OPENROUTER_API_KEY"):
    api_key = secret.get("OPENROUTER_API_KEY")

model: ChatModel = ChatModel(
    model_id=MODEL_ID,
    provider=PROVIDER,
    model=ChatOpenAI(
        model=MODEL_ID,
        temperature=0,
        api_key=SecretStr(api_key),
    ),
)