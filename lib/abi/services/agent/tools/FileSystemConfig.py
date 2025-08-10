"""
File System Configuration for ABI Agents

This module provides configuration management for file system tools,
including security settings, access control, and path restrictions.
"""

import os
from pathlib import Path
from typing import List, Set, Optional, Dict, Any
from dataclasses import dataclass, field
from abi import logger


@dataclass
class FileSystemPermissions:
    """File system permissions configuration."""
    
    # Allowed operations
    can_read: bool = True
    can_write: bool = True
    can_delete: bool = False
    can_create_directories: bool = True
    can_move_files: bool = False
    can_copy_files: bool = True
    
    # File type restrictions
    allowed_extensions: Set[str] = field(default_factory=lambda: {
        '.txt', '.md', '.py', '.js', '.html', '.css', '.json', '.xml', 
        '.csv', '.yaml', '.yml', '.log', '.conf', '.ini', '.cfg'
    })
    
    # Size limits (in bytes)
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    max_directory_size: int = 100 * 1024 * 1024  # 100MB
    
    # Path restrictions
    allowed_paths: Set[str] = field(default_factory=set)
    blocked_paths: Set[str] = field(default_factory=lambda: {
        '/etc', '/var', '/usr', '/bin', '/sbin', '/dev', '/proc', '/sys',
        '/root', '/home', '/tmp', '/var/log', '/var/cache'
    })
    
    # Recursive depth limits
    max_recursive_depth: int = 5
    
    def is_extension_allowed(self, extension: str) -> bool:
        """Check if file extension is allowed."""
        return extension.lower() in self.allowed_extensions
    
    def is_path_allowed(self, path: str) -> bool:
        """Check if path is allowed."""
        path_obj = Path(path).resolve()
        
        # Check blocked paths first
        for blocked in self.blocked_paths:
            if str(path_obj).startswith(blocked):
                return False
        
        # If specific allowed paths are set, check against them
        if self.allowed_paths:
            return any(str(path_obj).startswith(allowed) for allowed in self.allowed_paths)
        
        return True


@dataclass
class FileSystemConfig:
    """File system configuration for ABI agents."""
    
    # Base configuration
    base_path: str = "."
    permissions: FileSystemPermissions = field(default_factory=FileSystemPermissions)
    
    # Security settings
    enable_path_validation: bool = True
    enable_size_limits: bool = True
    enable_extension_validation: bool = True
    enable_logging: bool = True
    
    # Performance settings
    max_files_per_operation: int = 1000
    timeout_seconds: int = 30
    
    # Environment-specific settings
    is_production: bool = False
    is_development: bool = True
    
    def __post_init__(self):
        """Post-initialization setup."""
        self.base_path = str(Path(self.base_path).resolve())
    
    def validate_path(self, path: str) -> bool:
        """Validate if a path is allowed."""
        if not self.enable_path_validation:
            return True
        
        return self.permissions.is_path_allowed(path)
    
    def validate_file_size(self, size: int) -> bool:
        """Validate if file size is within limits."""
        if not self.enable_size_limits:
            return True
        
        return size <= self.permissions.max_file_size
    
    def validate_extension(self, extension: str) -> bool:
        """Validate if file extension is allowed."""
        if not self.enable_extension_validation:
            return True
        
        return self.permissions.is_extension_allowed(extension)
    
    def get_allowed_operations(self) -> Dict[str, bool]:
        """Get allowed operations."""
        return {
            'read': self.permissions.can_read,
            'write': self.permissions.can_write,
            'delete': self.permissions.can_delete,
            'create_directories': self.permissions.can_create_directories,
            'move_files': self.permissions.can_move_files,
            'copy_files': self.permissions.can_copy_files
        }


class FileSystemConfigManager:
    """Manager for file system configurations."""
    
    def __init__(self):
        self._configs: Dict[str, FileSystemConfig] = {}
        self._default_config: Optional[FileSystemConfig] = None
    
    def register_config(self, name: str, config: FileSystemConfig) -> None:
        """Register a file system configuration."""
        self._configs[name] = config
        logger.info(f"Registered file system config: {name}")
    
    def get_config(self, name: str) -> FileSystemConfig:
        """Get a file system configuration by name."""
        if name not in self._configs:
            if self._default_config is None:
                # Create default config
                self._default_config = FileSystemConfig()
                logger.info("Created default file system config")
            return self._default_config
        
        return self._configs[name]
    
    def set_default_config(self, config: FileSystemConfig) -> None:
        """Set the default configuration."""
        self._default_config = config
        logger.info("Set default file system config")
    
    def list_configs(self) -> List[str]:
        """List all registered configuration names."""
        return list(self._configs.keys())
    
    def remove_config(self, name: str) -> bool:
        """Remove a configuration."""
        if name in self._configs:
            del self._configs[name]
            logger.info(f"Removed file system config: {name}")
            return True
        return False


# Global configuration manager instance
config_manager = FileSystemConfigManager()


def create_default_configs():
    """Create default configurations for different environments."""
    
    # Development configuration
    dev_config = FileSystemConfig(
        base_path=".",
        is_development=True,
        permissions=FileSystemPermissions(
            can_read=True,
            can_write=True,
            can_delete=True,
            can_create_directories=True,
            can_move_files=True,
            can_copy_files=True,
            max_file_size=50 * 1024 * 1024,  # 50MB
            allowed_extensions={
                '.txt', '.md', '.py', '.js', '.html', '.css', '.json', '.xml', 
                '.csv', '.yaml', '.yml', '.log', '.conf', '.ini', '.cfg',
                '.pdf', '.jpg', '.jpeg', '.png', '.gif', '.svg'
            }
        )
    )
    
    # Production configuration
    prod_config = FileSystemConfig(
        base_path="storage",
        is_production=True,
        permissions=FileSystemPermissions(
            can_read=True,
            can_write=True,
            can_delete=False,
            can_create_directories=True,
            can_move_files=False,
            can_copy_files=True,
            max_file_size=5 * 1024 * 1024,  # 5MB
            allowed_extensions={
                '.txt', '.md', '.json', '.xml', '.csv', '.yaml', '.yml'
            },
            allowed_paths={'storage'}
        )
    )
    
    # Restricted configuration
    restricted_config = FileSystemConfig(
        base_path="storage/readonly",
        permissions=FileSystemPermissions(
            can_read=True,
            can_write=False,
            can_delete=False,
            can_create_directories=False,
            can_move_files=False,
            can_copy_files=False,
            max_file_size=1 * 1024 * 1024,  # 1MB
            allowed_extensions={'.txt', '.md', '.json'}
        )
    )
    
    # Register configurations
    config_manager.register_config("development", dev_config)
    config_manager.register_config("production", prod_config)
    config_manager.register_config("restricted", restricted_config)
    config_manager.set_default_config(dev_config)
    
    logger.info("Created default file system configurations")


# Initialize default configurations
create_default_configs()
