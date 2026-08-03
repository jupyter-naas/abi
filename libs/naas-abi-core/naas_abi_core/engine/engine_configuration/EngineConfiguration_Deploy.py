from pydantic import BaseModel


class DeployConfiguration(BaseModel):
    workspace_id: str
    space_name: str
    naas_api_key: str
    env: dict[str, str] = {}
