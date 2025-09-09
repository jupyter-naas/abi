from src import secret, config

def requirements():
    li_at = secret.get('li_at')
    JSESSIONID = secret.get('JSESSIONID')
    openai_api_key = secret.get("OPENAI_API_KEY")
    naas_api_key = secret.get("NAAS_API_KEY")
    if li_at and JSESSIONID and openai_api_key and naas_api_key:
        return True
    return False