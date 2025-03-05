from abi.utils.Module import IModule
from typing import List
import importlib
import os
from pathlib import Path

MODULE_PATH = 'src/modules'

__modules : List[IModule] = []
__loaded : bool = False

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
        for module in Path(MODULE_PATH).glob('*/'):
            if module.is_dir() and module.name != '__pycache__' and "disabled" not in module.name:
                module_relative_path = '.'.join(MODULE_PATH.split('/') + [module.name])
                
                # We import the module for it to be initialized.
                importlib.import_module(module_relative_path)
                
                
                module_path = os.path.join(MODULE_PATH, module.name)
                module_import_path = '.'.join(module_path.split('/'))
                
                mod = IModule(module_path, module_import_path)
                mod.load()
                
                __modules.append(mod)
        
        __loaded = True
    
    return __modules