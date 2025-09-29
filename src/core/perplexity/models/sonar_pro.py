from langchain_perplexity import ChatPerplexity
from src import secret
from pydantic import SecretStr

perplexity_api_key = secret.get("PERPLEXITY_API_KEY")
model = ChatPerplexity(
    model="sonar-pro",
    temperature=0,
    api_key=SecretStr(perplexity_api_key),
    timeout=120
)