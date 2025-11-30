import os

class NoStorageFolderFound(Exception):
    pass

# Look for a "storage" folder until we reach /
def find_storage_folder(base_path: str, needle: str = "storage") -> str:
    if os.path.exists(os.path.join(base_path, needle)):
        return os.path.join(base_path, needle)

    if base_path == "/":
        raise NoStorageFolderFound("No storage folder found")

    return find_storage_folder(os.path.dirname(base_path))

def ensure_data_directory(module_name: str, component: str) -> str:
    """
    Ensures the data directory exists for a module component following Code-Data Symmetry.
    
    Args:
        module_name: Name of the module (e.g., "__demo__", "your_module")
        component: Component type (e.g., "orchestration", "pipelines", "workflows")
    
    Returns:
        str: The absolute path to the created directory
    
    Example:
        data_dir = ensure_data_directory("__demo__", "orchestration")
        # Returns: /path/to/project/storage/datastore/core/modules/__demo__/orchestration
    """
    data_dir = os.path.join("storage", "datastore", "core", "modules", module_name, component)
    os.makedirs(data_dir, exist_ok=True)
    return os.path.abspath(data_dir)
