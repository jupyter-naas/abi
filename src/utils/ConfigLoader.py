"""
AI Network Configuration Loader

This module handles loading and parsing the AI Network configuration from config.yaml,
replacing the old "disabled" prefix system with a centralized configuration approach.
"""

import yaml
import os
from typing import Dict, List, Any, Optional
from pathlib import Path
from abi import logger


class AINetworkConfig:
    """Configuration class for AI Network module management"""
    
    # Class-level cache for configuration data
    _config_cache = {}
    _cache_timestamp = {}
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.config = self._load_config_cached()
        self.ai_network = self.config.get("ai_network", {})
        
    def _load_config_cached(self) -> Dict[str, Any]:
        """Load configuration from YAML file with caching and file modification check"""
        import os
        import time
        
        try:
            # Get file modification time
            file_mtime = os.path.getmtime(self.config_path)
            
            # Check if we have cached data and if file hasn't been modified
            if (self.config_path in self._config_cache and 
                self.config_path in self._cache_timestamp and
                self._cache_timestamp[self.config_path] >= file_mtime):
                logger.debug(f"📋 Using cached configuration from {self.config_path}")
                return self._config_cache[self.config_path]
            
            # Load fresh configuration
            config = self._load_config()
            
            # Cache the configuration and timestamp
            self._config_cache[self.config_path] = config
            self._cache_timestamp[self.config_path] = time.time()
            
            return config
            
        except Exception as e:
            logger.error(f"❌ Error in cached config loading: {e}")
            return self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        try:
            with open(self.config_path, 'r') as file:
                config = yaml.safe_load(file)
                logger.info(f"✅ Loaded configuration from {self.config_path}")
                return config
        except FileNotFoundError:
            logger.error(f"❌ Configuration file not found: {self.config_path}")
            return {}
        except yaml.YAMLError as e:
            logger.error(f"❌ Error parsing YAML configuration: {e}")
            return {}
    
    def get_enabled_modules(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get all enabled modules organized by category - adapted for simplified structure"""
        enabled_modules = {"core": []}
        
        # Convert the simplified ai_network structure to the expected format
        for agent_name, agent_config in self.ai_network.items():
            if isinstance(agent_config, dict) and agent_config.get("enabled", False):
                # Convert agent config to module format expected by the loader
                module_config = {
                    "name": agent_name,
                    "enabled": True,
                    "description": agent_config.get("description", ""),
                    "strengths": agent_config.get("strengths", ""),
                    "use_when": agent_config.get("use_when", "")
                }
                enabled_modules["core"].append(module_config)
        
        logger.info(f"✅ Enabled {len(enabled_modules['core'])} modules in 'core' category")
        
        # Add empty categories to avoid warnings
        enabled_modules["custom"] = []
        enabled_modules["marketplace"] = []
        
        return enabled_modules
    
    def get_module_paths(self) -> Dict[str, str]:
        """Get the file system paths for each module category"""
        return {
            "core": "src/core/modules",
            "custom": "src/custom/modules",
            "marketplace": "src/marketplace/modules"
        }
    
    def should_load_module(self, module_name: str, category: str) -> bool:
        """Check if a specific module should be loaded"""
        category_config = self.ai_network.get(category, {})
        
        if not category_config.get("enabled", False):
            return False
            
        modules = category_config.get("modules", [])
        
        for module in modules:
            if module.get("name") == module_name:
                return module.get("enabled", False)
        
        # If module not found in config and auto_discover is enabled for custom modules
        if category == "custom_modules" and category_config.get("auto_discover", False):
            return True
            
        return False
    
    def get_loading_settings(self) -> Dict[str, Any]:
        """Get module loading settings"""
        return self.ai_network.get("loading", {
            "fail_on_error": True,
            "parallel_loading": False,
            "timeout_seconds": 30,
            "retry_attempts": 3
        })
    
    def get_module_info(self, module_name: str, category: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific module"""
        category_config = self.ai_network.get(category, {})
        modules = category_config.get("modules", [])
        
        for module in modules:
            if module.get("name") == module_name:
                return module
        
        return None
    
    def get_enabled_agents_metadata(self) -> Dict[str, Dict[str, str]]:
        """Get metadata for all enabled agents for dynamic system prompt generation - adapted for simplified structure"""
        enabled_agents = {}

        # Convert the simplified ai_network structure to the expected format
        for agent_name, agent_config in self.ai_network.items():
            if isinstance(agent_config, dict) and agent_config.get("enabled", False):
                enabled_agents[agent_name] = {
                    "category": "core",  # All agents are now in core category
                    "strengths": agent_config.get("strengths", "General AI capabilities"),
                    "use_when": agent_config.get("use_when", "General assistance tasks")
                }

        return enabled_agents
    
    def get_intent_mapping(self) -> Dict[str, List[str]]:
        """Get intent mapping from ABI agent configuration"""
        abi_config = self.ai_network.get("abi", {})
        if abi_config.get("enabled", False):
            return abi_config.get("intent_mapping", {})
        return {}
    
    def get_logging_config(self) -> Dict[str, Any]:
        """Get logging configuration from config.yaml"""
        return self.config.get("logging", {
            "level": "INFO",
            "format": "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s",
            "console_output": True,
            "file_output": False,
            "file_path": "storage/datastore/utils/logs/{timestamp}_abi_logs.txt"
        })
    
    def get_log_level(self) -> str:
        """Get the configured log level"""
        logging_config = self.get_logging_config()
        return logging_config.get("level", "INFO").upper()
    
    def get_logging_manager(self):
        """Get a LoggingManager instance for this configuration"""
        from src.utils.Logging import create_logging_manager
        return create_logging_manager(self.get_logging_config())
    
    def setup_logging(self) -> Optional[str]:
        """
        Setup logging based on configuration using LoggingManager
        
        Returns:
            Optional[str]: Log file path if file logging is enabled, None otherwise
        """
        logging_manager = self.get_logging_manager()
        return logging_manager.setup_logging()
    
    def validate_configuration(self) -> List[str]:
        """Validate the AI Network configuration and return any issues"""
        issues = []
        
        if not self.ai_network:
            issues.append("No 'ai_network' configuration found")
            return issues
        
        # Check required categories
        required_categories = ["core", "custom", "marketplace"]
        for category in required_categories:
            if category not in self.ai_network:
                issues.append(f"Missing required category: {category}")
        
        # Validate module configurations
        for category, config in self.ai_network.items():
            if category == "loading":
                continue
                
            if not isinstance(config, dict):
                issues.append(f"Category '{category}' must be a dictionary")
                continue
                
            modules = config.get("modules", [])
            if not isinstance(modules, list):
                issues.append(f"Modules in '{category}' must be a list")
                continue
            
            # Check for duplicate module names within category
            module_names = [m.get("name") for m in modules if m.get("name")]
            if len(module_names) != len(set(module_names)):
                issues.append(f"Duplicate module names found in '{category}'")
            
            # Validate individual modules
            for i, module in enumerate(modules):
                if not isinstance(module, dict):
                    issues.append(f"Module {i} in '{category}' must be a dictionary")
                    continue
                    
                if not module.get("name"):
                    issues.append(f"Module {i} in '{category}' missing required 'name' field")
                
                if "enabled" not in module:
                    issues.append(f"Module '{module.get('name', i)}' in '{category}' missing 'enabled' field")
        
        return issues


# Global configuration instance
_config_instance: Optional[AINetworkConfig] = None


def get_ai_network_config(config_path: str = "config.yaml") -> AINetworkConfig:
    """Get the global AI Network configuration instance"""
    global _config_instance
    
    if _config_instance is None:
        _config_instance = AINetworkConfig(config_path)
        
        # Validate configuration
        issues = _config_instance.validate_configuration()
        if issues:
            logger.warning("⚠️ Configuration validation issues found:")
            for issue in issues:
                logger.warning(f"  - {issue}")
    
    return _config_instance


def reload_config(config_path: str = "config.yaml") -> AINetworkConfig:
    """Reload the configuration (useful for testing or config changes)"""
    global _config_instance
    _config_instance = None
    return get_ai_network_config(config_path)
