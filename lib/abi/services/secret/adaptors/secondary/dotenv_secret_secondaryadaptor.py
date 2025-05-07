from abi.services.secret.SecretPorts import ISecretAdapter
from dotenv import load_dotenv
import os


class DotenvSecretSecondaryAdaptor(ISecretAdapter):
    def __init__(self):
        load_dotenv()

    def get(self, key: str, default: any = None) -> str:
        return os.getenv(key, default)
