from src import secret
from src.core.modules.naas.integrations.NaasIntegration import NaasIntegration, NaasIntegrationConfiguration
from src.custom.modules.linkedin.integrations.LinkedInIntegration import LinkedInIntegration, LinkedInIntegrationConfiguration

naas_api_key = secret.get('NAAS_API_KEY')
if naas_api_key:
    naas_integration_config = NaasIntegrationConfiguration(api_key=naas_api_key)
    li_at = NaasIntegration(naas_integration_config).get_secret('li_at').get('secret', {}).get('value')
    JSESSIONID = NaasIntegration(naas_integration_config).get_secret('JSESSIONID').get('secret', {}).get('value')
if not li_at or not JSESSIONID:
    raise Exception("li_at or JSESSIONID is not set")
configuration = LinkedInIntegrationConfiguration(li_at=li_at, JSESSIONID=JSESSIONID)
integration = LinkedInIntegration(configuration)

linkedin_url = "https://www.linkedin.com/company/naas-ai/"
data = integration.get_organization_info(linkedin_url)
print(data)