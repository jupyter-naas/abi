from urllib.parse import quote
import hashlib
import uuid
from uuid import UUID

def create_id_from_string(string: str) -> str:
    """Create a URL-safe ID from a string.

    Args:
        string (str): Input string to convert

    Returns:
        str: URL-safe string with spaces replaced by hyphens
    """
    return quote(string.replace(" ", "-").lower(), safe="")

def string_to_uuid(input_string: str) -> UUID:
    """Convert a string to a UUID.

    Args:
        input_string (str): Input string to convert

    Returns:
        str: UUID
    """
    hash_object = hashlib.sha256(input_string.encode())
    hex_hash = hash_object.hexdigest()
    uuid_obj = uuid.UUID(hex_hash[:32])
    return uuid_obj