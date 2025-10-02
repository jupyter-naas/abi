from lib.abi.models.Model import ChatModel
from langchain_openai import ChatOpenAI
from pydantic import SecretStr
from src import secret
from typing import Optional

ID = "gpt-4.1"
NAME = "gpt-4.1"
DESCRIPTION = "GPT-4.1 excels at instruction following and tool calling, with broad knowledge across domains. It features a 1M token context window, and low latency without a reasoning step."
IMAGE = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
CONTEXT_WINDOW = 1047576
OWNER = "openai"

model: Optional[ChatModel] = None
openai_api_key = secret.get("OPENAI_API_KEY")

if openai_api_key is None:
    # Ask the user to enter the OpenAI API key
    openai_api_key = None
    while openai_api_key in ["", None]:
        openai_api_key = input("Enter your OpenAI API key: ")
    
    secret.set("OPENAI_API_KEY", openai_api_key)
    

model = ChatModel(
    model_id=ID,
    name=NAME,
    description=DESCRIPTION,
    image=IMAGE,
    owner=OWNER,
    model=ChatOpenAI(
        model=ID,
        temperature=0,
        api_key=SecretStr(openai_api_key),
    ),
    context_window=CONTEXT_WINDOW,
)