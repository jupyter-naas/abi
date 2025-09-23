"""
Cyber Security Analyst Agents

Expert AI agents for cyber security analysis and management.
"""

# Always available
from .CyberSecuritySPARQLAgent import CyberSecuritySPARQLAgent

# Main agent - conditionally available based on OpenAI API key
try:
    from .CyberSecurityAnalystAgent import (
        create_agent,
        NAME,
        DESCRIPTION,
        AVATAR_URL
    )
    _main_agent_available = True
except ImportError as e:
    _main_agent_available = False

__all__ = ["CyberSecuritySPARQLAgent"]

if _main_agent_available:
    __all__.extend([
        "create_agent", 
        "NAME",
        "DESCRIPTION",
        "AVATAR_URL"
    ])
