from langchain_openai import OpenAIEmbeddings
from abi.models.DockerModelRunnerEmbeddings import DockerModelRunnerEmbeddings
from src import secret

# Select embedding model based on AI_MODE
ai_mode = secret.get("AI_MODE", "cloud")

if ai_mode == "local":
    embeddings_model = DockerModelRunnerEmbeddings(
        endpoint="http://localhost:8081",
        model_name="embeddinggemma"
    )
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

