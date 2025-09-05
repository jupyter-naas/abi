from abi.utils.Module import IModule
from abi import logger
from typing import List, Dict, Set
import importlib
import ast
import os
from pathlib import Path

__modules: List[IModule] = []
__loaded: bool = False
__loading: bool = False  # Flag to prevent recursive loading

def analyze_module_dependencies(module_paths: List[str]) -> Dict[str, Set[str]]:
    """Analyze module dependencies by parsing import statements in agent files.
    
    Returns:
        Dict mapping module_path -> set of dependency module_paths
    """
    dependencies = {path: set() for path in module_paths}
    
    for module_path in module_paths:
        logger.debug(f"Analyzing dependencies for module: {module_path}")
        module_dir = Path(module_path)
        if not module_dir.exists():
            continue

        # Find all Python files in this module recursively
        for py_file in module_dir.rglob("*.py"):
            if "sandbox" in str(py_file):
                continue
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                # Parse the file to find import statements and function calls
                tree = ast.parse(content)
                
                # Check for get_modules() calls or "from src import modules" - if found, this module needs ALL other modules
                get_modules_found = False
                modules_imported = False
                
                # First check for "from src import modules" import statement
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom):
                        if node.module == 'src' and node.names:
                            for alias in node.names:
                                if alias.name == 'modules':
                                    modules_imported = True
                                    logger.debug(f"'from src import modules' found in {py_file}")
                                    break
                        if modules_imported:
                            break
                
                # If modules is imported, check if it's used (making this module depend on all others)
                if modules_imported:
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Name) and node.id == 'modules':
                            get_modules_found = True
                            logger.debug(f"Imported 'modules' is used in {py_file}")
                            break
                        elif isinstance(node, ast.For) and isinstance(node.iter, ast.Name) and node.iter.id == 'modules':
                            get_modules_found = True
                            logger.debug(f"Imported 'modules' is iterated over in {py_file}")
                            break
                
                # Also check for get_modules() function calls
                if not get_modules_found:
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Call):
                            if isinstance(node.func, ast.Name) and (node.func.id == 'get_modules' or node.func.id == 'modules'):
                                get_modules_found = True
                                logger.debug(f"All modules are called in {py_file}")
                                break
                            elif isinstance(node.func, ast.Attribute) and (node.func.attr == 'get_modules' or node.func.attr == 'modules'):
                                get_modules_found = True
                                logger.debug(f"All modules are called in {py_file}")
                                break
                
                # If get_modules() is found, this module depends on ALL other modules
                if get_modules_found:
                    for other_module in module_paths:
                        if other_module != module_path:
                            dependencies[module_path].add(other_module)
                    logger.info(f"Module {module_path} depends on ALL other modules")
                else:
                    # Regular dependency analysis for import statements
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ImportFrom) and node.module:
                            module_name = node.module
                            
                            # Check if this is importing from another src module
                            if '.modules.' in module_name and module_name != module_path:
                                # Extract the module path from the import
                                parts = module_name.split('.')
                                if 'modules' in parts:
                                    module_idx = parts.index('modules')
                                    if len(parts) > module_idx + 1:
                                        # For marketplace module, include 2 levels after modules
                                        if 'marketplace' in parts and module_idx > 0 and parts[module_idx-1] == 'marketplace':
                                            if len(parts) > module_idx + 2:
                                                dep_module_path = '/'.join(['src'] + parts[module_idx-1:module_idx+3])
                                            else:
                                                dep_module_path = '/'.join(['src'] + parts[module_idx-1:module_idx+2])
                                        else:
                                            dep_module_path = '/'.join(['src'] + parts[module_idx-1:module_idx+2])
                                        
                                        # Check if dependency exists in module_paths
                                        if not any(dep_module_path.startswith(path) for path in module_paths):
                                            logger.debug(f"Analyzing file {py_file}")
                                            logger.warning(f"Module {module_path} imports from {dep_module_path} but that module is not in the module list")
                                        # Only add dependency if it's in our module list and different from current
                                        elif dep_module_path != module_path:
                                            logger.debug(f"Analyzing file {py_file}")
                                            dependencies[module_path].add(dep_module_path)
                                            logger.debug(f"Module {module_path} depends on {dep_module_path}")
                                        
            except Exception as e:
                logger.warning(f"Could not analyze dependencies for {py_file}: {e}")
                
    return dependencies

def topological_sort(module_paths: List[str], dependencies: Dict[str, Set[str]]) -> List[str]:
    """Sort modules based on their dependencies using topological sort.
    
    Returns modules in order where dependencies are loaded before dependents.
    """
    # Create a copy of dependencies for modification
    deps = {path: deps.copy() for path, deps in dependencies.items()}
    result = []
    
    # Find modules with no dependencies
    no_deps = [path for path, dep_set in deps.items() if not dep_set]
    
    while no_deps:
        # Pick a module with no dependencies
        current = no_deps.pop(0)
        result.append(current)
        
        # Remove this module from all dependency lists
        for path in deps:
            if current in deps[path]:
                deps[path].remove(current)
                # If this module now has no dependencies, add it to the queue
                if not deps[path] and path not in result and path not in no_deps:
                    no_deps.append(path)
    
    # Check for circular dependencies
    remaining = [path for path, dep_set in deps.items() if dep_set and path not in result]
    if remaining:
        logger.warning(f"Circular dependencies detected in modules: {remaining}")
        # Add remaining modules anyway to prevent failure
        result.extend(remaining)
    
    return result

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
    global __modules, __loaded, __loading
    
    # If we're currently loading, return the current state (even if incomplete)
    # This prevents infinite recursion when agents call get_modules() during their creation
    if __loading:
        logger.debug("Module loading in progress, returning current state")
        return __modules
    
    if not __loaded:
        __loading = True
        try:
            # Get enabled modules from config if provided
            enabled_modules = []
            
            if config is not None and hasattr(config, 'modules'):
                enabled_modules = [m.path for m in config.modules if m.enabled]
            
            logger.debug(f"Modules from config.yaml: {enabled_modules}")
            
            # Filter valid modules
            valid_modules = []
            for modulepath in enabled_modules:
                module = Path(modulepath)
                
                if not module.is_dir():
                    error_message = f"Module {modulepath} does not exist! This message is showing because you have a module in your config.yaml that does not exist. Please either remove it, set enabled to false or fix the path."
                    logger.error(error_message)
                    raise ValueError(error_message)
                
                if (
                    module.name != "__pycache__"
                    and "disabled" not in module.name
                    ):
                    valid_modules.append(modulepath)
            
            # Analyze dependencies and sort modules
            logger.debug("Analyzing module dependencies...")
            dependencies = analyze_module_dependencies(valid_modules)
            sorted_modules = topological_sort(valid_modules, dependencies)
            
            logger.debug(f"Module loading order: {sorted_modules}")
            
            # Load modules in dependency order
            for modulepath in sorted_modules:
                try:
                    logger.debug(f"Loading module: {modulepath}")
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
                    
                    logger.error(f"❌ Critical error loading module {modulepath}: {e}")
                    traceback.print_exc()
                    raise SystemExit(f"Application crashed due to module loading failure: {modulepath}")

            __loaded = True
        finally:
            __loading = False

    return __modules
