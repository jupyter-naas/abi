from lib.abi.models.Model import ChatModel
from langchain_anthropic import ChatAnthropic
from src import secret
from pydantic import SecretStr

MODEL_ID = "claude-opus-4-1-20250805"
PROVIDER = "anthropic"

model: ChatModel = ChatModel(
    model_id=MODEL_ID,
    provider=PROVIDER,
    model=ChatAnthropic(
        model_name=MODEL_ID,
        temperature=0,
        max_retries=2,
        api_key=SecretStr(secret.get("ANTHROPIC_API_KEY")),
        timeout=None,
        stop=None
    ),
)

