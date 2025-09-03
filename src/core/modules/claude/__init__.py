from src import secret

def requirements():
    anthropic_api_key = secret.get("ANTHROPIC_API_KEY")
    if anthropic_api_key:
        return True
    return False