from src import secret

def requirements():
    ai_mode = secret.get("AI_MODE")
    xai_api_key = secret.get("XAI_API_KEY")
    openrouter_api_key = secret.get("OPENROUTER_API_KEY")
    if ai_mode == "cloud" and (xai_api_key or openrouter_api_key):
        return True
    return False