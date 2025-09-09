from langchain_perplexity import ChatPerplexity
from src import secret
from pydantic import SecretStr
from abi import logger

perplexity_api_key = secret.get("PERPLEXITY_API_KEY")
model = ChatPerplexity(
    model="sonar",
    temperature=0,
    api_key=SecretStr(perplexity_api_key),
    timeout=120
)
logger.debug("✅ Perplexity GPT-4o model loaded successfully via OpenAI")