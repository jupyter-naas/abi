from src import secret, services
from src.core.modules.naas.integrations.NaasIntegration import NaasIntegration, NaasIntegrationConfiguration
from src.custom.modules.linkedin.integrations.LinkedInIntegration import LinkedInIntegration, LinkedInIntegrationConfiguration

naas_api_key = secret.get('NAAS_API_KEY')
if naas_api_key:
    naas_integration_config = NaasIntegrationConfiguration(api_key=naas_api_key)
    li_at = NaasIntegration(naas_integration_config).get_secret('li_at').get('secret').get('value')
    JSESSIONID = NaasIntegration(naas_integration_config).get_secret('JSESSIONID').get('secret').get('value')

configuration = LinkedInIntegrationConfiguration(li_at=li_at, JSESSIONID=JSESSIONID)
integration = LinkedInIntegration(configuration)

profile_id = "ACoAAADS0WQBhQQVMD2eFJNZgjOOjDTH6ptbScU"
data = integration.get_posts_feed(profile_id)
print(data)