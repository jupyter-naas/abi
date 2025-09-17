from src import secret

def requirements():
    mistral_api_key = secret.get("MISTRAL_API_KEY")
    if mistral_api_key:
        return True
    return False