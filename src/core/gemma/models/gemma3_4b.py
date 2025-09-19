from abi.models.Model import ChatModel
from abi.models.DockerModelRunnerChat import DockerModelRunnerChat
from langchain_ollama import ChatOllama
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
    response = requests.get("http://localhost:8080/health", timeout=2)
    if response.status_code == 200:
        model = ChatModel(
            model_id=ID,
            name=NAME,
            description=DESCRIPTION,
            image=IMAGE,
            owner=OWNER,
            model=DockerModelRunnerChat(
                endpoint="http://localhost:8080",
                model_name="gemma3n",
                temperature=0.4,
                max_tokens=2048,
            ),
            context_window=CONTEXT_WINDOW,
        )
        logger.debug("✅ Gemma3 model loaded via Docker Model Runner")
    else:
        raise ConnectionError("Docker Model Runner not healthy")
except (requests.exceptions.RequestException, ConnectionError):
    # Fallback to Ollama
    try:
        model = ChatModel(
            model_id="gemma3:4b",
            name="Gemma3 4B (Ollama)",
            description="Google's Gemma3 4B model via Ollama fallback",
            image=IMAGE,
            owner=OWNER,
            model=ChatOllama(
                model="gemma3:4b",
                temperature=0.4,
            ),
            context_window=CONTEXT_WINDOW,
        )
        logger.debug("✅ Gemma3 model loaded via Ollama (fallback)")
    except Exception as e:
        logger.error(f"⚠️ Error loading Gemma3 model (both Docker and Ollama failed): {e}")
        logger.error("   Install either Docker Model Runner or Ollama with gemma3:4b")