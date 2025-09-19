from abi.models.Model import ChatModel
from abi.models.DockerModelRunnerChat import DockerModelRunnerChat
from typing import Optional
from abi import logger
import requests

ID = "gemma3n"
NAME = "Gemma3 Local"
DESCRIPTION = "Google's Gemma3 model for local deployment. Tries Docker Model Runner first, falls back to Ollama."
IMAGE = "https://naasai-public.s3.eu-west-3.amazonaws.com/logos/docker_100x100.png"
CONTEXT_WINDOW = 8192
OWNER = "google"

model: Optional[ChatModel] = None

# Try Docker Model Runner first
try:
    response = requests.get("http://localhost:12434/api/tags", timeout=2)
    if response.status_code == 200:
        model = ChatModel(
            model_id=ID,
            name=NAME,
            description=DESCRIPTION,
            image=IMAGE,
            owner=OWNER,
            model=DockerModelRunnerChat(
                endpoint="http://localhost:12434",
                model_name="gemma2:2b",
                temperature=0.4,
                max_tokens=2048,
            ),
            context_window=CONTEXT_WINDOW,
        )
        logger.debug("✅ Gemma2 model loaded via Docker Model Runner")
    else:
        raise ConnectionError("Docker Model Runner not healthy")
except (requests.exceptions.RequestException, ConnectionError):
    # Fallback to direct Ollama via our DockerModelRunnerChat adapter
    try:
        # Check if standard Ollama is running on port 11434
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        if response.status_code == 200:
            model = ChatModel(
                model_id="gemma2:2b",
                name="Gemma2 2B (Ollama Direct)",
                description="Google's Gemma2 2B model via direct Ollama fallback",
                image=IMAGE,
                owner=OWNER,
                model=DockerModelRunnerChat(
                    endpoint="http://localhost:11434",
                    model_name="gemma2:2b",
                    temperature=0.4,
                    max_tokens=2048,
                ),
                context_window=CONTEXT_WINDOW,
            )
            logger.debug("✅ Gemma2 model loaded via direct Ollama (fallback)")
        else:
            raise ConnectionError("No Ollama service available")
    except Exception as e:
        logger.error(f"⚠️ Error loading Gemma model (all methods failed): {e}")
        logger.error("   Start local services with: make local-up")