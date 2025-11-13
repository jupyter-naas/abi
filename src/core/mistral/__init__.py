from src import secret

def requirements():
    ai_mode = secret.get("AI_MODE")
    mistral_api_key = secret.get("MISTRAL_API_KEY")
    openrouter_api_key = secret.get("OPENROUTER_API_KEY")
    if ai_mode == "cloud" and (mistral_api_key or openrouter_api_key):
        return True
    return False