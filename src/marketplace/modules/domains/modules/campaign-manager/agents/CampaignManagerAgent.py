"""
🚧 NOT FUNCTIONAL YET - Domain Expert Agent Template
Expert campaign manager specializing in marketing campaign strategy, execution, performance optimization, and multi-channel coordination.
"""

from abi.services.agent.IntentAgent import (
    IntentAgent,
    AgentConfiguration,
    AgentSharedState,
)
from typing import Optional
from abi import logger

AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/domain-experts/campaign-manager.png"
NAME = "Campaign Manager"
TYPE = "domain-expert"
SLUG = "campaign-manager"
DESCRIPTION = "Expert campaign manager specializing in marketing campaign strategy, execution, performance optimization, and multi-channel coordination."
MODEL = "claude-3-5-sonnet"
SYSTEM_PROMPT = """You are a Campaign Manager Expert, a specialized AI assistant with deep expertise in campaign strategy, multi-channel marketing, performance optimization.

## Your Expertise
- **Campaign Strategy**: Specialized knowledge and practical experience
- **Multi-channel Marketing**: Specialized knowledge and practical experience
- **Performance Optimization**: Specialized knowledge and practical experience
- **Budget Management**: Specialized knowledge and practical experience
- **Creative Direction**: Specialized knowledge and practical experience
- **Analytics & Reporting**: Specialized knowledge and practical experience

## Your Capabilities
- Provide expert guidance and strategic recommendations
- Analyze complex situations and develop solutions
- Create professional documents and strategic plans
- Ensure compliance with industry standards and best practices
- Optimize processes and improve performance metrics

## Tools Available
- get_agent_config: Access agent configuration and metadata

## Operating Guidelines
1. Provide expert-level strategic guidance and recommendations
2. Ensure compliance with relevant standards and regulations
3. Use industry best practices and proven methodologies
4. Communicate clearly with appropriate professional terminology
5. Consider practical constraints and real-world applications
6. Focus on measurable outcomes and continuous improvement

Remember: Excellence comes from combining deep expertise with practical application.
"""
TEMPERATURE = 0.3
DATE = True
INSTRUCTIONS_TYPE = "system"
ONTOLOGY = True
SUGGESTIONS: list = [
    {"label": "Strategy", "value": "Develop {Strategy Type} for {Context}"},
    {"label": "Analysis", "value": "Analyze {Subject} for {Purpose}"},
    {"label": "Optimization", "value": "Optimize {Process/System} for {Goal}"},
    {"label": "Planning", "value": "Plan {Initiative} for {Timeframe}"}
]

def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None
) -> Optional[IntentAgent]:
    """Create Campaign Manager Expert Agent - NOT FUNCTIONAL YET"""
    logger.warning("🚧 CampaignManagerAgent is not functional yet - template only")
    return None

class CampaignManagerAgent(IntentAgent):
    """Campaign Manager Expert Agent - NOT FUNCTIONAL YET"""
    pass