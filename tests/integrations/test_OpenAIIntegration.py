from src.core.integrations.OpenAIIntegration import OpenAIIntegration, OpenAIIntegrationConfiguration
from src import secret
from abi import logger
from pydantic import BaseModel, Field

# Init
configuration = OpenAIIntegrationConfiguration(api_key=secret.get("OPENAI_API_KEY"))
integration = OpenAIIntegration(configuration)

# Create chat completion
completion = integration.create_chat_completion(
    prompt="What is the capital of France? Please respond in JSON format.",
    system_prompt="You are a helpful AI assistant.",
    model="o3-mini",
    response_format={"type": "json_object"},
)
logger.info(completion)

# Create chat completion beta
class Response(BaseModel):
    answer: str = Field(description="The answer to the question")
    source: str = Field(description="The source of the answer")

completion = integration.create_chat_completion_beta(
    prompt="What is the capital of France? Please respond in JSON format.",
    system_prompt="You are a helpful AI assistant.",
    model="o3-mini",
    response_format=Response,
)
logger.info(completion)