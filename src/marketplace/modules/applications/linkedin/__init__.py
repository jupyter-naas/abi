from src.marketplace.modules.applications.naas.integrations.NaasIntegration import NaasIntegration, NaasIntegrationConfiguration
from src import secret

def requirements():
    li_at = secret.get('li_at')
    JSESSIONID = secret.get('JSESSIONID')
    linkedin_profile_url = secret.get('LINKEDIN_PROFILE_URL')
    # if li_at is None and JSESSIONID is None:
    #     naas_api_key = secret.get('NAAS_API_KEY')
    #     if naas_api_key:
    #         naas_integration_config = NaasIntegrationConfiguration(api_key=naas_api_key)
    #         li_at = NaasIntegration(naas_integration_config).get_secret('li_at').get('secret', {}).get('value')
    #         JSESSIONID = NaasIntegration(naas_integration_config).get_secret('JSESSIONID').get('secret', {}).get('value')
    if li_at is not None and JSESSIONID is not None and linkedin_profile_url is not None:
        return True
    return False