import naas_python
import pydash as _
import requests
import os
from io import BytesIO
import json


class AssetManager:

    def __init__(self, workspace_id, storage_name, storage_manager, api_key):
        self.workspace_id = workspace_id
        self.storage_name = storage_name
        self.storage_manager = storage_manager
        self.api_key = api_key

    def create_asset(self, data):
        url = f"https://api.naas.ai/workspace/{self.workspace_id}/asset/"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        response = requests.post(url, headers=headers, data=data)
        return response.json()

    def update_asset(self, asset_id, data):
        url = f"https://api.naas.ai/workspace/{self.workspace_id}/asset/{asset_id}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        response = requests.put(url, headers=headers, data=data)
        return response.json()

    def get_asset(self, asset_id):
        url = f"https://api.naas.ai/workspace/{self.workspace_id}/asset/{asset_id}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        response = requests.get(url, headers=headers)
        return response.json()

    def add(
        self,
        file_path=None,
        file_s3=None,
        visibility="public",
        content_disposition="inline",
        password=None,
    ):
        # Init
        asset_id = None
        asset = {}

        # Upload file in storage
        if file_s3 is None:
            file_s3 = self.storage_manager.upload_file(file_path)
            
        # Create asset
        try:
            data = json.dumps(
                {
                    "workspace_id": self.workspace_id,
                    "asset_creation": {
                        "workspace_id": self.workspace_id,
                        "storage_name": self.storage_name,
                        "object_name": file_s3,
                        "visibility": visibility,
                        "content_disposition": content_disposition,
                        "password": password,
                    },
                }
            )
            asset = self.create_asset(data)
            if "message" in asset:
                asset_id = asset.get("message").split("id:'")[1].split("'")[0]
                asset = self.get_asset(asset_id)
        except Exception as e:
            print(e)
        return asset

    def delete(
        self,
        asset_id,
    ):
        naas_python.asset.delete_asset(
            workspace_id=self.workspace_id, asset_id=asset_id
        )

    def create_image_asset_from_url(self, url, output_dir, file_name):
        image_path = os.path.join(output_dir, file_name)
        try:
            self.storage_manager.get_object(output_dir, file_name)
#             print(f"'{file_name}' already exist in storage!")
        except Exception as e:
            # Get image from web
            response = requests.get(url)

            # Put object to storage
            image_path = self.storage_manager.put_object(
                BytesIO(response.content), output_dir, file_name, "png"
            )
        # Create asset
        asset = self.add(file_s3=image_path)
        asset_url = _.get(asset, "asset.url")
        print("🔗 URL:", asset_url)
        return asset_url
