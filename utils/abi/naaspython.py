import requests
import json
import os
import datetime
import time


class CRUD:
    
    def __init__(
        self,
        req_url,
        headers,
    ):
        self.req_url = req_url
        self.headers = headers
        
    def post(self, data):
        response = requests.post(self.req_url, headers=self.headers, json=data)
        response.raise_for_status()
        return response.json()
    

    def get(self, uid=None):
        url = self.req_url
        if uid:
            url = os.path.join(self.req_url, uid)
        response = requests.get(url, headers=self.headers)
        return response.json()
    
    def put(self, uid, data):
        response = requests.put(os.path.join(self.req_url, uid), headers=self.headers, json=data)
        return response.json()
    
    def patch(self, uid, data):
        response = requests.patch(os.path.join(self.req_url, uid), headers=self.headers, json=data)
        return response.json()

    def delete(self, uid):
        response = requests.delete(os.path.join(self.req_url, uid), headers=self.headers)
        return response.json()

    
class Workspace(CRUD):
    
    def __init__(self, url, headers):
        self.req_url = url
        self.headers = headers
        
    def create(self, data):
        self.req_url = os.path.join(self.req_url, "")
        return self.post(data)

    def get_personal(self):
        # Init
        personal_workspace_id = None

        # Get workspaces
        workspaces = self.get()

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


class Plugin(CRUD):
    
    def __init__(self, url, headers, workspace_id):
        self.req_url = url
        self.headers = headers
        self.workspace_id = workspace_id
        
    def create(self, data):
        data = {
            "workspace_id": self.workspace_id,
            "payload": json.dumps(data),
        }
        return self.post(data)

    def update(self, uid, data):
        data = {
            "workspace_id": self.workspace_id,
            "plugin_id": uid,
            "workspace_plugin": {
                "payload": json.dumps(data),
            },
        }
        return self.put(uid, data)
    
    def duplicate(self, uid):
        # Get plugin payload
        plugin = self.get(uid)
        string_payload = plugin['workspace_plugin']['payload']
        payload = json.loads(string_payload)

        # Generate date string from UTC time YYYYMMDDHHMMSS
        date = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
        date = f'{date}-utc'

        # Edit payload
        payload['id'] = f"{payload['id']} ({date})"
        payload['name'] = f"{payload['name']} ({date})"
        payload['slug'] = f"{payload['slug']}-{date}"

        # Create workspace plugin
        return self.create(payload)
    
    def get_id(self, key="id", value="aia"):
        # List workspace plugins
        plugins = self.get()
        
        # Get value by key
        for i, p in enumerate(plugins.get('workspace_plugins')):
            plugin_id = p.get("id")
            p_json = json.loads(p.get("payload"))
            identifier = p_json.get(key)
            if identifier == value:
                return plugin_id
        return None


class Ontology(CRUD):
    
    def __init__(self, url, headers):
        self.req_url = url
        self.headers = headers
        
    def create(self, ontology):
        self.req_url = os.path.join(self.req_url, "")
        data = {"ontology": ontology}
        return self.post(data)
    
    def update(self, uid, ontology, field_masks=["label", "source", "download_url", "description", "logo_url", "level"]):
        ontology["id"] = uid
        ontology["field_mask"] = {}
        ontology["field_mask"]["paths"] = field_masks
        data = {"ontology": ontology}
        return self.patch(uid, data)

    def get(self, workspace_id, uid=""):
        url = os.path.join(self.req_url, uid)
        params = {
          "workspace_id": workspace_id,
          "page_size": 100,
          "page_number": 0
        }
        if uid != "":
            params["id"] = uid
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()
    
    def duplicate(self, workspace_id, uid):
        # Get ontology
        ontology = self.get(workspace_id, uid)
        ontology_dict = ontology['ontology']
        ontology_dict.pop("id")

        # Generate date string from UTC time YYYYMMDDHHMMSS
        date = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
        date = f'{date}-utc'

        # Edit payload
        ontology_dict['label'] = f"{ontology_dict['label']} ({date})"
        
        # Create ontology
        return self.create(ontology_dict)
    
    def get_id(self, workspace_id, key="label", value="aia"):
        ontologies = self.get(workspace_id).get("ontologies")
        for o in ontologies:
            if o.get(key) == value:
                return o.get("id")
        return None
    
    def delete(self, workspace_id, uid):
        url = os.path.join(self.req_url, uid)
        params = {
          "workspace_id": workspace_id,
        }
        response = requests.delete(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()

    
class User(CRUD):
    
    def __init__(self, url, headers, workspace_id):
        self.req_url = url
        self.headers = headers
        self.workspace_id = workspace_id
        
    def invite(self, email=None, role="member"):
        data = json.dumps(
            {
                "workspace_id": self.workspace_id,
                "email": email,
                "role": role,
            }
        )
        response = requests.post(os.path.join(self.req_url, ""), headers=self.headers, data=data)
        return response.json()


class Secret(CRUD):
    
    def __init__(self, url, headers):
        self.req_url = url
        self.headers = headers

        
class AIModel(CRUD):
    
    def __init__(self, url, headers):
        self.req_url = url
        self.headers = headers
        
    def create_completion(
        self,
        prompt="",
        message="",
        model_id="507dbbc5-88a1-4bd7-8c35-28cea3faaf1f",
    ):
        # Requests
        url = os.path.join(self.req_url, model_id, "completion")
        payload = json.dumps(
            {
                "id": model_id,
                "payload": json.dumps(
                    {
                        "messages": [
                            {"role": "system", "content": prompt},
                            {"role": "user", "content": message},
                        ]
                    }
                ),
            }
        )
        result = None
        retry = 0
        while True:
            try:
                response = requests.post(url, headers=self.headers, data=payload)
                result = response.json()["completion"]["completions"][0]
                break
            except Exception as e:
                print(e)
            retry += 1
            time.sleep(5)
            if retry >= 3:
                break
        return result
        
        
class NaasPython:
    
    def connect(self, api_key, workspace_id=None):
        self.api_key = api_key
        self.headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}
        self.base_url = "https://api.naas.ai"
        self.workspace_id = workspace_id
        if workspace_id:
            self.base_url = os.path.join("https://api.naas.ai", "workspace", self.workspace_id)

        # Init end point
        self.workspace = Workspace(os.path.join(self.base_url, "workspace", ""), self.headers)
        self.plugin = Plugin(os.path.join(self.base_url, "plugin"), self.headers, self.workspace_id)
        self.user = User(os.path.join(self.base_url, "user"), self.headers, self.workspace_id)
        self.ontology = Ontology(os.path.join(self.base_url, "ontology", ""), self.headers)
        self.secret = Secret(os.path.join(self.base_url, "secret", ""), self.headers)
        self.aimodel = AIModel(os.path.join(self.base_url, "model"), self.headers)
        return self
