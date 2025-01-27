# Load .env file
import os
import requests
import yaml
import pydash
from dotenv import load_dotenv



def get_config():
    load_dotenv()
    
    naas_api_key = os.environ.get('NAAS_API_KEY')
    
    if naas_api_key is None:
        print("NAAS_API_KEY is not set in .env file. Please set it and try again.")
        exit(1)


    # Read config.yaml file
    with open('config.yaml', 'r') as file:
        config = yaml.safe_load(file)

    # Get workspace ID
    workspace_id = pydash.get(config, 'config.workspace_id')
    
    if workspace_id is None:
        print("config.workspace_id is not set in config.yaml file. Please set it and try again.")
        exit(1)


    # Get storage name
    storage_name = pydash.get(config, 'config.storage_name')
    
    if storage_name is None:
        print("config.storage_name is not set in config.yaml file. Please set it and try again.")
        exit(1)
        
    return naas_api_key, workspace_id, storage_name

if __name__ == "__main__":
    naas_api_key, workspace_id, storage_name = get_config()
    
    response = requests.post(f'https://api.naas.ai/workspace/{workspace_id}/storage/credentials/', headers={
        'Authorization': f'Bearer {naas_api_key}',
        'Content-Type': 'application/json'
    }, json={
        'name': storage_name
    })

    response.raise_for_status()
    
    res = response.json()
    
    bucket = pydash.get(res, 'credentials.s3.endpoint_url')
    access_key_id = pydash.get(res, 'credentials.s3.access_key_id')
    secret_access_key = pydash.get(res, 'credentials.s3.secret_key')
    session_token = pydash.get(res, 'credentials.s3.session_token')
    
    print(f'dvc remote add -f -d naas {bucket}/dvc')
    print(f'dvc remote modify --local naas access_key_id {access_key_id}')
    print(f'dvc remote modify --local naas secret_access_key {secret_access_key}')
    print(f'dvc remote modify --local naas session_token {session_token}')
