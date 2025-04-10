from common import get_config, get_storage_credentials
import os
from datetime import datetime

if __name__ == "__main__":
    
    # Ask user to validate storage? (y/n): " confirm
    confirm = input("Are you sure you want to override the storage? (y/n): ")
    if confirm != "y":
        print("Storage override cancelled.")
        exit()
    
    naas_api_key, workspace_id, storage_name = get_config()
    bucket, access_key_id, secret_access_key, session_token = get_storage_credentials(naas_api_key, workspace_id, storage_name)
    
    # Backup the prod before overriding
    backup_timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    os.system(f'AWS_ACCESS_KEY_ID={access_key_id} AWS_SECRET_ACCESS_KEY={secret_access_key} AWS_SESSION_TOKEN={session_token} aws s3 mv --recursive {bucket}/ontologies {bucket}/ontologies-backups/{backup_timestamp}')
    
    # os.system(f'AWS_ACCESS_KEY_ID={access_key_id} AWS_SECRET_ACCESS_KEY={secret_access_key} AWS_SESSION_TOKEN={session_token} aws s3 cp --recursive {bucket}/storage/triplestore {bucket}/ontologies')
    os.system(f'AWS_ACCESS_KEY_ID={access_key_id} AWS_SECRET_ACCESS_KEY={secret_access_key} AWS_SESSION_TOKEN={session_token} aws s3 sync --follow-symlinks --delete  storage/triplestore {bucket}/ontologies')