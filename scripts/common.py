from dotenv import load_dotenv
import os
import yaml
import pydash
import requests

def get_storage_credentials(naas_api_key, workspace_id, storage_name):
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
    
    return bucket, access_key_id, secret_access_key, session_token

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