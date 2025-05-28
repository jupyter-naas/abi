from src import secret
from src.core.modules.naas.integrations.NaasIntegration import NaasIntegration, NaasIntegrationConfiguration
from src.custom.modules.linkedin.integrations.LinkedInIntegration import LinkedInIntegration, LinkedInIntegrationConfiguration
from abi.utils.Storage import save_json, get_json, save_image
import os
import pydash
import requests

# Configuration
## Integration
naas_api_key = secret.get('NAAS_API_KEY')
if naas_api_key:
    naas_integration_config = NaasIntegrationConfiguration(api_key=naas_api_key)
    li_at = NaasIntegration(naas_integration_config).get_secret('li_at').get('secret', {}).get('value')
    JSESSIONID = NaasIntegration(naas_integration_config).get_secret('JSESSIONID').get('secret', {}).get('value')
if not li_at or not JSESSIONID:
    raise Exception("li_at or JSESSIONID is not set")
configuration = LinkedInIntegrationConfiguration(li_at=li_at, JSESSIONID=JSESSIONID)
linkedin_integration = LinkedInIntegration(configuration)

## Parameters
linkedin_url = "https://www.linkedin.com/company/forvis-mazars"
data_store_path = "datastore/linkedin/get_organization_info"
linkedin_data = linkedin_integration.get_organization_info(linkedin_url)
linkedin_id = linkedin_integration.get_organization_id(linkedin_url)

# Get profile view
linkedin_url = "https://www.linkedin.com/in/sylvainfreon/"
data_store_path = "datastore/linkedin/get_profile_view"
linkedin_data = linkedin_integration.get_profile_view(linkedin_url)
linkedin_id = linkedin_integration.get_profile_id(linkedin_url)

# Initialize output directory
output_dir = os.path.join(data_store_path, linkedin_id)

# Save dict data
output_dir_data = os.path.join(output_dir, "data")
data = linkedin_data.get("data", {})
if len(get_json(output_dir_data, f"{linkedin_id}_data.json")) == 0:
    save_json(data, output_dir_data, f"{linkedin_id}_data.json")

def save_images(data: dict, key: str, output_dir: str):
    """
    Extracts picture URLs from a nested dictionary.

    Args:
        data (dict): The dictionary containing picture data.
        key (str): The key to extract picture URLs from.
        output_dir (str): The directory to save the images to.

    Returns:
        list: A list of picture URLs.
    """
    entity_urn = data.get("entityUrn")
    if key == "logo":
        root_url = pydash.get(data, f"{key}.image.rootUrl")
        artifacts = pydash.get(data, f"{key}.image.artifacts", [])
    else:
        root_url = pydash.get(data, f"{key}.rootUrl")
        artifacts = pydash.get(data, f"{key}.artifacts", [])
    if root_url:
        for x in artifacts:
            file_url = x.get("fileIdentifyingUrlPathSegment")
            image_url = f"{root_url}{file_url}"
            response = requests.get(image_url)
            save_image(response.content, output_dir, f"{entity_urn}_{key}_{file_url.split('/')[0]}.png")

# Save dict included
output_dir_included = os.path.join(output_dir, "included")
included = linkedin_data.get("included", [])
if len(get_json(output_dir_included, f"{linkedin_id}_included.json")) == 0:
    save_json(included, output_dir_included, f"{linkedin_id}_included.json")
for include in included:
    dict_type = include.get("$type")
    dict_label = dict_type.split(".")[-1].strip()
    output_dir_dict_type = os.path.join(output_dir_included, dict_label)
    entity_urn = include.get("entityUrn")
    if len(get_json(output_dir_dict_type, f"{entity_urn}.json")) == 0:
        save_json(include, output_dir_dict_type, f"{entity_urn}.json")
    for key in ["logo", "backgroundImage", "profile"]:
        if include.get(key):
            save_images(include, key, output_dir_dict_type)
