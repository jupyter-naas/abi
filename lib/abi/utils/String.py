from urllib.parse import quote


def create_id_from_string(string: str) -> str:
    """Create a URL-safe ID from a string.

    Args:
        string (str): Input string to convert

    Returns:
        str: URL-safe string with spaces replaced by hyphens
    """
    return quote(string.replace(" ", "-").lower(), safe="")
