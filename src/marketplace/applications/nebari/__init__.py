from src import secret

def requirements():
    local_mode = secret.get("AI_MODE")
    if local_mode == "local":
        return True
    else:
        openai_api_key = secret.get("OPENAI_API_KEY")
        if openai_api_key:
            return True
    return False