from abi.utils.Module import IModule
from abi import logger
from typing import List, Dict, Any
import importlib
import os
import time
from pathlib import Path
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.ConfigLoader import get_ai_network_config

__modules: List[IModule] = []
__loaded: bool = False


def get_modules():
    """
    Load modules based on AI Network configuration from config.yaml.
    
    This method replaces the old "disabled" prefix system with a centralized
    configuration approach. Modules are loaded according to their enabled status
    and priority settings in the ai_network section of config.yaml.

    The modules are only loaded once - subsequent calls return the cached modules list.

    Returns:
        List[IModule]: List of loaded module instances
    """
    global __modules, __loaded
    if not __loaded:
        start_time = time.time()
        logger.info("🚀 Starting AI Network module loading...")
        
        # Load configuration
        config = get_ai_network_config()
        enabled_modules = config.get_enabled_modules()
        module_paths = config.get_module_paths()
        loading_settings = config.get_loading_settings()
        
        total_enabled = sum(len(modules) for modules in enabled_modules.values())
        logger.info(f"📊 Found {total_enabled} enabled modules across all categories")
        
        # Load modules by category in priority order
        for category, modules in enabled_modules.items():
            if not modules:
                continue
                
            category_path = module_paths[category]
            logger.info(f"📂 Loading {len(modules)} modules from '{category}' ({category_path})")
            
            for module_config in modules:
                module_name = module_config["name"]
                priority = module_config.get("priority", 999)
                description = module_config.get("description", "No description")
                
                success = _load_single_module(
                    module_name, 
                    category, 
                    category_path, 
                    loading_settings,
                    priority,
                    description
                )
                
                if not success and loading_settings.get("fail_on_error", True):
                    logger.error(f"❌ Critical: Module loading failed and fail_on_error is enabled")
                    raise SystemExit(f"Application crashed due to module loading failure: {module_name}")

        __loaded = True
        
        load_time = time.time() - start_time
        logger.info(f"✅ AI Network module loading completed in {load_time:.2f}s")
        logger.info(f"📈 Successfully loaded {len(__modules)} modules")

    return __modules


def _load_single_module(
    module_name: str, 
    category: str, 
    base_path: str, 
    loading_settings: Dict[str, Any],
    priority: int,
    description: str
) -> bool:
    """
    Load a single module with retry logic and error handling.
    
    Args:
        module_name: Name of the module to load
        category: Category of the module (core_models, domain_experts, etc.)
        base_path: Base path where the module is located
        loading_settings: Loading configuration settings
        priority: Module priority for loading order
        description: Module description for logging
        
    Returns:
        bool: True if module loaded successfully, False otherwise
    """
    retry_attempts = loading_settings.get("retry_attempts", 3)
    timeout_seconds = loading_settings.get("timeout_seconds", 30)
    
    for attempt in range(retry_attempts):
        try:
            # Determine the actual module path based on category
            if category == "domain_experts":
                # Domain experts are in subdirectories
                module_path = Path(base_path) / module_name
            else:
                # Other modules are direct subdirectories
                module_path = Path(base_path) / module_name
            
            # Check if module directory exists
            if not module_path.exists():
                # For applications, check if it has .disabled suffix
                disabled_path = Path(f"{module_path}.disabled")
                if disabled_path.exists():
                    logger.warning(f"⚠️ Module '{module_name}' exists but is disabled via .disabled suffix")
                    logger.info(f"💡 Remove .disabled suffix or update config to enable: {disabled_path}")
                    return False
                else:
                    logger.error(f"❌ Module directory not found: {module_path}")
                    return False
            
            # Skip if it's a __pycache__ directory
            if module_path.name == "__pycache__":
                return True
            
            # Build import path
            if category == "domain_experts":
                module_relative_path = f"src.marketplace.modules.domains.modules.{module_name}"
            elif category == "applications":
                module_relative_path = f"src.marketplace.modules.applications.{module_name}"
            elif category == "core_models":
                module_relative_path = f"src.core.modules.{module_name}"
            elif category == "custom_modules":
                module_relative_path = f"src.custom.modules.{module_name}"
            else:
                logger.error(f"❌ Unknown module category: {category}")
                return False
            
            logger.info(f"🔄 Loading module '{module_name}' (priority: {priority}) - {description}")
            
            # Import the module
            imported_module = importlib.import_module(module_relative_path)
            
            # Create IModule instance
            module_import_path = module_relative_path.replace("/", ".")
            mod = IModule(str(module_path), module_import_path, imported_module)
            mod.load()
            
            __modules.append(mod)
            
            logger.info(f"✅ Successfully loaded module '{module_name}'")
            return True
            
        except ImportError as e:
            logger.warning(f"⚠️ Import error for module '{module_name}' (attempt {attempt + 1}/{retry_attempts}): {e}")
            if attempt == retry_attempts - 1:
                logger.error(f"❌ Failed to import module '{module_name}' after {retry_attempts} attempts")
                return False
        except Exception as e:
            import traceback
            logger.error(f"❌ Error loading module '{module_name}' (attempt {attempt + 1}/{retry_attempts}): {e}")
            if logger.level <= 10:  # DEBUG level
                traceback.print_exc()
            
            if attempt == retry_attempts - 1:
                logger.error(f"❌ Failed to load module '{module_name}' after {retry_attempts} attempts")
                return False
        
        # Wait before retry (exponential backoff)
        if attempt < retry_attempts - 1:
            wait_time = 2 ** attempt
            logger.info(f"⏳ Waiting {wait_time}s before retry...")
            time.sleep(wait_time)
    
    return False


def reload_modules():
    """
    Reload all modules (useful for development and testing).
    This will clear the module cache and reload based on current configuration.
    """
    global __modules, __loaded
    __modules = []
    __loaded = False
    
    # Also reload the configuration
    from src.utils.ConfigLoader import reload_config
    reload_config()
    
    logger.info("🔄 Module cache cleared, reloading modules...")
    return get_modules()


def get_module_by_name(module_name: str) -> IModule:
    """
    Get a specific module by name.
    
    Args:
        module_name: Name of the module to retrieve
        
    Returns:
        IModule: The requested module instance
        
    Raises:
        ValueError: If module is not found
    """
    modules = get_modules()
    
    for module in modules:
        if module_name in module.module_import_path:
            return module
    
    raise ValueError(f"Module '{module_name}' not found in loaded modules")


def get_modules_by_category(category: str) -> List[IModule]:
    """
    Get all modules from a specific category.
    
    Args:
        category: Category name (core_models, domain_experts, applications, custom_modules)
        
    Returns:
        List[IModule]: List of modules in the specified category
    """
    modules = get_modules()
    category_modules = []
    
    # Map category to path patterns
    path_patterns = {
        "core_models": "src.core.modules",
        "domain_experts": "src.marketplace.modules.domains.modules",
        "applications": "src.marketplace.modules.applications",
        "custom_modules": "src.custom.modules"
    }
    
    pattern = path_patterns.get(category)
    if not pattern:
        logger.warning(f"⚠️ Unknown category: {category}")
        return []
    
    for module in modules:
        if pattern in module.module_import_path:
            category_modules.append(module)
    
    return category_modules