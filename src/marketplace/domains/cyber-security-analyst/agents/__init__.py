"""
Cyber Security Analyst Agents

Expert AI agents for cyber security analysis and management.
"""

# Always available
from .CyberSecuritySPARQLAgent import CyberSecuritySPARQLAgent

# Main agent - conditionally available based on OpenAI API key
try:
    from .CyberSecurityAnalystAgent import (  # noqa: F401
        create_agent,  # noqa: F401
        NAME,  # noqa: F401
        DESCRIPTION,  # noqa: F401
        AVATAR_URL  # noqa: F401
    )
    _main_agent_available = True
except ImportError:
    _main_agent_available = False

__all__ = ["CyberSecuritySPARQLAgent"]

if _main_agent_available:
    __all__.extend([
        "create_agent", 
        "NAME",
        "DESCRIPTION",
        "AVATAR_URL"
    ])
