from src import secret

def requirements():
    google_api_key = secret.get("GOOGLE_API_KEY")
    if google_api_key:
        return True
    return False