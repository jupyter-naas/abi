from lib.abi.models.Model import ChatModel
from langchain_openai import ChatOpenAI
from pydantic import SecretStr
from src import secret

MODEL_ID = "o4-mini-deep-research"
PROVIDER = "openai"

model: ChatModel = ChatModel(
    model_id=MODEL_ID,
    provider=PROVIDER,
    model=ChatOpenAI(
        model=MODEL_ID,
        temperature=0,
        api_key=SecretStr(secret.get("OPENAI_API_KEY")),
    ),
)

