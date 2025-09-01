"""
🚧 NOT FUNCTIONAL YET - Domain Expert Agent Template
Expert account executive specializing in client relationship management, sales strategy, account growth, and revenue optimization.
"""

from abi.services.agent.IntentAgent import (
    IntentAgent,
    AgentConfiguration,
    AgentSharedState,
)
from typing import Optional
from abi import logger

AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/domain-experts/account-executive.png"
NAME = "Account Executive"
TYPE = "domain-expert"
SLUG = "account-executive"
DESCRIPTION = "Expert account executive specializing in client relationship management, sales strategy, account growth, and revenue optimization."
MODEL = "gpt-4o"
SYSTEM_PROMPT = """You are a Account Executive Expert, a specialized AI assistant with deep expertise in client relationship management, sales strategy, account growth.

## Your Expertise
- **Client Relationship Management**: Specialized knowledge and practical experience
- **Sales Strategy**: Specialized knowledge and practical experience
- **Account Growth**: Specialized knowledge and practical experience
- **Revenue Optimization**: Specialized knowledge and practical experience
- **Contract Negotiation**: Specialized knowledge and practical experience
- **Customer Retention**: Specialized knowledge and practical experience

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
    """Create Account Executive Expert Agent - NOT FUNCTIONAL YET"""
    logger.warning("🚧 AccountExecutiveAgent is not functional yet - template only")
    return None

class AccountExecutiveAgent(IntentAgent):
    """Account Executive Expert Agent - NOT FUNCTIONAL YET"""
    pass