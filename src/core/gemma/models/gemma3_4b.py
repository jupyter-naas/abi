from abi.models.Model import ChatModel
from abi.models.DockerModelRunnerChat import DockerModelRunnerChat
from typing import Optional
from abi import logger
import requests

ID = "ai/gemma3:4B-Q4_0"
NAME = "Gemma3 4B Q4_0"
DESCRIPTION = "Google's Gemma3 4B model with Q4_0 quantization via Docker Model Runner - 131K context window."
IMAGE = "https://naasai-public.s3.eu-west-3.amazonaws.com/logos/docker_100x100.png"
CONTEXT_WINDOW = 131072  # 131K tokens, 4B parameters
OWNER = "google"

model: Optional[ChatModel] = None

# Try Docker Model Runner OpenAI API (proper HTTP endpoint)
try:
    response = requests.get("http://localhost:11434/v1/models", timeout=3)
    if response.status_code == 200:
        models_data = response.json()
        available_models = [m["id"] for m in models_data.get("data", [])]
        
        # Use gemma3:4b (available) instead of ai/gemma3:4B-Q4_0
        if "gemma3:4b" in available_models:
            model = ChatModel(
                model_id="gemma3:4b",
                name="Gemma3 4B (Docker Model Runner)",
                description="Google's Gemma3 4B model via Docker Model Runner OpenAI API",
                image=IMAGE,
                owner=OWNER,
                model=DockerModelRunnerChat(
                    endpoint="http://localhost:11434/v1",
                    model_name="gemma3:4b",
                    temperature=0.4,
                    max_tokens=4096,
                ),
                context_window=CONTEXT_WINDOW,
            )
            logger.debug("✅ Gemma3 4B model loaded via Docker Model Runner OpenAI API")
        else:
            raise ConnectionError("gemma3:4b not available in API")
    else:
        raise ConnectionError("Docker Model Runner OpenAI API not available")
except Exception as e:
    logger.error(f"⚠️ Error loading Docker Model Runner: {e}")
    logger.error("   Ensure Docker Model Runner is enabled and ai/gemma3:4B-Q4_0 is pulled")
    logger.error("   Run: docker model pull ai/gemma3:4B-Q4_0")