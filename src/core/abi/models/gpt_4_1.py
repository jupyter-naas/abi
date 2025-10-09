from lib.abi.models.Model import ChatModel
from langchain_openai import ChatOpenAI
from pydantic import SecretStr
from src import secret

ID = "gpt-4.1"
NAME = "gpt-4.1"
DESCRIPTION = "GPT-4.1 excels at instruction following and tool calling, with broad knowledge across domains. It features a 1M token context window, and low latency without a reasoning step."
IMAGE = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
CONTEXT_WINDOW = 1047576
OWNER = "openai"

model: ChatModel
openai_api_key = secret.get("OPENAI_API_KEY")
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