from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from lib.abi.models.Model import ChatModel
from src.core.chatgpt import ABIModule

ID = "o3-mini"
NAME = "o3-mini"
DESCRIPTION = "OpenAI's fastest reasoning model, optimized for performance and efficiency in multi-agent orchestration."
IMAGE = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
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
        temperature=1,  # AbiAgent uses temperature=1 for creative orchestration
        max_retries=2,
        api_key=SecretStr(ABIModule.get_instance().configuration.openai_api_key),
    ),
    context_window=CONTEXT_WINDOW,
)
