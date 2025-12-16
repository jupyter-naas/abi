"""
🚧 NOT FUNCTIONAL YET - Domain Expert Agent Template
Expert inside sales representative specializing in remote sales, phone prospecting, CRM management, and inbound lead conversion.
"""

from abi.services.agent.IntentAgent import (
    IntentAgent,
    AgentConfiguration,
    AgentSharedState,
)
from typing import Optional
from abi import logger

AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/domain-experts/inside-sales-representative.png"
NAME = "Inside Sales Representative"
TYPE = "domain-expert"
SLUG = "inside-sales-representative"
DESCRIPTION = "Expert inside sales representative specializing in remote sales, phone prospecting, CRM management, and inbound lead conversion."
MODEL = "gpt-4o"
SYSTEM_PROMPT = """You are a Inside Sales Representative Expert, a specialized AI assistant with deep expertise in remote sales, phone prospecting, crm management.

## Your Expertise
- **Remote Sales**: Specialized knowledge and practical experience
- **Phone Prospecting**: Specialized knowledge and practical experience
- **CRM Management**: Specialized knowledge and practical experience
- **Lead Conversion**: Specialized knowledge and practical experience
- **Sales Automation**: Specialized knowledge and practical experience
- **Customer Qualification**: Specialized knowledge and practical experience

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
TEMPERATURE = 0.2
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
    """Create Inside Sales Representative Expert Agent - NOT FUNCTIONAL YET"""
    logger.warning("🚧 InsideSalesRepresentativeAgent is not functional yet - template only")
    return None

class InsideSalesRepresentativeAgent(IntentAgent):
    """Inside Sales Representative Expert Agent - NOT FUNCTIONAL YET"""
    pass