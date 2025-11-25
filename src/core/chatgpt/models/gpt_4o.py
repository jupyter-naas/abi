from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from lib.abi.models.Model import ChatModel
from src.core.chatgpt import ABIModule

ID = "gpt-4o"
NAME = "gpt-4o"
DESCRIPTION = "OpenAI's most advanced model with superior performance across text, code, and reasoning tasks."
IMAGE = "https://i.pinimg.com/736x/2a/62/c3/2a62c34e0d217a7aa14645ce114d84b3.jpg"
CONTEXT_WINDOW = 128000
OWNER = "openai"

model: ChatModel = ChatModel(
    model_id=ID,
    name=NAME,
    description=DESCRIPTION,
    image=IMAGE,
    owner=OWNER,
    model=ChatOpenAI(
        model=ID,
        temperature=0,
        api_key=SecretStr(ABIModule.get_instance().configuration.openai_api_key),
    ),
    context_window=CONTEXT_WINDOW,
)
