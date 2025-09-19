from abi.models.Model import ChatModel
from abi.models.DockerModelRunnerChat import DockerModelRunnerChat
from typing import Optional
from abi import logger

ID = "gemma3n"
NAME = "Gemma3 Docker"
DESCRIPTION = "Google's Gemma3 model running via Docker Model Runner for local deployment without Ollama dependency."
IMAGE = "https://naasai-public.s3.eu-west-3.amazonaws.com/logos/docker_100x100.png"
CONTEXT_WINDOW = 8192
OWNER = "google"

model: Optional[ChatModel] = None

try:
    model = ChatModel(
        model_id=ID,
        name=NAME,
        description=DESCRIPTION,
        image=IMAGE,
        owner=OWNER,
        model=DockerModelRunnerChat(
            endpoint="http://localhost:8080",
            model_name="gemma3n",
            temperature=0.4,  # Balanced creativity for general conversation
            max_tokens=2048,
        ),
        context_window=CONTEXT_WINDOW,
    )
    logger.debug("✅ Gemma3 Docker model loaded successfully via Docker Model Runner")
except Exception as e:
    logger.error(f"⚠️  Error loading Gemma3 Docker model: {e}")
    logger.error("   Make sure Docker Model Runner services are running (make local-up)")