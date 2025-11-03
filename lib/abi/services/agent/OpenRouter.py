import os
from dotenv import load_dotenv
load_dotenv()

from langchain_openai import ChatOpenAI  # using the OpenAI LLM class as wrapper
from pydantic import SecretStr

class ChatOpenRouter(ChatOpenAI):
    def __init__(self, model_name: str, **kwargs):
        api_key = SecretStr(os.environ["OPENROUTER_API_KEY"])
        super().__init__(
            model=model_name,
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
            **kwargs,
        )
