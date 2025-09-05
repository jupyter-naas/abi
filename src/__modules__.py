from abi.utils.Module import IModule
from abi import logger
from typing import List
import importlib
from pathlib import Path

__modules: List[IModule] = []
__loaded: bool = False

def get_modules(config=None):
    """Loads and returns all enabled modules from the module directories.

    This method scans all MODULE_PATH directories and dynamically loads each module found.
    Modules are autonomous and self-contained - they can be added by simply dropping them
    into the appropriate modules directory without modifying other code.

    The modules are only loaded once - subsequent calls return the cached modules list.

    Args:
        config: Configuration object containing module settings

    Returns:
        List[IModule]: List of loaded module instances
    """
    global __modules, __loaded
    if not __loaded:
        # Get enabled modules from config if provided
        enabled_modules = []
        
        if config is not None and hasattr(config, 'modules'):
            enabled_modules = [m.path for m in config.modules if m.enabled]
        
        logger.debug(f"Modules from config.yaml: {enabled_modules}")
        for modulepath in enabled_modules:
            module = Path(modulepath)
            module_path_str = str(module)
            
            if not module.is_dir():
                error_message = f"Module {modulepath} does not exist! This message is showing because you have a module in your config.yaml that does not exist. Please either remove it, set enabled to false or fix the path."
                logger.error(error_message)
                raise ValueError(error_message)
            
            if (
                module.name != "__pycache__"
                and "disabled" not in module.name
                ):
                try:
                    logger.debug(f"Loading module: {module_path_str}")
                    module_relative_path = ".".join(
                        modulepath.split("/")
                    )
                    

                    # We import the module for it to be initialized.
                    imported_module = importlib.import_module(module_relative_path)

                    module_path = modulepath
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
