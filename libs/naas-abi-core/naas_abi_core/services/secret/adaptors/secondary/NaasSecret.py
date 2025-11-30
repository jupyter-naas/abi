from typing import Any, Dict

import requests
from naas_abi_core import logger
from naas_abi_core.services.secret.SecretPorts import ISecretAdapter

NAAS_API_URL = "https://api.naas.ai"


class NaasSecret(ISecretAdapter):
    def __init__(self, naas_api_key: str, naas_api_url: str | None = None):
        self.naas_api_key = naas_api_key

        if naas_api_url is None:
            self.naas_api_url = NAAS_API_URL
        else:
            self.naas_api_url = naas_api_url

    def get(self, key: str, default: Any = None) -> str | Any | None:
        response = requests.get(
            f"{self.naas_api_url}/secret/{key}",
            headers={"Authorization": f"Bearer {self.naas_api_key}"},
        )
        try:
            response.raise_for_status()
            return str(response.json()["secret"]["value"])
        except requests.exceptions.HTTPError as _:
            if response.status_code == 404:
                logger.debug(f"Secret {key} not found")
            else:
                logger.error(f"Error getting secret {key}: {response.status_code}")
            return default

    def set(self, key: str, value: str):
        response = requests.post(
            f"{self.naas_api_url}/secret/",
            headers={"Authorization": f"Bearer {self.naas_api_key}"},
            json={"secret": {"name": key, "value": value}},
        )

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as _:
            logger.error(f"Error setting secret {key}: {response.status_code}")
            return

    def remove(self, key: str):
        response = requests.delete(
            f"{self.naas_api_url}/secret/{key}",
            headers={"Authorization": f"Bearer {self.naas_api_key}"},
        )

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as _:
            logger.error(f"Error removing secret {key}: {response.status_code}")
            return

    def list(self) -> Dict[str, str | None]:
        response = requests.get(
            f"{self.naas_api_url}/secret/",
            headers={"Authorization": f"Bearer {self.naas_api_key}"},
            json={
                "page_size": 1000,
                "page_number": 1,
            },
        )

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as _:
            if response.status_code == 404:
                logger.debug("No secrets found or workspace not accessible")
            else:
                logger.error(f"Error listing secrets: {response.status_code}")
            return {}

        return {
            str(secret["name"]): str(secret["value"])
            for secret in response.json()["secrets"]
        }
