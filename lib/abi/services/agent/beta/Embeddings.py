from langchain_openai import OpenAIEmbeddings
from abi.models.DockerModelRunnerEmbeddings import DockerModelRunnerEmbeddings
from src import secret
from typing import Union
import requests
from abi import logger

# Select embedding model based on AI_MODE
ai_mode = secret.get("AI_MODE", "cloud")

embeddings_model: Union[DockerModelRunnerEmbeddings, OpenAIEmbeddings]

if ai_mode == "local":
    # Check if Docker Model Runner is available
    try:
        response = requests.get("http://localhost:8081/health", timeout=2)
        if response.status_code == 200:
            embeddings_model = DockerModelRunnerEmbeddings(
                endpoint="http://localhost:8081",
                model_name="embeddinggemma"
            )
            logger.info("✅ Using Docker Model Runner embeddings (local mode)")
        else:
            raise ConnectionError("Docker Model Runner not healthy")
    except (requests.exceptions.RequestException, ConnectionError):
        logger.warning("⚠️ Docker Model Runner not available, falling back to OpenAI embeddings")
        embeddings_model = OpenAIEmbeddings(model="text-embedding-ada-002")
else:
    embeddings_model = OpenAIEmbeddings(model="text-embedding-ada-002")


def openai_embeddings_batch(texts):
    return embeddings_model.embed_documents(texts)

def openai_embeddings(text):
    """Generate embeddings for text using the configured embedding model.
    
    Args:
        text (str): The text to generate embeddings for
        
    Returns:
        List[float]: The embedding vector
    """

    embedding = embeddings_model.embed_query(text)
    
    return embedding

