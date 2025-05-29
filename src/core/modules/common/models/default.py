from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel
from src import secret
from pydantic import SecretStr
import os

def default_chat_model() -> BaseChatModel:
    openai_api_key : str | None = os.environ.get("OPENAI_API_KEY", None)
    return (
        ChatOpenAI(
            model="gpt-4o", temperature=0, api_key=SecretStr(openai_api_key) if openai_api_key is not None else None
        )
        if os.environ.get("OPENAI_API_KEY") is not None
        # else ChatOllama(model="llama3.2", temperature=0.7)
        else ChatOpenAI( api_key=SecretStr("ollama"), model="llama3.2", base_url="http://localhost:11434/v1")
    )