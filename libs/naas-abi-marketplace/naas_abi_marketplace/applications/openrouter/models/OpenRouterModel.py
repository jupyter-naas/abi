from langchain_openai import ChatOpenAI
from pydantic import SecretStr


class OpenRouterModel:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://openrouter.ai/api/v1"

    def get_model(self, model_id: str):
        return ChatOpenAI(
            model=model_id,
            api_key=SecretStr(self.api_key),
            base_url=self.base_url,
        )
