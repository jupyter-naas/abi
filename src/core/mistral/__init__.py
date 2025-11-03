from src import secret

def requirements():
    ai_mode = secret.get("AI_MODE")
    mistral_api_key = secret.get("MISTRAL_API_KEY")
    if ai_mode == "cloud" and mistral_api_key:
        return True
    return False