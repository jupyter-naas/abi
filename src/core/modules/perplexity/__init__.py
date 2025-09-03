from src import secret

def requirements():
    perplexity_api_key = secret.get("PERPLEXITY_API_KEY")
    if perplexity_api_key:
        return True
    return False