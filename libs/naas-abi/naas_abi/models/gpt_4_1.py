from langchain_openai import ChatOpenAI
from naas_abi import ABIModule
from naas_abi_core.models.Model import ChatModel
from pydantic import SecretStr

ID = "gpt-4.1"
NAME = "gpt-4.1"
DESCRIPTION = "GPT-4.1 excels at instruction following and tool calling, with broad knowledge across domains. It features a 1M token context window, and low latency without a reasoning step."
IMAGE = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
CONTEXT_WINDOW = 1047576
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
