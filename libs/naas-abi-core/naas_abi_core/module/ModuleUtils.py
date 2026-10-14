import inspect
import sys
from pathlib import Path


def module_package(class_: type) -> str:
    """The dotted package of the folder holding ``class_``: where the loaders look
    for ``agents/``, ``workflows/``, ``models/``... (``find_class_module_root_path``).

    ``pkg`` for a class defined in ``pkg/__init__.py`` and also for one defined in a
    submodule such as ``pkg/_abi_module.py``, whose ``__module__`` is
    ``pkg._abi_module``: its components are under ``pkg``, not under that file.
    """
    module = sys.modules.get(class_.__module__)
    package = getattr(module, "__package__", None)
    if package is None:
        file = getattr(module, "__file__", "") or ""
        package = (
            class_.__module__
            if Path(file).name == "__init__.py"
            else class_.__module__.rpartition(".")[0]
        )
    return package or class_.__module__


def find_class_module_root_path(class_: type) -> Path:
    class_file_path = inspect.getfile(class_)
    class_path = Path(class_file_path)
    class_directory = str(class_path.parent)
    return Path(class_directory)
    # logger.debug(f"Class directory: {class_.__module__}")
    # logger.debug(f"Class file path: {class_directory}")
    # module_name = class_.__module__.split(".")[0]

    # # find last occurrence of module_name in class_directory
    # module_root_path = class_directory[
    #     : class_directory.rfind(module_name) + len(module_name)
    # ]

    # logger.debug(f"Module root path: {module_root_path}")
    # return Path(module_root_path)
