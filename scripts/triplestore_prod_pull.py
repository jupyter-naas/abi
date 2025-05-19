from common import get_config, get_storage_credentials
import os

if __name__ == "__main__":
    naas_api_key, workspace_id, storage_name = get_config()
    bucket, access_key_id, secret_access_key, session_token = get_storage_credentials(
        naas_api_key, workspace_id, storage_name
    )

    os.system(
        f"AWS_ACCESS_KEY_ID={access_key_id} AWS_SECRET_ACCESS_KEY={secret_access_key} AWS_SESSION_TOKEN={session_token} aws s3 sync --follow-symlinks --delete {bucket}/ontologies storage/triplestore"
    )
