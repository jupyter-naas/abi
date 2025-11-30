from naas_abi import secret


def requirements():
    api_key = secret.get("EXCHANGERATESAPI_API_KEY")
    if api_key:
        return True
    return False
