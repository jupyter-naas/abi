from src import secret

def requirements():
    li_at = secret.get('li_at')
    JSESSIONID = secret.get('JSESSIONID')
    li_a = secret.get('li_a')
    linkedin_profile_url = secret.get('LINKEDIN_PROFILE_URL')
    if li_at is not None and JSESSIONID is not None and li_a is not None and linkedin_profile_url is not None:
        return True
    return False