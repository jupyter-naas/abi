from naas_abi import secret


def requirements():
    google_custom_search_api_key = secret.get("GOOGLE_CUSTOM_SEARCH_API_KEY")
    google_custom_search_engine_id = secret.get("GOOGLE_CUSTOM_SEARCH_ENGINE_ID")
    if google_custom_search_api_key and google_custom_search_engine_id:
        return True
    return False
