from lib.abi.models.Model import ChatModel
from langchain_anthropic import ChatAnthropic
from src import secret
from pydantic import SecretStr

MODEL_ID = "claude-haiku-4-5-20251001"
PROVIDER = "anthropic"

api_key = secret.get("ANTHROPIC_API_KEY")
if secret.get("OPENROUTER_API_KEY"):
    api_key = secret.get("OPENROUTER_API_KEY")

model: ChatModel = ChatModel(
    model_id=MODEL_ID,
    provider=PROVIDER,
    model=ChatAnthropic(
        model_name=MODEL_ID,
        temperature=0,
        max_retries=2,
        api_key=SecretStr(api_key),
        timeout=None,
        stop=None
    ),
)

