from lib.abi.models.Model import ChatModel
from langchain_openai import ChatOpenAI

MODEL_ID = "ai/qwen3"
PROVIDER = "qwen"
NAME = "qwen3-airgap"
DESCRIPTION = "Qwen3 model running in airgap mode via Docker Model Runner with tool support."
IMAGE = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
CONTEXT_WINDOW = 8192

model: ChatModel = ChatModel(
    model_id=MODEL_ID,
    provider=PROVIDER,
    name=NAME,
    description=DESCRIPTION,
    image=IMAGE,
    model=ChatOpenAI(
        model="ai/qwen3",  # Qwen3 8B - better performance with 16GB RAM
        temperature=0.7,
        base_url="http://localhost:12434/engines/v1",
    )
)