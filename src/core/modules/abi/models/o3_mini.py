from lib.abi.models.Model import ChatModel
from langchain_openai import ChatOpenAI
from src import secret
from typing import Optional
from pydantic import SecretStr

ID = "o3-mini"
NAME = "o3-mini"
DESCRIPTION = "OpenAI's fastest reasoning model, optimized for performance and efficiency in multi-agent orchestration."
IMAGE = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
CONTEXT_WINDOW = 128000
OWNER = "openai"

model: Optional[ChatModel] = None
if secret.get("OPENAI_API_KEY"):
    model = ChatModel(
        model_id=ID,
        name=NAME,
        description=DESCRIPTION,
        image=IMAGE,
        owner=OWNER,
        model=ChatOpenAI(
            model=ID,
            temperature=1,  # AbiAgent uses temperature=1 for creative orchestration
            max_retries=2,
            api_key=SecretStr(secret.get("OPENAI_API_KEY")),
        ),
        context_window=CONTEXT_WINDOW,
    )