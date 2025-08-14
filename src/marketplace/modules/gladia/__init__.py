"""
Gladia Speech-to-Text Module

Simple module for speech-to-text transcription using Gladia's API.
"""

# Lazy import to avoid initialization issues during module discovery
def _get_agent_components():
    from .agents.GladiaAgent import (
        create_agent,
        get_default_agent,
        router,
        NAME,
        DESCRIPTION,
        AVATAR_URL
    )
    return create_agent, get_default_agent, router, NAME, DESCRIPTION, AVATAR_URL

# Export functions for dynamic access
def get_create_agent():
    create_agent, _, _, _, _, _ = _get_agent_components()
    return create_agent

def get_default_agent():
    _, default_agent, _, _, _, _ = _get_agent_components()
    return default_agent

from .integrations.GladiaIntegration import (
    GladiaIntegration,
    GladiaIntegrationConfiguration,
    TranscriptionJob,
    TranscriptionResult,
    Speaker
)

from .models.solaria import model as solaria_model

# Register apps - simplified
APPS = {
    "cli": {
        "main": "apps/cli/playground.py",
        "name": "Gladia CLI",
        "description": "Simple command-line transcription tool",
        "executable": True
    }
}

# Available components for easy import
__all__ = [
    # Main agent
    "get_create_agent",
    "get_default_agent",
    
    # Integration
    "GladiaIntegration",
    "GladiaIntegrationConfiguration",
    "TranscriptionJob",
    "TranscriptionResult",
    "Speaker",
    
    # Model
    "solaria_model",
    
    # Apps
    "APPS"
]