# Load .env file
import requests
import pydash
from common import get_config, get_storage_credentials

if __name__ == "__main__":
    naas_api_key, workspace_id, storage_name = get_config()
    bucket, access_key_id, secret_access_key, session_token = get_storage_credentials(
        naas_api_key, workspace_id, storage_name
    )

    print(f"dvc remote add -f -d naas {bucket}/dvc")
    print(f"dvc remote modify --local naas access_key_id {access_key_id}")
    print(f"dvc remote modify --local naas secret_access_key {secret_access_key}")
    print(f"dvc remote modify --local naas session_token {session_token}")
