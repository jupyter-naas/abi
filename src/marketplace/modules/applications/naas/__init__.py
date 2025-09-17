from src import secret

def requirements():
    naas_api_key = secret.get('NAAS_API_KEY')
    if naas_api_key:
        return True
    return False