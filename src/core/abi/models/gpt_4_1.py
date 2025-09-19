from langchain_openai import ChatOpenAI
from pydantic import SecretStr
from src import secret
from abi import logger

openai_api_key = secret.get("OPENAI_API_KEY")
model = ChatOpenAI(
    model="gpt-4.1",
    temperature=0,
    api_key=SecretStr(openai_api_key),
)
logger.debug("✅ GPT-4.1 model loaded successfully via OpenAI")