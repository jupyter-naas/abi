"""
Cyber Security Analyst Domain Module

Expert cyber security analyst specializing in threat analysis, vulnerability assessment,
incident response, and security architecture.

This module provides:
- CyberSecurityAnalystAgent: Expert AI agent for cyber security analysis
- Comprehensive ontologies: ThreatLandscape, VulnerabilityManagement, SecurityControls
- Specialized workflows: ThreatAssessment, IncidentResponse, VulnerabilityAssessment, SecurityArchitecture
- Model configurations: Optimized for security analysis tasks
"""

from .agents.CyberSecurityAnalystAgent import (
    CyberSecurityAnalystAgent,
    create_agent,
    NAME,
    DESCRIPTION,
    AVATAR_URL
)

__all__ = [
    "CyberSecurityAnalystAgent",
    "create_agent",
    "NAME",
    "DESCRIPTION",
    "AVATAR_URL"
]
