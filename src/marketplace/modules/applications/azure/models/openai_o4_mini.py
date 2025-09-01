from lib.abi.models.Model import ChatModel
from langchain_openai import AzureChatOpenAI
from src import secret
import os

if "AZURE_OPENAI_API_KEY" not in os.environ:
    os.environ["AZURE_OPENAI_API_KEY"] = secret.get("AZURE_OPENAI_API_KEY")

os.environ["AZURE_OPENAI_ENDPOINT"] = "https://YOUR-ENDPOINT.openai.azure.com/"

model = ChatModel(
    model_id="113f2201-9f0e-4bf1-a25f-3ea8ba88e41d",
    name="o4-mini",
    description="",
    image="",
    owner="openai",
    model=AzureChatOpenAI(
        azure_deployment="o4-mini",
        api_version="2024-08-01-preview",
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    ),
    context_window=200000,
)
