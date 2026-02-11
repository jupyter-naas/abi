"""
Environment-aware configuration loader.
Reads from config.yaml and resolves environment variables.
"""

import os
import re
from pathlib import Path
from typing import Any

import yaml


def _resolve_env_vars(value: Any) -> Any:
    """Recursively resolve ${VAR} and ${VAR:-default} patterns in values."""
    if isinstance(value, str):
        # Pattern: ${VAR} or ${VAR:-default}
        pattern = r'\$\{([^}:]+)(?::-([^}]*))?\}'
        
        def replacer(match):
            var_name = match.group(1)
            default = match.group(2) if match.group(2) is not None else ""
            return os.environ.get(var_name, default)
        
        return re.sub(pattern, replacer, value)
    elif isinstance(value, dict):
        return {k: _resolve_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_resolve_env_vars(item) for item in value]
    else:
        return value


def load_config(env: str | None = None) -> dict:
    """
    Load configuration for the specified environment.
    
    Args:
        env: Environment name (local, cloudflare, staging). 
             Defaults to NEXUS_ENV or 'local'.
    
    Returns:
        Merged configuration dict with environment-specific settings.
    """
    env = env or os.environ.get("NEXUS_ENV", "local")
    
    # Find config.yaml (check multiple locations)
    config_paths = [
        Path(__file__).parent.parent.parent.parent.parent / "config.yaml",  # /nexus/config.yaml
        Path.cwd() / "config.yaml",
        Path.cwd().parent.parent / "config.yaml",  # From apps/api
    ]
    
    config_path = None
    for path in config_paths:
        if path.exists():
            config_path = path
            break
    
    if not config_path:
        raise FileNotFoundError(
            f"config.yaml not found. Searched: {[str(p) for p in config_paths]}"
        )
    
    with open(config_path) as f:
        raw_config = yaml.safe_load(f)
    
    # Get environment-specific config
    environments = raw_config.get("environments", {})
    if env not in environments:
        available = list(environments.keys())
        raise ValueError(f"Unknown environment '{env}'. Available: {available}")
    
    env_config = environments[env]
    shared_config = raw_config.get("shared", {})
    
    # Merge shared + environment config
    merged = {**shared_config, **env_config}
    
    # Resolve environment variables
    resolved = _resolve_env_vars(merged)
    
    # Add metadata
    resolved["_env"] = env
    resolved["_config_path"] = str(config_path)
    
    return resolved


class NexusConfig:
    """
    Typed configuration wrapper for easy access.
    """
    
    def __init__(self, env: str | None = None):
        self._config = load_config(env)
        self._env = self._config["_env"]
    
    @property
    def env(self) -> str:
        return self._env
    
    @property
    def is_local(self) -> bool:
        return self._env == "local"
    
    @property
    def is_cloudflare(self) -> bool:
        return self._env == "cloudflare"
    
    @property
    def name(self) -> str:
        return self._config.get("name", "Unknown")
    
    @property
    def app_name(self) -> str:
        return self._config.get("app_name", "NEXUS")
    
    @property
    def version(self) -> str:
        return self._config.get("version", "0.0.0")
    
    # Frontend
    @property
    def frontend_url(self) -> str:
        return self._config.get("frontend", {}).get("url", "http://localhost:3000")
    
    # API
    @property
    def api_url(self) -> str:
        return self._config.get("api", {}).get("url", "http://localhost:8000")
    
    @property
    def cors_origins(self) -> list[str]:
        return self._config.get("api", {}).get("cors_origins", [])
    
    # Database
    @property
    def database_type(self) -> str:
        return self._config.get("database", {}).get("type", "postgresql")
    
    @property
    def database_url(self) -> str | None:
        return self._config.get("database", {}).get("url")
    
    @property
    def database_binding(self) -> str | None:
        """For Cloudflare D1 binding name."""
        return self._config.get("database", {}).get("binding")
    
    @property
    def database_pool_size(self) -> int:
        return self._config.get("database", {}).get("pool_size", 5)
    
    # Cache
    @property
    def cache_type(self) -> str:
        return self._config.get("cache", {}).get("type", "redis")
    
    @property
    def cache_url(self) -> str | None:
        return self._config.get("cache", {}).get("url")
    
    @property
    def cache_binding(self) -> str | None:
        """For Cloudflare KV binding name."""
        return self._config.get("cache", {}).get("binding")
    
    # Auth
    @property
    def auth_type(self) -> str:
        return self._config.get("auth", {}).get("type", "jwt")
    
    @property
    def auth_secret(self) -> str:
        return self._config.get("auth", {}).get("secret", "")
    
    @property
    def token_expire_minutes(self) -> int:
        return self._config.get("auth", {}).get("token_expire_minutes", 10080)
    
    # Providers
    @property
    def providers(self) -> dict:
        return self._config.get("providers", {})
    
    def get_provider(self, name: str) -> dict:
        return self.providers.get(name, {})
    
    def is_provider_enabled(self, name: str) -> bool:
        return self.get_provider(name).get("enabled", False)
    
    # Features
    @property
    def features(self) -> dict:
        return self._config.get("features", {})
    
    def is_feature_enabled(self, name: str) -> bool:
        return self.features.get(name, False)
    
    # Rate limiting
    @property
    def rate_limit_rpm(self) -> int:
        return self._config.get("rate_limit", {}).get("requests_per_minute", 60)
    
    @property
    def rate_limit_burst(self) -> int:
        return self._config.get("rate_limit", {}).get("burst", 10)
    
    # Raw access
    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)
    
    def __getitem__(self, key: str) -> Any:
        return self._config[key]
    
    def to_dict(self) -> dict:
        return self._config.copy()


# Singleton instance
_config: NexusConfig | None = None


def get_config(env: str | None = None) -> NexusConfig:
    """Get the configuration singleton."""
    global _config
    if _config is None:
        _config = NexusConfig(env)
    return _config


def reload_config(env: str | None = None) -> NexusConfig:
    """Force reload configuration."""
    global _config
    _config = NexusConfig(env)
    return _config
