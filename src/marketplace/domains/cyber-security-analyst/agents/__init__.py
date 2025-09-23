"""
Cyber Security Analyst Agents

Expert AI agents for cyber security analysis and management.
"""

# Import agents conditionally to avoid dependency issues
_conversational_available = False
# Disable conversational agent for now to avoid OpenAI dependency
# try:
#     from .ConversationalCyberAgent import (
#         ConversationalCyberAgent,
#         create_agent,
#         NAME,
#         DESCRIPTION,
#         AVATAR_URL
#     )
#     _conversational_available = True
# except ImportError:
#     _conversational_available = False

# Always available
from .CyberSecuritySPARQLAgent import CyberSecuritySPARQLAgent

__all__ = ["CyberSecuritySPARQLAgent"]

if _conversational_available:
    __all__.extend([
        "ConversationalCyberAgent",
        "create_agent", 
        "NAME",
        "DESCRIPTION",
        "AVATAR_URL"
    ])
