from src import secret

def requirements():
    openai_api_key = secret.get("OPENAI_API_KEY")
    if openai_api_key:
        return True
    return False