from langchain_openai import OpenAIEmbeddings
from abi.models.DockerModelRunnerEmbeddings import DockerModelRunnerEmbeddings
from src import secret
from typing import Union
from abi import logger

# Select embedding model based on AI_MODE
ai_mode = secret.get("AI_MODE", "cloud")

embeddings_model: Union[DockerModelRunnerEmbeddings, OpenAIEmbeddings]

if ai_mode == "local":
    # Use Docker Model Runner deterministic embeddings for local mode
    embeddings_model = DockerModelRunnerEmbeddings(
        model_name="ai/embeddinggemma:300M-Q8_0"
    )
    logger.info("✅ Using Docker Model Runner deterministic embeddings (768 dimensions)")
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

