from abi.utils.Module import IModule
from abi import logger
from typing import List
import importlib
import os
from pathlib import Path

MODULE_PATH: list[str] = [
    "src/core/modules",
    "src/custom/modules",
    "src/marketplace/modules",
]

__modules: List[IModule] = []
__loaded: bool = False


def get_modules():
    """Loads and returns all enabled modules from the src/modules directory.

    This method scans the src/modules directory and dynamically loads each module found.
    Modules are autonomous and self-contained - they can be added by simply dropping them
    into the modules directory without modifying other code. A module can be disabled
    by adding "disabled" to its directory name (e.g. "opendata_disabled").

    The modules are only loaded once - subsequent calls return the cached modules list.

    Returns:
        List[IModule]: List of loaded module instances
    """
    global __modules, __loaded
    if not __loaded:
        for modulepath in MODULE_PATH:
            for module in Path(modulepath).glob("*/"):
                if (
                    module.is_dir()
                    and module.name != "__pycache__"
                    and "disabled" not in module.name
                ):
                    try:
                        module_relative_path = ".".join(
                            modulepath.split("/") + [module.name]
                        )

                        # We import the module for it to be initialized.
                        imported_module = importlib.import_module(module_relative_path)

                        module_path = os.path.join(modulepath, module.name)
                        module_import_path = ".".join(module_path.split("/"))

                        mod = IModule(module_path, module_import_path, imported_module)
                        mod.load()

                        __modules.append(mod)
                    except Exception as e:
                        import traceback
                        
                        logger.error(f"❌ Critical error loading module {module.name}: {e}")
                        traceback.print_exc()
                        raise SystemExit(f"Application crashed due to module loading failure: {module.name}")

        __loaded = True

    return __modules
