from src import secret

def requirements():
    xai_api_key = secret.get("XAI_API_KEY")
    if xai_api_key:
        return True
    return False