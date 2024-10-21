import requests
import json
import naas_python


def invite_user_to_workspace(api_key, workspace_id, email=None, role="member"):
    url = f"https://api.naas.ai/workspace/{workspace_id}/user/"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    data = json.dumps(
        {
            "workspace_id": workspace_id,
            # "user_id": user_id,
            "email": email,
            "role": role,
        }
    )
    response = requests.post(url, headers=headers, data=data)
    response.raise_for_status()
    return response.json()


def create_workspace(
    api_key,
    data,
):
    url = "https://api.naas.ai/workspace"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    return response.json()


def delete_workspace(
    api_key,
    uid,
):
    url = f"https://api.naas.ai/workspace/{uid}"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    response = requests.delete(url, headers=headers)
    response.raise_for_status()
    return response.json()


def list_workspaces(
    api_key,
):
    url = "https://api.naas.ai/workspace/"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def get_personal_workspace(api_key):
    # Init
    personal_workspace_id = None

    # Get workspaces
    workspaces = list_workspaces(api_key)

    # Get existing workspace ids
    current_workspace_ids = [
        workspace.get("id") for workspace in workspaces.get("workspaces")
    ]

    # Get personal workspace
    for workspace in workspaces.get("workspaces"):
        if workspace.get("is_personal"):
            personal_workspace_id = workspace.get("id")
            break
    return personal_workspace_id


def list_workspace_plugins(
    api_key,
    workspace_id,
):
    url = f"https://api.naas.ai/workspace/{workspace_id}/plugin"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def create_workspace_plugin(
    api_key,
    workspace_id,
    plugin,
):
    url = f"https://api.naas.ai/workspace/{workspace_id}/plugin"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    data = {
        "workspace_id": workspace_id,
        "payload": json.dumps(plugin),
    }
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    return response.json()


def update_workspace_plugin(
    api_key,
    workspace_id,
    plugin_id,
    plugin,
):
    url = f"https://api.naas.ai/workspace/{workspace_id}/plugin/{plugin_id}"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    data = {
        "workspace_id": workspace_id,
        "plugin_id": plugin_id,
        "workspace_plugin": {
            "payload": json.dumps(plugin),
        },
    }
    response = requests.put(url, headers=headers, json=data)
    response.raise_for_status()
    return response.json()


def delete_workspace_plugin(
    api_key,
    workspace_id,
    plugin_id,
):
    url = f"https://api.naas.ai/workspace/{workspace_id}/plugin/{plugin_id}"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    response = requests.delete(url, headers=headers)
    response.raise_for_status()
    return response.json()


def get_workspace_plugin(
    api_key,
    workspace_id,
    plugin_id,
):
    url = f"https://api.naas.ai/workspace/{workspace_id}/plugin/{plugin_id}"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def list_workspace_storage(
    api_key,
    workspace_id,
):
    url = f"https://api.naas.ai/workspace/{workspace_id}/storage/"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def create_workspace_storage(
    api_key,
    workspace_id,
    storage_name,
):
    url = f"https://api.naas.ai/workspace/{workspace_id}/storage/"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    payload = {"storage": {"name": storage_name}}
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()


def create_workspace_storage_credentials(
    api_key,
    workspace_id,
    storage_name,
):
    url = f"https://api.naas.ai/workspace/{workspace_id}/storage/credentials/"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    payload = json.dumps({"name": storage_name, "workspace_id": workspace_id})
    response = requests.post(url, headers=headers, data=payload)
    response.raise_for_status()
    return response.json()


def get_storage_credentials(
    workspace_id=None,
    storage_name=None,
    api_key=None,
):
    # Init
    if not api_key:
        api_key = naas_python.utils.domains_base.authorization.NaasSpaceAuthenticatorAdapter().jwt_token()
    if not workspace_id:
        workspace_id = get_personal_workspace(api_key)
        
    # List storage
    result = list_workspace_storage(api_key, workspace_id)
#     result = naas_python.storage.list_workspace_storage(workspace_id=workspace_id)
    storages = result.get("storage")
    storage_exist = False
    for storage in storages:
        if storage.get("name") == storage_name:
            storage_exist = True
            new_storage = storage
            
    # Create storage
    if not storage_exist:
#         new_storage = naas_python.storage.create_workspace_storage(workspace_id=workspace_id, storage_name=storage_name).get("storage")
        new_storage = create_workspace_storage(api_key, workspace_id, storage_name)
        print(new_storage)
        
    # Get storage credentials
#     credentials = naas_python.storage.create_workspace_storage_credentials(workspace_id=workspace_id, storage_name=storage_name)
    credentials = create_workspace_storage_credentials(api_key, workspace_id, storage_name)
    return credentials, workspace_id
