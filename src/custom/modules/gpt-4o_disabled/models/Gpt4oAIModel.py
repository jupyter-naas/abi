
from langchain_openai import ChatOpenAI
from src import secret
from lib.abi.models.Model import ChatModel

ID = "113f2201-9f0e-4bf1-a25f-3ea8ba88e41d"
NAME = "gpt-4o"
DESCRIPTION = "OpenAI's most advanced, multimodal flagship model that's cheaper and faster than GPT-4 Turbo."
IMAGE = "https://naasai-public.s3.eu-west-3.amazonaws.com/logos/openai_100x100.png"
CONTEXT_WINDOW = 128000
OWNER = "openai" 

model = ChatModel(
    id=ID,
    name=NAME,
    description=DESCRIPTION,
    image=IMAGE,
    context_window=CONTEXT_WINDOW,
    owner=OWNER,
    model=ChatOpenAI(
        model=NAME,
        temperature=1,
        api_key=secret.get("OPENAI_API_KEY")
    )
)