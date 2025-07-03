import os

    
# Look for a "storage" folder until we reach /
def find_storage_folder(base_path: str, needle: str = "storage") -> str:
    if os.path.exists(os.path.join(base_path, needle)):
        return os.path.join(base_path, needle)

    if base_path == "/":
        raise Exception("No storage folder found")

    return find_storage_folder(os.path.dirname(base_path))