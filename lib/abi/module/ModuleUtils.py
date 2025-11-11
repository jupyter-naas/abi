import inspect
from pathlib import Path


def find_class_module_root_path(class_: type) -> Path:
    class_file_path = inspect.getfile(class_)
    class_path = Path(class_file_path)
    class_directory = str(class_path.parent)
    module_name = class_.__module__.split(".")[0]

    # find last occurrence of module_name in class_directory
    module_root_path = class_directory[
        : class_directory.rfind(module_name) + len(module_name)
    ]
    return Path(module_root_path)
